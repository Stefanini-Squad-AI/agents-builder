"""Tests for Migration Workbench module.

Unit tests for SSIS parser and module components.
Integration tests for API endpoints (require WORKSHOP_RUN_INTEGRATION=1).
"""

from __future__ import annotations

import os

import pytest
from app.domain import register_models

register_models()


# =============================================================================
# Unit Tests - SSIS Parser
# =============================================================================

MINIMAL_SSIS_PACKAGE = """<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="www.microsoft.com/SqlServer/Dts"
  DTS:refId="Package"
  DTS:CreationDate="5/15/2026 10:00:00 AM"
  DTS:CreatorComputerName="DEVBOX"
  DTS:CreatorName="TestUser"
  DTS:DTSID="{12345678-1234-1234-1234-123456789012}"
  DTS:ExecutableType="Microsoft.Package"
  DTS:LastModifiedProductVersion="15.0.0"
  DTS:ObjectName="TestPackage"
  DTS:Description="A test SSIS package">
  <DTS:ConnectionManagers>
    <DTS:ConnectionManager
      DTS:refId="Package.ConnectionManagers[SourceDB]"
      DTS:CreationName="OLEDB"
      DTS:DTSID="{A1234567-1234-1234-1234-123456789012}"
      DTS:ObjectName="SourceDB">
      <DTS:ObjectData>
        <DTS:ConnectionManager
          DTS:ConnectionString="Data Source=SERVER1;Initial Catalog=SourceDB;Provider=SQLNCLI11.1;Integrated Security=SSPI;">
        </DTS:ConnectionManager>
      </DTS:ObjectData>
    </DTS:ConnectionManager>
    <DTS:ConnectionManager
      DTS:refId="Package.ConnectionManagers[TargetDB]"
      DTS:CreationName="OLEDB"
      DTS:DTSID="{B1234567-1234-1234-1234-123456789012}"
      DTS:ObjectName="TargetDB">
      <DTS:ObjectData>
        <DTS:ConnectionManager
          DTS:ConnectionString="Data Source=SERVER2;Initial Catalog=TargetDB;Provider=SQLNCLI11.1;Integrated Security=SSPI;">
        </DTS:ConnectionManager>
      </DTS:ObjectData>
    </DTS:ConnectionManager>
  </DTS:ConnectionManagers>
  <DTS:Variables>
    <DTS:Variable
      DTS:CreationName=""
      DTS:DTSID="{V1234567-1234-1234-1234-123456789012}"
      DTS:IncludeInDebugDump="6789"
      DTS:Namespace="User"
      DTS:ObjectName="BatchDate">
      <DTS:VariableValue DTS:DataType="7">5/15/2026 0:00:00</DTS:VariableValue>
    </DTS:Variable>
  </DTS:Variables>
  <DTS:Executables>
    <DTS:Executable
      DTS:refId="Package\\Load Data"
      DTS:CreationName="Microsoft.Pipeline"
      DTS:Description="Load data from source to target"
      DTS:DTSID="{E1234567-1234-1234-1234-123456789012}"
      DTS:ExecutableType="Microsoft.Pipeline"
      DTS:ObjectName="Load Data">
      <DTS:ObjectData>
        <pipeline version="1">
          <components>
            <component
              componentClassID="Microsoft.OLEDBSource"
              name="OLE DB Source"
              refId="Package\\Load Data\\OLE DB Source">
              <properties>
                <property name="AccessMode">0</property>
                <property name="OpenRowset">[dbo].[Customers]</property>
              </properties>
              <connections>
                <connection
                  refId="Package\\Load Data\\OLE DB Source.Connections[OleDbConnection]"
                  connectionManagerID="Package.ConnectionManagers[SourceDB]"
                  connectionManagerRefId="Package.ConnectionManagers[SourceDB]"
                  name="OleDbConnection"/>
              </connections>
            </component>
            <component
              componentClassID="Microsoft.OLEDBDestination"
              name="OLE DB Destination"
              refId="Package\\Load Data\\OLE DB Destination">
              <properties>
                <property name="OpenRowset">[dbo].[Customers_Staging]</property>
              </properties>
              <connections>
                <connection
                  refId="Package\\Load Data\\OLE DB Destination.Connections[OleDbConnection]"
                  connectionManagerID="Package.ConnectionManagers[TargetDB]"
                  connectionManagerRefId="Package.ConnectionManagers[TargetDB]"
                  name="OleDbConnection"/>
              </connections>
            </component>
          </components>
        </pipeline>
      </DTS:ObjectData>
    </DTS:Executable>
  </DTS:Executables>
</DTS:Executable>
"""


