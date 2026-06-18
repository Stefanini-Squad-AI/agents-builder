"""`analyze_package` Dramatiq actor.

Pipeline for analyzing ETL packages:

  1. `pending`     -> `analyzing`    (worker picked the job)
  2. `analyzing`   -> `analyzed`     (analysis completed successfully)
                  or `failed`        (parser error or LLM failure)

State transitions are idempotent: re-running on an `analyzed` package
is a no-op. To re-analyze, reset status to `pending` and re-enqueue.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import dramatiq
import structlog
from sqlalchemy import select

from app.db import session_scope
from app.domain import register_models
from app.modules.migration_workbench.analysis.analyzer import PackageAnalyzer
from app.modules.migration_workbench.analysis.blockers import BlockerDetector
from app.modules.migration_workbench.analysis.extractor import extract_connection_points
from app.modules.migration_workbench.analysis.parsers import get_parser
from app.modules.migration_workbench.analysis.parsers.base import ParseError
from app.modules.migration_workbench.map.service import MigrationMapService
from app.modules.migration_workbench.models import ETLPackage, PackageConnectionPoints
from app.services.llm_service_factory import LlmServiceFactory
from app.storage import resolve_artifact_path

register_models()

log = structlog.get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=0, time_limit=300_000)
def analyze_package(package_id: str) -> None:
    """Parse and analyze an ETL package.
    
    Time-limited to 5 minutes to allow for LLM analysis.
    
    Steps:
    1. Load package file content
    2. Parse using technology-specific parser
    3. Extract connection points (sources/targets)
    4. Run LLM analysis for patterns and blockers
    5. Auto-resolve blockers using project context
    6. Store results
    """
    pkg_id = uuid.UUID(package_id)
    log.info("analyze_package_start", package_id=str(pkg_id))
    
    # Step 1: Claim the package (status pending -> analyzing)
    with session_scope() as session:
        package = session.execute(
            select(ETLPackage).where(ETLPackage.id == pkg_id)
        ).scalar_one_or_none()
        
        if package is None:
            log.warning("analyze_package_not_found", package_id=str(pkg_id))
            return
        
        if package.analysis_status == "analyzed":
            log.info("analyze_package_already_done", package_id=str(pkg_id))
            return
        
        if package.analysis_status == "analyzing":
            log.warning("analyze_package_already_in_progress", package_id=str(pkg_id))
            return
        
        # Claim the job
        package.analysis_status = "analyzing"
        package.analysis_error = None
        
        # Get info needed for analysis
        project_id = package.project_id
        source_technology = package.source_technology or "ssis"
        file_path = package.file_path
        package_name = package.package_name
    
    # Step 2: Load and parse package file
    try:
        content = _load_package_content(file_path)
        parser = get_parser(source_technology)
        
        if not parser.can_parse(content):
            _mark_failed(pkg_id, f"Parser cannot handle this file format")
            return
        
        parsed = parser.parse(content)
        
    except ParseError as e:
        log.error("analyze_package_parse_error", package_id=str(pkg_id), error=str(e))
        _mark_failed(pkg_id, f"Parse error: {e}")
        return
    except FileNotFoundError:
        log.error("analyze_package_file_not_found", package_id=str(pkg_id), path=file_path)
        _mark_failed(pkg_id, f"Package file not found: {file_path}")
        return
    except Exception as e:
        log.exception("analyze_package_parse_unhandled", package_id=str(pkg_id))
        _mark_failed(pkg_id, f"Parse error: {type(e).__name__}: {e}"[:200])
        return
    
    # Step 3: Extract connection points
    try:
        connection_points = extract_connection_points(parsed)
    except Exception as e:
        log.exception("analyze_package_extract_error", package_id=str(pkg_id))
        # Non-fatal - continue without connection points
        connection_points = None
    
    # Step 4: Run LLM analysis
    try:
        with session_scope() as session:
            # Get project slug for LLM service
            package = session.execute(
                select(ETLPackage).where(ETLPackage.id == pkg_id)
            ).scalar_one()
            
            # Create LLM service
            factory = LlmServiceFactory()
            llm_service = factory.create_for_project_id(project_id, session)
            
            # Run analysis
            analyzer = PackageAnalyzer(llm_service)
            analysis = analyzer.analyze(
                package=parsed,
                package_id=pkg_id,
                source_technology=source_technology,
            )
            
    except Exception as e:
        log.exception("analyze_package_llm_error", package_id=str(pkg_id))
        # LLM failure - use structural analysis only
        analysis = None
    
    # Step 5: Process blockers with auto-resolution
    try:
        with session_scope() as session:
            if analysis and analysis.blockers:
                detector = BlockerDetector(session, project_id)
                processed_blockers = detector.process_blockers(analysis, pkg_id)
                analysis.blockers = processed_blockers
    except Exception as e:
        log.exception("analyze_package_blocker_error", package_id=str(pkg_id))
        # Non-fatal - continue with unprocessed blockers
    
    # Step 6: Store results
    with session_scope() as session:
        package = session.execute(
            select(ETLPackage).where(ETLPackage.id == pkg_id)
        ).scalar_one()
        
        # Store connection points
        if connection_points:
            _store_connection_points(session, pkg_id, connection_points)
        
        # Update package with analysis results
        package.analysis_status = "analyzed"
        package.analyzed_at = datetime.now(timezone.utc)
        
        if analysis:
            package.complexity = analysis.complexity
            package.domain = analysis.domain
            package.estimated_effort = analysis.estimated_effort
            
            # Store analysis JSON
            package.analysis_json = {
                "patterns": [p.model_dump() for p in analysis.detected_patterns],
                "blockers": [b.model_dump() for b in analysis.blockers],
                "business_rules": [r.model_dump() for r in analysis.business_rules],
                "summary": analysis.analysis_summary,
                "target_structure": analysis.target_notebook_structure,
                "notes": analysis.migration_notes,
            }
            
            # Count blockers
            package.blockers_count = len(analysis.blockers)
            package.auto_resolved_count = sum(
                1 for b in analysis.blockers if b.auto_resolved
            )
        
        # Store parse warnings
        if parsed.parse_warnings:
            package.parse_warnings = parsed.parse_warnings
    
    # Step 7: Update Migration Map
    if connection_points:
        try:
            with session_scope() as session:
                map_service = MigrationMapService(session)
                
                # Convert connection points to map format
                sources = [
                    {
                        "type": "table",
                        "name": t.table_name,
                        "schema": t.schema_name,
                        "connection": t.connection_ref,
                        "access_type": t.access_type,
                    }
                    for t in connection_points.source_tables
                ]
                targets = [
                    {
                        "type": "table",
                        "name": t.table_name,
                        "schema": t.schema_name,
                        "connection": t.connection_ref,
                        "access_type": t.access_type,
                    }
                    for t in connection_points.target_tables
                ]
                
                # Add package to migration map
                map_result = map_service.add_package(
                    project_id=project_id,
                    package_id=pkg_id,
                    sources=sources,
                    targets=targets,
                )
                
                log.info(
                    "analyze_package_map_updated",
                    package_id=str(pkg_id),
                    objects_created=map_result.objects_created,
                    dependencies_created=map_result.dependencies_created,
                    clusters=map_result.clusters_created,
                )
        except Exception as e:
            log.exception("analyze_package_map_error", package_id=str(pkg_id))
            # Non-fatal - map update failure doesn't affect analysis status
    
    log.info(
        "analyze_package_done",
        package_id=str(pkg_id),
        patterns=len(analysis.detected_patterns) if analysis else 0,
        blockers=len(analysis.blockers) if analysis else 0,
    )


def _load_package_content(file_path: str) -> str:
    """Load package file content.
    
    Args:
        file_path: Relative or absolute path to package file
        
    Returns:
        File content as string
    """
    # Try as absolute path first
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except FileNotFoundError:
        pass
    
    # Try resolving through storage
    abs_path = resolve_artifact_path(file_path)
    with open(abs_path, "r", encoding="utf-8-sig") as f:
        return f.read()


def _store_connection_points(
    session,
    package_id: uuid.UUID,
    connection_points,
) -> None:
    """Store extracted connection points in database.
    
    Args:
        session: Database session
        package_id: Package ID
        connection_points: Extracted connection points
    """
    from sqlalchemy import select
    from app.modules.migration_workbench.models import PackageConnectionPoints
    
    # Check if record exists
    existing = session.execute(
        select(PackageConnectionPoints).where(
            PackageConnectionPoints.package_id == package_id
        )
    ).scalar_one_or_none()
    
    # Prepare data as JSONB-compatible dicts
    source_tables = [
        {
            "schema": t.schema_name,
            "table": t.table_name,
            "connection": t.connection_ref,
            "access_type": t.access_type,
        }
        for t in connection_points.source_tables
    ]
    
    target_tables = [
        {
            "schema": t.schema_name,
            "table": t.table_name,
            "connection": t.connection_ref,
            "access_type": t.access_type,
        }
        for t in connection_points.target_tables
    ]
    
    # Include files as well
    for f in connection_points.source_files:
        source_tables.append({
            "type": "file",
            "path": f.file_path,
            "file_type": f.file_type,
            "connection": f.connection_ref,
        })
    
    for f in connection_points.target_files:
        target_tables.append({
            "type": "file",
            "path": f.file_path,
            "file_type": f.file_type,
            "connection": f.connection_ref,
        })
    
    if existing:
        # Update existing record
        existing.source_tables = source_tables
        existing.target_tables = target_tables
        existing.source_connections = connection_points.source_connections
        existing.target_connections = connection_points.target_connections
        existing.declared_predecessors = connection_points.declared_predecessors
    else:
        # Create new record
        session.add(PackageConnectionPoints(
            package_id=package_id,
            source_tables=source_tables,
            target_tables=target_tables,
            source_connections=connection_points.source_connections,
            target_connections=connection_points.target_connections,
            declared_predecessors=connection_points.declared_predecessors,
        ))


def _mark_failed(package_id: uuid.UUID, error: str) -> None:
    """Mark package analysis as failed.
    
    Args:
        package_id: Package ID
        error: Error message
    """
    with session_scope() as session:
        package = session.execute(
            select(ETLPackage).where(ETLPackage.id == package_id)
        ).scalar_one()
        package.analysis_status = "failed"
        package.analysis_error = error[:500]
    
    log.warning(
        "analyze_package_failed",
        package_id=str(package_id),
        error=error,
    )
