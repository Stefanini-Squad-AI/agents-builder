"""Analysis sub-module for package parsing and analysis.

Provides:
- SSIS Parser: Extract structure from .dtsx files
- Connection Points Extractor: Identify source/target tables
- LLM Analysis: Technology-aware enrichment
- Blocker Detection: Identify and auto-resolve blockers
"""

from app.modules.migration_workbench.analysis.analyzer import (
    PackageAnalyzer,
    create_analyzer,
)
from app.modules.migration_workbench.analysis.blockers import (
    BlockerDetector,
    detect_blockers,
)
from app.modules.migration_workbench.analysis.extractor import (
    ConnectionPointsExtractor,
    extract_connection_points,
)
from app.modules.migration_workbench.analysis.parsers import (
    ParserInterface,
    SSISParser,
    get_parser,
)
from app.modules.migration_workbench.analysis.router import router as analysis_router
from app.modules.migration_workbench.analysis.schemas import (
    BlockerItem,
    BlockerSeverity,
    BlockerType,
    ConnectionManager,
    DataFlow,
    DetectedPattern,
    ExtractedConnectionPoints,
    PackageAnalysis,
    SSISPackage,
)
from app.modules.migration_workbench.analysis.service import AnalysisService

__all__ = [
    # Parsers
    "ParserInterface",
    "SSISParser",
    "get_parser",
    # Extraction
    "ConnectionPointsExtractor",
    "extract_connection_points",
    # Analysis
    "PackageAnalyzer",
    "create_analyzer",
    # Blockers
    "BlockerDetector",
    "detect_blockers",
    # Schemas
    "SSISPackage",
    "ConnectionManager",
    "DataFlow",
    "PackageAnalysis",
    "ExtractedConnectionPoints",
    "DetectedPattern",
    "BlockerItem",
    "BlockerSeverity",
    "BlockerType",
    # Service & Router
    "AnalysisService",
    "analysis_router",
]