class TestSSISParser:
    """Tests for the SSIS parser."""

    def test_can_parse_valid_ssis(self):
        """Test that parser recognizes valid SSIS content."""
        from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
        
        parser = SSISParser()
        assert parser.can_parse(MINIMAL_SSIS_PACKAGE) is True

    def test_can_parse_rejects_non_ssis(self):
        """Test that parser rejects non-SSIS content."""
        from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
        
        parser = SSISParser()
        assert parser.can_parse("<root><data/></root>") is False
        assert parser.can_parse("not xml at all") is False

    def test_parse_extracts_package_name(self):
        """Test that parser extracts package name."""
        from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
        
        parser = SSISParser()
        result = parser.parse(MINIMAL_SSIS_PACKAGE)
        assert result.name == "TestPackage"
        assert result.description == "A test SSIS package"
        assert result.creator_name == "TestUser"

    def test_parse_extracts_connection_managers(self):
        """Test that parser extracts connection managers."""
        from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
        
        parser = SSISParser()
        result = parser.parse(MINIMAL_SSIS_PACKAGE)
        
        assert len(result.connection_managers) == 2
        
        names = {cm.name for cm in result.connection_managers}
        assert "SourceDB" in names
        assert "TargetDB" in names

    def test_parse_extracts_variables(self):
        """Test that parser extracts package variables."""
        from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
        
        parser = SSISParser()
        result = parser.parse(MINIMAL_SSIS_PACKAGE)
        
        assert len(result.variables) >= 1
        batch_date = next((v for v in result.variables if v.name == "BatchDate"), None)
        assert batch_date is not None
        assert batch_date.namespace == "User"

    def test_parse_extracts_tasks(self):
        """Test that parser extracts tasks."""
        from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
        
        parser = SSISParser()
        result = parser.parse(MINIMAL_SSIS_PACKAGE)
        
        assert len(result.tasks) >= 1
        load_task = next((t for t in result.tasks if t.name == "Load Data"), None)
        assert load_task is not None
        assert load_task.description == "Load data from source to target"

    def test_parse_invalid_xml_raises_error(self):
        """Test that parser raises error on invalid XML."""
        from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
        from app.modules.migration_workbench.analysis.parsers.base import ParseError
        
        parser = SSISParser()
        with pytest.raises(ParseError):
            parser.parse("<broken>xml")

    def test_extract_metadata(self):
        """Test metadata extraction without full parsing."""
        from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
        
        parser = SSISParser()
        metadata = parser.extract_metadata(MINIMAL_SSIS_PACKAGE)
        
        assert metadata["name"] == "TestPackage"
        assert metadata["description"] == "A test SSIS package"


class TestParserRegistry:
    """Tests for the parser registry."""

    def test_get_parser_ssis(self):
        """Test getting SSIS parser."""
        from app.modules.migration_workbench.analysis.parsers import get_parser
        from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
        
        parser = get_parser("ssis")
        assert isinstance(parser, SSISParser)

    def test_get_parser_unknown(self):
        """Test getting unknown parser raises error."""
        from app.modules.migration_workbench.analysis.parsers import get_parser
        
        with pytest.raises(ValueError, match="No parser available"):
            get_parser("unknown_tech")


# =============================================================================
# Unit Tests - Schemas
# =============================================================================


class TestSchemas:
    """Tests for Pydantic schemas."""

    def test_connection_manager_schema(self):
        """Test ConnectionManager schema."""
        from app.modules.migration_workbench.analysis.schemas import ConnectionManager
        
        cm = ConnectionManager(
            name="TestConn",
            connection_type="OLEDB",
            server="SERVER1",
            database="TestDB",
        )
        assert cm.name == "TestConn"
        assert cm.connection_type == "OLEDB"

    def test_ssis_package_schema(self):
        """Test SSISPackage schema."""
        from app.modules.migration_workbench.analysis.schemas import SSISPackage
        
        pkg = SSISPackage(
            name="TestPackage",
            connection_managers=[],
            tasks=[],
            precedence_constraints=[],
            data_flows=[],
            variables=[],
            parameters=[],
            annotations=[],
            disabled_tasks=[],
            parse_warnings=[],
        )
        assert pkg.name == "TestPackage"


# =============================================================================
# Integration Tests - API Endpoints
# =============================================================================


def _skip_if_no_db() -> None:
    if not os.environ.get("WORKSHOP_RUN_INTEGRATION"):
        pytest.skip("set WORKSHOP_RUN_INTEGRATION=1 to enable; requires docker compose up")


async def _hit(method: str, path: str, **kwargs):
    from app.main import create_app
    from httpx import ASGITransport, AsyncClient
    
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.integration
async def test_migration_health_endpoint():
    """Test the migration workbench health endpoint."""
    _skip_if_no_db()
    r = await _hit("GET", "/api/migrations/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["module"] == "migration_workbench"


@pytest.mark.integration
async def test_profiles_list():
    """Test listing technology profiles."""
    _skip_if_no_db()
    r = await _hit("GET", "/api/migrations/profiles")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


# =============================================================================
# Unit Tests - Migration Map Schemas
# =============================================================================


class TestMapSchemas:
    """Unit tests for map schemas."""

    def test_object_type_enum(self):
        """Test ObjectType enum values."""
        from app.modules.migration_workbench.map.schemas import ObjectType
        
        assert ObjectType.TABLE.value == "table"
        assert ObjectType.FILE.value == "file"
        assert ObjectType.API.value == "api"

    def test_object_direction_enum(self):
        """Test ObjectDirection enum values."""
        from app.modules.migration_workbench.map.schemas import ObjectDirection
        
        assert ObjectDirection.READ.value == "read"
        assert ObjectDirection.WRITE.value == "write"
        assert ObjectDirection.LOOKUP.value == "lookup"

    def test_object_create_schema(self):
        """Test ObjectCreate schema."""
        from app.modules.migration_workbench.map.schemas import ObjectCreate, ObjectType
        
        obj = ObjectCreate(
            object_type=ObjectType.TABLE,
            object_name="customers",
            schema_name="dbo",
            connection_ref="SourceDB",
        )
        
        assert obj.object_type == ObjectType.TABLE
        assert obj.object_name == "customers"
        assert obj.schema_name == "dbo"

    def test_map_node_schema(self):
        """Test MapNode schema for React Flow."""
        from app.modules.migration_workbench.map.schemas import MapNode
        
        node = MapNode(
            id="pkg-123",
            type="package",
            position={"x": 100, "y": 200},
            data={
                "label": "ETL Package 1",
                "status": "analyzed",
                "wave": 1,
                "blockers": 2,
            },
        )
        
        assert node.id == "pkg-123"
        assert node.type == "package"
        assert node.data["label"] == "ETL Package 1"
        assert node.data["wave"] == 1

    def test_map_edge_schema(self):
        """Test MapEdge schema for React Flow."""
        from app.modules.migration_workbench.map.schemas import MapEdge
        
        edge = MapEdge(
            id="edge-1-2",
            source="pkg-1",
            target="pkg-2",
            label="customers",
        )
        
        assert edge.source == "pkg-1"
        assert edge.target == "pkg-2"

    def test_wave_suggestion_schema(self):
        """Test WaveSuggestion schema."""
        from app.modules.migration_workbench.map.schemas import WaveSuggestion
        import uuid
        
        pkg_id = uuid.uuid4()
        suggestion = WaveSuggestion(
            package_id=pkg_id,
            package_name="Package 1",
            current_wave=None,
            suggested_wave=1,
            reason="No upstream dependencies",
        )
        
        assert suggestion.package_id == pkg_id
        assert suggestion.suggested_wave == 1


# =============================================================================
# Integration Tests - Migration Map API
# =============================================================================


@pytest.mark.integration
async def test_map_visualization_empty():
    """Test map visualization endpoint with no data."""
    _skip_if_no_db()
    # Use a random project ID that won't exist
    r = await _hit("GET", "/api/migrations/00000000-0000-0000-0000-000000000000/map")
    # Should return empty map structure, not 404
    assert r.status_code in [200, 404]


@pytest.mark.integration
async def test_map_objects_list():
    """Test listing objects in migration map."""
    _skip_if_no_db()
    r = await _hit("GET", "/api/migrations/00000000-0000-0000-0000-000000000000/map/objects")
    assert r.status_code in [200, 404]


@pytest.mark.integration
async def test_map_clusters_list():
    """Test listing clusters in migration map."""
    _skip_if_no_db()
    r = await _hit("GET", "/api/migrations/00000000-0000-0000-0000-000000000000/map/clusters")
    assert r.status_code in [200, 404]


@pytest.mark.integration
async def test_map_dependencies_list():
    """Test listing dependencies in migration map."""
    _skip_if_no_db()
    r = await _hit("GET", "/api/migrations/00000000-0000-0000-0000-000000000000/map/deps")
    assert r.status_code in [200, 404]


@pytest.mark.integration
async def test_map_wave_suggestions():
    """Test wave suggestion endpoint."""
    _skip_if_no_db()
    r = await _hit("POST", "/api/migrations/00000000-0000-0000-0000-000000000000/map/waves/suggest")
    assert r.status_code in [200, 404]


# =============================================================================
# Unit Tests - Databricks Generator
# =============================================================================


class TestDatabricksGenerator:
    """Unit tests for the modular Databricks notebook generator."""

    def _make_package(self, name="TestPackage.dtsx", tasks=None):
        from app.modules.migration_workbench.analysis.schemas import SSISPackage
        
        return SSISPackage(name=name, tasks=tasks or [])

    def _sql_task(self, name, sql):
        from app.modules.migration_workbench.analysis.schemas import Task, TaskType
        
        return Task(name=name, task_type=TaskType.EXECUTE_SQL, sql_statement=sql)

    def test_modular_strategy_produces_orchestrator_plus_sql_modules(self):
        """MODULAR strategy: emit orchestrator + grouped SQL modules + README."""
        import uuid as _uuid
        from app.modules.migration_workbench.generation.generators.databricks import (
            DatabricksGenerator,
        )
        from app.modules.migration_workbench.generation.schemas import ArtifactTier
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            GenerationStrategy,
        )
        
        package = self._make_package(
            tasks=[
                self._sql_task("extract", "INSERT INTO stg SELECT * FROM src"),
                self._sql_task("transform", "INSERT INTO clean SELECT * FROM stg"),
                self._sql_task("merge", "MERGE INTO dim USING clean ON 1=1"),
                self._sql_task("cleanup", "TRUNCATE TABLE stg"),
            ]
        )
        
        result = DatabricksGenerator().generate(package, package_id=_uuid.uuid4())
        
        assert result.strategy == GenerationStrategy.MODULAR
        tiers = [a.tier for a in result.artifacts]
        assert ArtifactTier.ORCHESTRATOR in tiers
        assert ArtifactTier.SQL_MODULE in tiers
        assert ArtifactTier.DOCUMENTATION in tiers  # README
        # At least: orchestrator + 1 SQL module + README
        assert len(result.artifacts) >= 3

    def test_orchestrator_references_each_sql_module(self):
        """Orchestrator notebook calls dbutils.notebook.run for each module."""
        import uuid as _uuid
        from app.modules.migration_workbench.generation.generators.databricks import (
            DatabricksGenerator,
        )
        from app.modules.migration_workbench.generation.schemas import ArtifactTier
        
        package = self._make_package(
            tasks=[
                self._sql_task("a", "INSERT INTO x VALUES (1)"),
                self._sql_task("b", "MERGE INTO y USING x ON 1=1"),
                self._sql_task("c", "TRUNCATE TABLE x"),
            ]
        )
        
        result = DatabricksGenerator().generate(package, package_id=_uuid.uuid4())
        
        orch = next(a for a in result.artifacts if a.tier == ArtifactTier.ORCHESTRATOR)
        sql_modules = [a for a in result.artifacts if a.tier == ArtifactTier.SQL_MODULE]
        
        assert "dbutils.notebook.run" in orch.content
        # Each SQL module name must appear in the orchestrator's modules list
        for mod in sql_modules:
            mod_basename = mod.name.replace(".sql", "")
            assert mod_basename in orch.content

    def test_sql_module_contains_databricks_notebook_header(self):
        """SQL modules must be valid Databricks notebook format."""
        import uuid as _uuid
        from app.modules.migration_workbench.generation.generators.databricks import (
            DatabricksGenerator,
        )
        from app.modules.migration_workbench.generation.schemas import ArtifactTier
        
        package = self._make_package(
            tasks=[
                self._sql_task("a", "SELECT * FROM t"),
                self._sql_task("b", "SELECT * FROM u"),
                self._sql_task("c", "MERGE INTO d USING s ON 1=1"),
            ]
        )
        
        result = DatabricksGenerator().generate(package, package_id=_uuid.uuid4())
        
        for art in result.artifacts:
            if art.tier == ArtifactTier.SQL_MODULE:
                assert art.content.startswith("-- Databricks notebook source")
                assert "-- COMMAND ----------" in art.content
                assert art.language == "sql"

    def test_pyspark_strategy_for_script_task(self):
        """Script Task triggers PYSPARK strategy producing one .py notebook."""
        import uuid as _uuid
        from app.modules.migration_workbench.analysis.schemas import Task, TaskType
        from app.modules.migration_workbench.generation.generators.databricks import (
            DatabricksGenerator,
        )
        from app.modules.migration_workbench.generation.schemas import ArtifactTier
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            GenerationStrategy,
        )
        
        package = self._make_package(
            tasks=[
                Task(name="script1", task_type=TaskType.SCRIPT),
                self._sql_task("q", "SELECT 1"),
            ]
        )
        
        result = DatabricksGenerator().generate(package, package_id=_uuid.uuid4())
        
        assert result.strategy == GenerationStrategy.PYSPARK
        pyspark = [a for a in result.artifacts if a.tier == ArtifactTier.PYSPARK_MODULE]
        assert len(pyspark) == 1
        assert pyspark[0].content.startswith("# Databricks notebook source")
        assert pyspark[0].language == "python"

    def test_single_sql_notebook_for_small_pure_sql(self):
        """Few SQL tasks → single SQL notebook (not modular)."""
        import uuid as _uuid
        from app.modules.migration_workbench.generation.generators.databricks import (
            DatabricksGenerator,
        )
        from app.modules.migration_workbench.generation.schemas import ArtifactTier
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            GenerationStrategy,
        )
        
        package = self._make_package(
            tasks=[
                self._sql_task("a", "SELECT 1"),
                self._sql_task("b", "SELECT 2"),
            ]
        )
        
        result = DatabricksGenerator().generate(package, package_id=_uuid.uuid4())
        
        assert result.strategy == GenerationStrategy.SQL_NOTEBOOK
        sql = [a for a in result.artifacts if a.tier == ArtifactTier.SQL_MODULE]
        assert len(sql) == 1
        # Single SQL notebook, no orchestrator
        orch = [a for a in result.artifacts if a.tier == ArtifactTier.ORCHESTRATOR]
        assert len(orch) == 0

    def test_force_strategy_overrides_classifier(self):
        """force_strategy in options overrides backward analysis."""
        import uuid as _uuid
        from app.modules.migration_workbench.generation.generators.databricks import (
            DatabricksGenerator,
        )
        from app.modules.migration_workbench.generation.schemas import GenerationOptions
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            GenerationStrategy,
        )
        
        # Two SQL tasks would classify as SQL_NOTEBOOK; force PYSPARK
        package = self._make_package(
            tasks=[self._sql_task("a", "SELECT 1"), self._sql_task("b", "SELECT 2")]
        )
        options = GenerationOptions(force_strategy=GenerationStrategy.PYSPARK)
        
        result = DatabricksGenerator().generate(
            package, package_id=_uuid.uuid4(), options=options
        )
        
        assert result.strategy == GenerationStrategy.PYSPARK
        assert result.strategy_source == "user_override"

    def test_readme_always_included(self):
        """Every result includes a README documentation artifact."""
        import uuid as _uuid
        from app.modules.migration_workbench.generation.generators.databricks import (
            DatabricksGenerator,
        )
        from app.modules.migration_workbench.generation.schemas import ArtifactTier
        
        package = self._make_package(tasks=[self._sql_task("only", "SELECT 1")])
        result = DatabricksGenerator().generate(package, package_id=_uuid.uuid4())
        
        readmes = [a for a in result.artifacts if a.tier == ArtifactTier.DOCUMENTATION]
        assert len(readmes) == 1
        assert readmes[0].name == "README.md"
        assert package.name in readmes[0].content


# =============================================================================
# Unit Tests - Strategy Classifier (Backward Analysis)
# =============================================================================


class TestStrategyClassifier:
    """Unit tests for backward-analysis generation strategy classifier."""

    def _make_package(self, tasks=None, data_flows=None, variables=None):
        from app.modules.migration_workbench.analysis.schemas import SSISPackage
        
        return SSISPackage(
            name="TestPackage.dtsx",
            tasks=tasks or [],
            data_flows=data_flows or [],
            variables=variables or [],
        )

    def _sql_task(self, name="sql1", sql="SELECT 1"):
        from app.modules.migration_workbench.analysis.schemas import Task, TaskType
        
        return Task(name=name, task_type=TaskType.EXECUTE_SQL, sql_statement=sql)

    def test_script_task_forces_pyspark(self):
        """Script Tasks require PySpark for custom Python logic."""
        from app.modules.migration_workbench.analysis.schemas import Task, TaskType
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            GenerationStrategy,
            StrategyClassifier,
        )
        
        package = self._make_package(
            tasks=[
                Task(name="script1", task_type=TaskType.SCRIPT),
                self._sql_task(),
            ]
        )
        
        plan = StrategyClassifier().classify(package)
        
        assert plan.strategy == GenerationStrategy.PYSPARK
        assert plan.has_script_components is True
        assert "Script" in plan.rationale

    def test_high_sql_ratio_with_many_tasks_chooses_modular(self):
        """80%+ SQL with 3+ SQL tasks → modular SQL notebooks."""
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            GenerationStrategy,
            StrategyClassifier,
        )
        
        package = self._make_package(
            tasks=[
                self._sql_task("extract", "SELECT * INTO #tmp FROM src"),
                self._sql_task("transform", "INSERT INTO stg SELECT * FROM #tmp"),
                self._sql_task("merge", "MERGE INTO dim USING stg ON ..."),
                self._sql_task("cleanup", "TRUNCATE TABLE #tmp"),
            ]
        )
        
        plan = StrategyClassifier().classify(package)
        
        assert plan.strategy == GenerationStrategy.MODULAR
        assert plan.photon_eligible is True
        # Orchestrator + grouped SQL modules
        assert len(plan.modules) >= 2
        assert plan.modules[0].notebook_type == "orchestrator"
        assert any(m.notebook_type == "sql_module" for m in plan.modules)

    def test_high_sql_ratio_with_few_tasks_chooses_single_sql(self):
        """High SQL ratio but few tasks → single SQL notebook."""
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            GenerationStrategy,
            StrategyClassifier,
        )
        
        package = self._make_package(
            tasks=[self._sql_task("one", "SELECT 1"), self._sql_task("two", "SELECT 2")]
        )
        
        plan = StrategyClassifier().classify(package)
        
        assert plan.strategy == GenerationStrategy.SQL_NOTEBOOK
        assert plan.photon_eligible is True
        assert len(plan.modules) == 1

    def test_foreach_with_sql_chooses_modular(self):
        """Foreach Loop + multiple SQL tasks → modular structure."""
        from app.modules.migration_workbench.analysis.schemas import Task, TaskType
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            GenerationStrategy,
            StrategyClassifier,
        )
        
        package = self._make_package(
            tasks=[
                Task(name="loop", task_type=TaskType.FOREACH_LOOP),
                self._sql_task("s1"),
                self._sql_task("s2"),
                self._sql_task("s3"),
            ]
        )
        
        plan = StrategyClassifier().classify(package)
        
        assert plan.strategy == GenerationStrategy.MODULAR
        assert plan.has_foreach_loops is True

    def test_datediff_join_sets_range_join_hint(self):
        """DATEDIFF in SQL signals need for range-join optimization."""
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            StrategyClassifier,
        )
        
        package = self._make_package(
            tasks=[
                self._sql_task("j", "SELECT * FROM a JOIN b ON DATEDIFF(day,a.d,b.d)<5"),
            ]
        )
        
        plan = StrategyClassifier().classify(package)
        
        assert plan.requires_range_joins is True
        assert any("range" in n.lower() for n in plan.notes)

    def test_modular_grouping_orders_phases(self):
        """SQL modules should be ordered extract → transform → merge → cleanup."""
        from app.modules.migration_workbench.analysis.strategy_classifier import (
            StrategyClassifier,
        )
        
        package = self._make_package(
            tasks=[
                self._sql_task("clean", "TRUNCATE TABLE x"),
                self._sql_task("merge", "MERGE INTO t USING s ON 1=1"),
                self._sql_task("extract", "INSERT INTO stg VALUES (1)"),
            ]
        )
        
        plan = StrategyClassifier().classify(package)
        
        # Skip orchestrator (index 0), check order of sql modules
        sql_modules = [m for m in plan.modules if m.notebook_type == "sql_module"]
        purposes = [m.name.split("_", 2)[-1] for m in sql_modules]
        # extract should come before merge, merge before cleanup
        assert purposes.index("extract") < purposes.index("merge")
        assert purposes.index("merge") < purposes.index("cleanup")


# =============================================================================
# Unit Tests - Propagation Schemas
# =============================================================================


class TestPropagationSchemas:
    """Unit tests for propagation schemas."""

    def test_propagation_scope_enum(self):
        """Test PropagationScope enum values."""
        from app.modules.migration_workbench.propagation.schemas import PropagationScope
        
        assert PropagationScope.PROJECT.value == "project"
        assert PropagationScope.CLUSTER.value == "cluster"
        assert PropagationScope.DOMAIN.value == "domain"
        assert PropagationScope.SIMILAR.value == "similar"

    def test_propagation_result_schema(self):
        """Test PropagationResult schema."""
        from app.modules.migration_workbench.propagation.schemas import PropagationResult
        from datetime import datetime, timezone
        import uuid
        
        result = PropagationResult(
            source_decision_id=uuid.uuid4(),
            decision_type="incremental_strategy",
            packages_affected=5,
            packages_already_resolved=2,
            affected_package_ids=[uuid.uuid4() for _ in range(5)],
            errors=[],
            propagated_at=datetime.now(timezone.utc),
        )
        
        assert result.packages_affected == 5
        assert result.packages_already_resolved == 2
        assert len(result.affected_package_ids) == 5

    def test_propagation_preview_schema(self):
        """Test PropagationPreview schema."""
        from app.modules.migration_workbench.propagation.schemas import (
            PropagationPreview,
            PropagationScope,
        )
        import uuid
        
        preview = PropagationPreview(
            decision_id=uuid.uuid4(),
            decision_type="incremental_strategy",
            question="How should incremental loads be handled?",
            resolution="Use MERGE pattern with date column",
            scope=PropagationScope.PROJECT,
            would_affect_count=10,
            already_resolved_count=3,
            affected_packages=[
                {"id": str(uuid.uuid4()), "name": "Package1", "domain": "logistics"},
            ],
        )
        
        assert preview.would_affect_count == 10
        assert preview.already_resolved_count == 3
        assert len(preview.affected_packages) == 1

    def test_batch_wave_assignment_schema(self):
        """Test BatchWaveAssignment schema."""
        from app.modules.migration_workbench.propagation.schemas import BatchWaveAssignment
        import uuid
        
        batch = BatchWaveAssignment(
            assignments=[
                {"package_id": str(uuid.uuid4()), "wave": 1},
                {"package_id": str(uuid.uuid4()), "wave": 2},
            ]
        )
        
        assert len(batch.assignments) == 2

    def test_batch_wave_result_schema(self):
        """Test BatchWaveResult schema."""
        from app.modules.migration_workbench.propagation.schemas import BatchWaveResult
        import uuid
        
        result = BatchWaveResult(
            successful=8,
            failed=2,
            errors=["Package X not found"],
            assigned_packages=[uuid.uuid4() for _ in range(8)],
        )
        
        assert result.successful == 8
        assert result.failed == 2
        assert len(result.errors) == 1


# =============================================================================
# Integration Tests - Propagation API
# =============================================================================


@pytest.mark.integration
async def test_propagation_preview_not_found():
    """Test propagation preview with non-existent decision."""
    _skip_if_no_db()
    r = await _hit(
        "GET",
        "/api/migrations/00000000-0000-0000-0000-000000000000/propagation/decisions/00000000-0000-0000-0000-000000000001/preview"
    )
    assert r.status_code in [404]


@pytest.mark.integration
async def test_batch_wave_assignment():
    """Test batch wave assignment endpoint."""
    _skip_if_no_db()
    r = await _hit(
        "POST",
        "/api/migrations/00000000-0000-0000-0000-000000000000/propagation/waves/batch",
        json={"assignments": []}
    )
    assert r.status_code in [200, 404]


# =============================================================================
# Unit Tests - Data Pattern Classifier (Phase 7)
# =============================================================================


class TestDataPatternClassifier:
    """Unit tests for data pattern detection and classification."""

    def _sql_task(self, name="task1", sql="SELECT 1"):
        from app.modules.migration_workbench.analysis.schemas import Task, TaskType
        return Task(name=name, task_type=TaskType.EXECUTE_SQL, sql_statement=sql)

    def _script_task(self, name="script1"):
        from app.modules.migration_workbench.analysis.schemas import Task, TaskType
        return Task(name=name, task_type=TaskType.SCRIPT)

    def test_detects_merge_pattern(self):
        """MERGE INTO should be detected as MERGE pattern."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
            DataPattern,
        )
        
        task = self._sql_task("load_dim", "MERGE INTO dim_customer USING stg ON 1=1")
        classifier = DataPatternClassifier()
        result = classifier.classify_task(task)
        
        assert result.pattern == DataPattern.MERGE
        assert "MERGE" in result.detection_evidence[0]

    def test_detects_scd_type_2(self):
        """SCD Type 2 columns should trigger SCD2 pattern."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
            DataPattern,
        )
        
        task = self._sql_task(
            "scd2_history",
            "UPDATE dim SET end_date = GETDATE(), is_current = 0 WHERE key = @key"
        )
        classifier = DataPatternClassifier()
        result = classifier.classify_task(task)
        
        assert result.pattern == DataPattern.SCD_TYPE_2

    def test_detects_append_only(self):
        """INSERT without UPDATE/DELETE should be APPEND_ONLY."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
            DataPattern,
        )
        
        task = self._sql_task("append_log", "INSERT INTO audit_log SELECT * FROM events")
        classifier = DataPatternClassifier()
        result = classifier.classify_task(task)
        
        assert result.pattern == DataPattern.APPEND_ONLY

    def test_detects_aggregate(self):
        """SUM/COUNT with GROUP BY should be AGGREGATE pattern."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
            DataPattern,
        )
        
        task = self._sql_task(
            "agg_sales",
            "SELECT product_id, SUM(amount) FROM sales GROUP BY product_id"
        )
        classifier = DataPatternClassifier()
        result = classifier.classify_task(task)
        
        assert result.pattern == DataPattern.AGGREGATE

    def test_detects_cdc_pattern(self):
        """CDC markers like __$operation should trigger CDC pattern."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
            DataPattern,
        )
        
        task = self._sql_task(
            "process_cdc",
            "SELECT * FROM cdc.changes WHERE __$operation IN (1, 2, 4)"
        )
        classifier = DataPatternClassifier()
        result = classifier.classify_task(task)
        
        assert result.pattern == DataPattern.CDC

    def test_detects_watermark_pattern(self):
        """High-water mark incremental pattern detection."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
            DataPattern,
        )
        
        task = self._sql_task(
            "incremental_load",
            "SELECT * FROM orders WHERE modified_date > @last_run_date"
        )
        classifier = DataPatternClassifier()
        result = classifier.classify_task(task)
        
        assert result.pattern == DataPattern.WATERMARK

    def test_detects_medallion_layer_bronze(self):
        """Bronze layer detection from task name hints."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
            MedallionLayer,
        )
        
        task = self._sql_task("bronze_ingest_orders", "INSERT INTO bronze.orders SELECT *")
        classifier = DataPatternClassifier()
        result = classifier.classify_task(task)
        
        assert result.layer == MedallionLayer.BRONZE

    def test_detects_medallion_layer_gold(self):
        """Gold layer detection for aggregates and dimensions."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
            MedallionLayer,
        )
        
        task = self._sql_task(
            "gold_dim_customer",
            "MERGE INTO gold.dim_customer USING silver.customers"
        )
        classifier = DataPatternClassifier()
        result = classifier.classify_task(task)
        
        assert result.layer == MedallionLayer.GOLD

    def test_extracts_target_table(self):
        """Target table extraction from SQL."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
        )
        
        task = self._sql_task("load", "INSERT INTO dbo.customers SELECT * FROM src")
        classifier = DataPatternClassifier()
        result = classifier.classify_task(task)
        
        assert result.target_table == "dbo.customers"

    def test_analyze_package_photon_eligibility(self):
        """Package analysis checks for Photon eligibility."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
        )
        
        tasks = [
            self._sql_task("t1", "SELECT 1"),
            self._script_task("script1"),  # Script breaks Photon
        ]
        
        classifier = DataPatternClassifier()
        analysis = classifier.analyze_package("TestPkg", tasks)
        
        assert analysis.photon_eligible is False
        assert any("Photon" in n for n in analysis.performance_notes)

    def test_analyze_package_pattern_summary(self):
        """Package analysis produces pattern summary counts."""
        from app.modules.migration_workbench.analysis.data_pattern_classifier import (
            DataPatternClassifier,
        )
        
        tasks = [
            self._sql_task("merge1", "MERGE INTO t1 USING s1"),
            self._sql_task("merge2", "MERGE INTO t2 USING s2"),
            self._sql_task("agg", "SELECT SUM(x) FROM t GROUP BY y"),
        ]
        
        classifier = DataPatternClassifier()
        analysis = classifier.analyze_package("TestPkg", tasks)
        
        assert analysis.pattern_summary.get("merge", 0) == 2
        assert analysis.pattern_summary.get("aggregate", 0) == 1


# =============================================================================
# Unit Tests - Skill Loader (Phase 7)
# =============================================================================


class TestSkillLoader:
    """Unit tests for pre-built skill loading."""

    def test_list_skills_finds_builtin_skills(self):
        """SkillLoader finds the 4 built-in skills."""
        from app.modules.migration_workbench.skills.skill_loader import SkillLoader
        
        loader = SkillLoader()
        skills = loader.list_skills()
        
        # Should find at least 4 skills
        assert len(skills) >= 4
        skill_ids = {s.id for s in skills}
        assert "business-rules-compliance-analyzer" in skill_ids
        assert "disabled-task-auditor" in skill_ids
        assert "etl-migration-reconciler" in skill_ids
        assert "change-history-risk-analyzer" in skill_ids

    def test_get_skill_returns_detail(self):
        """SkillLoader returns skill content by ID."""
        from app.modules.migration_workbench.skills.skill_loader import SkillLoader
        
        loader = SkillLoader()
        skill = loader.get_skill("business-rules-compliance-analyzer")
        
        assert skill is not None
        assert skill.id == "business-rules-compliance-analyzer"
        assert skill.name == "Business Rules Compliance Analyzer"
        assert "business rule" in skill.description.lower()
        assert skill.content.startswith("# Business Rules")

    def test_get_skill_not_found_returns_none(self):
        """SkillLoader returns None for non-existent skill."""
        from app.modules.migration_workbench.skills.skill_loader import SkillLoader
        
        loader = SkillLoader()
        skill = loader.get_skill("nonexistent-skill-12345")
        
        assert skill is None

    def test_skill_parses_when_to_use(self):
        """Skill parser extracts 'When to Use' section."""
        from app.modules.migration_workbench.skills.skill_loader import SkillLoader
        
        loader = SkillLoader()
        skill = loader.get_skill("etl-migration-reconciler")
        
        assert skill is not None
        assert skill.when_to_use  # Should have content
        assert "validat" in skill.when_to_use.lower()

    def test_skill_parses_capabilities(self):
        """Skill parser extracts capability list items."""
        from app.modules.migration_workbench.skills.skill_loader import SkillLoader
        
        loader = SkillLoader()
        skill = loader.get_skill("disabled-task-auditor")
        
        assert skill is not None
        assert len(skill.capabilities) > 0
