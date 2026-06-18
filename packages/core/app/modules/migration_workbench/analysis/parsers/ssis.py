"""SSIS .dtsx package parser.

Parses SQL Server Integration Services packages (XML format) into
structured objects for analysis.

B3c Enhancement: Added parsing for:
- Variable/Parameter data_type (DTS:DataType attribute)
- Transform expressions (Derived Column, Conditional Split)
- Data flow paths (component wiring topology)
- Unparsed features tracking (Script Tasks, Event Handlers)
"""

from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from typing import Any

from app.modules.migration_workbench.analysis.parsers.base import ParserInterface, ParseError
from app.modules.migration_workbench.analysis.schemas import (
    Annotation,
    Column,
    ColumnMapping,
    ConnectionManager,
    DataFlow,
    DataFlowPath,
    Destination,
    Parameter,
    PrecedenceConstraint,
    Source,
    SSISPackage,
    Task,
    TaskType,
    Transform,
    UnparsedFeature,
    Variable,
)


class SSISParser(ParserInterface):
    """Parser for SSIS .dtsx packages.
    
    SSIS packages are XML files with a complex namespace structure.
    This parser extracts connection managers, control flow, data flows,
    variables, and annotations.
    """
    
    # SSIS XML namespaces
    NAMESPACES = {
        "DTS": "www.microsoft.com/SqlServer/Dts",
        "SQLTask": "www.microsoft.com/sqlserver/dts/tasks/sqltask",
    }
    
    # DTS prefix for attributes
    DTS_PREFIX = "{www.microsoft.com/SqlServer/Dts}"
    
    @property
    def technology(self) -> str:
        return "ssis"
    
    @property
    def file_extension(self) -> str:
        return ".dtsx"
    
    def can_parse(self, content: str) -> bool:
        """Check if content is an SSIS package."""
        return (
            "www.microsoft.com/SqlServer/Dts" in content
            and "<DTS:Executable" in content
        )
    
    def parse(self, content: str) -> SSISPackage:
        """Parse SSIS .dtsx XML content.
        
        Args:
            content: Raw XML content of the .dtsx file
            
        Returns:
            Parsed SSISPackage structure
        """
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise ParseError(f"Invalid XML: {e}")
        
        warnings: list[str] = []
        unparsed_features: list[UnparsedFeature] = []
        
        # Generate package_id (B3c: required by ParsedPackage base)
        package_id = str(uuid.uuid4())
        
        # Extract package metadata
        name = self._get_dts_attr(root, "ObjectName") or "Unknown"
        description = self._get_dts_attr(root, "Description")
        creation_date = self._get_dts_attr(root, "CreationDate")
        creator_name = self._get_dts_attr(root, "CreatorName")
        
        # Parse components
        connection_managers = self._parse_connection_managers(root, warnings)
        variables = self._parse_variables(root, warnings)
        parameters = self._parse_parameters(root, warnings)
        tasks, disabled_tasks = self._parse_tasks(root, warnings)
        precedence_constraints = self._parse_precedence_constraints(root, warnings)
        annotations = self._parse_annotations(root, warnings)
        
        # Extract data flows from Data Flow Tasks
        data_flows = []
        for task in tasks:
            if task.task_type == TaskType.DATA_FLOW and task.data_flow:
                data_flows.append(task.data_flow)
        
        # B3c: Track unparsed features for LLM awareness
        self._collect_unparsed_features(root, tasks, unparsed_features)
        
        return SSISPackage(
            package_id=package_id,
            name=name,
            description=description,
            creation_date=creation_date,
            creator_name=creator_name,
            connection_managers=connection_managers,
            tasks=tasks,
            precedence_constraints=precedence_constraints,
            data_flows=data_flows,
            variables=variables,
            parameters=parameters,
            annotations=annotations,
            disabled_tasks=disabled_tasks,
            parse_warnings=warnings,
            unparsed_features=unparsed_features,
        )
    
    def extract_metadata(self, content: str) -> dict[str, Any]:
        """Extract basic metadata without full parsing."""
        try:
            root = ET.fromstring(content)
            return {
                "name": self._get_dts_attr(root, "ObjectName"),
                "description": self._get_dts_attr(root, "Description"),
                "creation_date": self._get_dts_attr(root, "CreationDate"),
                "creator_name": self._get_dts_attr(root, "CreatorName"),
            }
        except ET.ParseError:
            return {}
    
    # -------------------------------------------------------------------------
    # Connection Managers
    # -------------------------------------------------------------------------
    
    def _parse_connection_managers(
        self, root: ET.Element, warnings: list[str]
    ) -> list[ConnectionManager]:
        """Parse connection manager definitions."""
        managers = []
        
        # Find ConnectionManagers element
        cm_parent = root.find(f".//{self.DTS_PREFIX}ConnectionManagers")
        if cm_parent is None:
            return managers
        
        for cm in cm_parent.findall(f"{self.DTS_PREFIX}ConnectionManager"):
            try:
                manager = self._parse_connection_manager(cm)
                managers.append(manager)
            except Exception as e:
                name = self._get_dts_attr(cm, "ObjectName") or "unknown"
                warnings.append(f"Failed to parse connection manager '{name}': {e}")
        
        return managers
    
    def _parse_connection_manager(self, elem: ET.Element) -> ConnectionManager:
        """Parse a single connection manager."""
        name = self._get_dts_attr(elem, "ObjectName") or ""
        creation_name = self._get_dts_attr(elem, "CreationName") or ""
        
        # Determine connection type from CreationName
        conn_type = self._infer_connection_type(creation_name)
        
        # Get connection string from ObjectData
        conn_string = None
        server = None
        database = None
        provider = None
        is_expression = False
        
        # Check for property expression (connection string from variable)
        prop_expr = elem.find(f".//{self.DTS_PREFIX}PropertyExpression")
        if prop_expr is not None and "ConnectionString" in (prop_expr.get("Name") or ""):
            is_expression = True
            conn_string = prop_expr.text
        
        # Parse ObjectData for connection details
        object_data = elem.find(f"{self.DTS_PREFIX}ObjectData")
        if object_data is not None:
            # For OLEDB/ADO.NET connections
            conn_mgr_data = object_data.find("ConnectionManager")
            if conn_mgr_data is not None:
                conn_string = conn_string or conn_mgr_data.get("ConnectionString")
            
            # For file connections
            file_conn = object_data.find("FileConnectionManagerData")
            if file_conn is not None:
                conn_string = file_conn.get("ConnectionString")
        
        # Extract server/database from connection string
        if conn_string and not is_expression:
            server, database, provider = self._parse_connection_string(conn_string)
        
        return ConnectionManager(
            name=name,
            object_name=name,
            connection_type=conn_type,
            connection_string=conn_string,
            server=server,
            database=database,
            provider=provider,
            is_expression_based=is_expression,
        )
    
    def _infer_connection_type(self, creation_name: str) -> str:
        """Infer connection type from SSIS CreationName."""
        creation_name = creation_name.upper()
        
        if "OLEDB" in creation_name:
            return "OLEDB"
        elif "ADO.NET" in creation_name or "ADONET" in creation_name:
            return "ADO.NET"
        elif "FLATFILE" in creation_name or "FLAT FILE" in creation_name:
            return "FLATFILE"
        elif "EXCEL" in creation_name:
            return "EXCEL"
        elif "FTP" in creation_name:
            return "FTP"
        elif "HTTP" in creation_name:
            return "HTTP"
        elif "SMTP" in creation_name:
            return "SMTP"
        elif "FILE" in creation_name:
            return "FILE"
        else:
            return creation_name or "UNKNOWN"
    
    def _parse_connection_string(self, conn_string: str) -> tuple[str | None, str | None, str | None]:
        """Extract server, database, and provider from connection string."""
        server = None
        database = None
        provider = None
        
        # Common patterns
        patterns = {
            "server": [
                r"Data Source=([^;]+)",
                r"Server=([^;]+)",
                r"HOST=([^;]+)",
            ],
            "database": [
                r"Initial Catalog=([^;]+)",
                r"Database=([^;]+)",
            ],
            "provider": [
                r"Provider=([^;]+)",
            ],
        }
        
        for pattern in patterns["server"]:
            match = re.search(pattern, conn_string, re.IGNORECASE)
            if match:
                server = match.group(1).strip()
                break
        
        for pattern in patterns["database"]:
            match = re.search(pattern, conn_string, re.IGNORECASE)
            if match:
                database = match.group(1).strip()
                break
        
        for pattern in patterns["provider"]:
            match = re.search(pattern, conn_string, re.IGNORECASE)
            if match:
                provider = match.group(1).strip()
                break
        
        return server, database, provider
    
    # -------------------------------------------------------------------------
    # Variables & Parameters
    # -------------------------------------------------------------------------
    
    def _parse_variables(self, root: ET.Element, warnings: list[str]) -> list[Variable]:
        """Parse package variables."""
        variables = []
        
        for var in root.findall(f".//{self.DTS_PREFIX}Variable"):
            try:
                name = self._get_dts_attr(var, "ObjectName") or ""
                namespace = self._get_dts_attr(var, "Namespace") or "User"
                
                # B3c: Extract data type from DTS:DataType attribute
                data_type = self._get_dts_attr(var, "DataType")
                data_type = self._map_ssis_data_type(data_type) if data_type else None
                
                # Get variable value
                var_value = var.find(f"{self.DTS_PREFIX}VariableValue")
                value = var_value.text if var_value is not None else None
                
                # Check for expression
                expression = self._get_dts_attr(var, "Expression")
                is_expression = self._get_dts_attr(var, "EvaluateAsExpression") == "True"
                
                variables.append(Variable(
                    name=name,
                    namespace=namespace,
                    data_type=data_type,
                    value=value,
                    expression=expression,
                    is_expression=is_expression,
                ))
            except Exception as e:
                warnings.append(f"Failed to parse variable: {e}")
        
        return variables
    
    def _parse_parameters(self, root: ET.Element, warnings: list[str]) -> list[Parameter]:
        """Parse package parameters (SSIS 2012+)."""
        parameters = []
        
        for param in root.findall(f".//{self.DTS_PREFIX}PackageParameter"):
            try:
                name = self._get_dts_attr(param, "ObjectName") or ""
                required = self._get_dts_attr(param, "Required") == "True"
                sensitive = self._get_dts_attr(param, "Sensitive") == "True"
                
                # B3c: Extract data type
                data_type = self._get_dts_attr(param, "DataType")
                data_type = self._map_ssis_data_type(data_type) if data_type else None
                
                param_value = param.find(f"{self.DTS_PREFIX}Property[@Name='ParameterValue']")
                value = param_value.text if param_value is not None else None
                
                parameters.append(Parameter(
                    name=name,
                    data_type=data_type,
                    value=value,
                    required=required,
                    sensitive=sensitive,
                ))
            except Exception as e:
                warnings.append(f"Failed to parse parameter: {e}")
        
        return parameters
    
    # -------------------------------------------------------------------------
    # Tasks (Control Flow)
    # -------------------------------------------------------------------------
    
    def _parse_tasks(
        self, root: ET.Element, warnings: list[str]
    ) -> tuple[list[Task], list[str]]:
        """Parse control flow tasks."""
        tasks = []
        disabled_tasks = []
        
        # Find Executables container
        executables = root.find(f".//{self.DTS_PREFIX}Executables")
        if executables is None:
            return tasks, disabled_tasks
        
        for exec_elem in executables.findall(f"{self.DTS_PREFIX}Executable"):
            try:
                task, is_disabled = self._parse_task(exec_elem, warnings)
                tasks.append(task)
                if is_disabled:
                    disabled_tasks.append(task.name)
            except Exception as e:
                name = self._get_dts_attr(exec_elem, "ObjectName") or "unknown"
                warnings.append(f"Failed to parse task '{name}': {e}")
        
        return tasks, disabled_tasks
    
    def _parse_task(
        self, elem: ET.Element, warnings: list[str]
    ) -> tuple[Task, bool]:
        """Parse a single task or container."""
        name = self._get_dts_attr(elem, "ObjectName") or "Unknown"
        description = self._get_dts_attr(elem, "Description")
        disabled = self._get_dts_attr(elem, "Disabled") == "True"
        creation_name = self._get_dts_attr(elem, "CreationName") or ""
        
        # Determine task type
        task_type = self._infer_task_type(creation_name)
        
        # Task-specific parsing
        sql_statement = None
        connection_ref = None
        data_flow = None
        child_tasks = []
        properties = {}
        
        if task_type == TaskType.EXECUTE_SQL:
            sql_statement, connection_ref = self._parse_execute_sql_task(elem)
        elif task_type == TaskType.DATA_FLOW:
            data_flow = self._parse_data_flow_task(elem, warnings)
        elif task_type == TaskType.SCRIPT:
            # B3c: Parse Script Task to extract code and language
            properties = self._parse_script_task(elem)
        elif task_type in (TaskType.FOR_LOOP, TaskType.FOREACH_LOOP, TaskType.SEQUENCE):
            # Parse child tasks in containers
            child_executables = elem.find(f"{self.DTS_PREFIX}Executables")
            if child_executables is not None:
                for child_elem in child_executables.findall(f"{self.DTS_PREFIX}Executable"):
                    child_task, _ = self._parse_task(child_elem, warnings)
                    child_tasks.append(child_task)
        
        return Task(
            name=name,
            task_type=task_type,
            description=description,
            disabled=disabled,
            sql_statement=sql_statement,
            connection_ref=connection_ref,
            data_flow=data_flow,
            child_tasks=child_tasks,
            properties=properties,
        ), disabled
    
    def _infer_task_type(self, creation_name: str) -> TaskType:
        """Infer task type from CreationName."""
        creation_name = creation_name.upper()
        
        if "PIPELINE" in creation_name or "DATAFLOW" in creation_name:
            return TaskType.DATA_FLOW
        elif "SQLTASK" in creation_name or "EXECUTESQL" in creation_name:
            return TaskType.EXECUTE_SQL
        elif "SCRIPTTASK" in creation_name:
            return TaskType.SCRIPT
        elif "EXECUTEPACKAGE" in creation_name:
            return TaskType.EXECUTE_PACKAGE
        elif "FORLOOP" in creation_name:
            return TaskType.FOR_LOOP
        elif "FOREACHLOOP" in creation_name:
            return TaskType.FOREACH_LOOP
        elif "SEQUENCE" in creation_name:
            return TaskType.SEQUENCE
        elif "EXPRESSIONTASK" in creation_name:
            return TaskType.EXPRESSION
        elif "FILESYSTEM" in creation_name:
            return TaskType.FILE_SYSTEM
        elif "FTP" in creation_name:
            return TaskType.FTP
        elif "SENDMAIL" in creation_name:
            return TaskType.SEND_MAIL
        elif "EXECUTEPROCESS" in creation_name:
            return TaskType.EXECUTE_PROCESS
        else:
            return TaskType.OTHER
    
    def _parse_execute_sql_task(self, elem: ET.Element) -> tuple[str | None, str | None]:
        """Parse Execute SQL Task details."""
        sql_statement = None
        connection_ref = None
        
        object_data = elem.find(f"{self.DTS_PREFIX}ObjectData")
        if object_data is not None:
            sql_task = object_data.find("SQLTask:SqlTaskData", self.NAMESPACES)
            if sql_task is not None:
                sql_statement = sql_task.get("SqlStatementSource")
                connection_ref = sql_task.get("Connection")
        
        return sql_statement, connection_ref
    
    # -------------------------------------------------------------------------
    # Data Flow
    # -------------------------------------------------------------------------
    
    def _parse_data_flow_task(self, elem: ET.Element, warnings: list[str]) -> DataFlow | None:
        """Parse Data Flow Task components."""
        name = self._get_dts_attr(elem, "ObjectName") or "DataFlow"
        description = self._get_dts_attr(elem, "Description")
        
        sources = []
        destinations = []
        transformations = []
        paths = []
        
        # Find pipeline components
        object_data = elem.find(f"{self.DTS_PREFIX}ObjectData")
        if object_data is None:
            return DataFlow(name=name, description=description)
        
        pipeline = object_data.find("pipeline")
        if pipeline is None:
            return DataFlow(name=name, description=description)
        
        components = pipeline.find("components")
        if components is None:
            return DataFlow(name=name, description=description)
        
        for component in components.findall("component"):
            try:
                comp_type = self._classify_component(component)
                
                if comp_type == "source":
                    source = self._parse_source_component(component)
                    sources.append(source)
                elif comp_type == "destination":
                    dest = self._parse_destination_component(component)
                    destinations.append(dest)
                else:
                    transform = self._parse_transform_component(component)
                    transformations.append(transform)
            except Exception as e:
                comp_name = component.get("name") or "unknown"
                warnings.append(f"Failed to parse component '{comp_name}': {e}")
        
        # B3c: Parse data flow paths (component wiring)
        paths = self._parse_data_flow_paths(pipeline)
        
        return DataFlow(
            name=name,
            description=description,
            sources=sources,
            destinations=destinations,
            transformations=transformations,
            paths=paths,
        )
    
    def _classify_component(self, component: ET.Element) -> str:
        """Classify component as source, destination, or transform."""
        component_class = component.get("componentClassID") or ""
        name = (component.get("name") or "").lower()
        
        # Source indicators
        if "Source" in component_class or "source" in name:
            return "source"
        
        # Destination indicators
        if "Destination" in component_class or "destination" in name:
            return "destination"
        
        return "transform"
    
    def _parse_source_component(self, component: ET.Element) -> Source:
        """Parse a source component."""
        name = component.get("name") or ""
        component_class = component.get("componentClassID") or ""
        
        # Determine component type
        if "OLE DB" in component_class or "OLEDB" in component_class:
            comp_type = "OLE DB Source"
        elif "Flat File" in component_class:
            comp_type = "Flat File Source"
        elif "Excel" in component_class:
            comp_type = "Excel Source"
        elif "ADO NET" in component_class:
            comp_type = "ADO.NET Source"
        else:
            comp_type = component_class
        
        # Get connection reference
        connection_ref = None
        connections = component.find("connections")
        if connections is not None:
            conn = connections.find("connection")
            if conn is not None:
                connection_ref = conn.get("connectionManagerID")
        
        # Get access mode and table/query
        access_mode = None
        table_name = None
        sql_command = None
        
        properties = component.find("properties")
        if properties is not None:
            for prop in properties.findall("property"):
                prop_name = prop.get("name") or ""
                if prop_name == "AccessMode":
                    access_mode = prop.text
                elif prop_name == "OpenRowset":
                    table_name = prop.text
                elif prop_name == "SqlCommand":
                    sql_command = prop.text
        
        # Parse output columns
        columns = self._parse_output_columns(component)
        
        return Source(
            name=name,
            component_type=comp_type,
            connection_ref=connection_ref,
            access_mode=access_mode,
            table_name=table_name,
            sql_command=sql_command,
            columns=columns,
        )
    
    def _parse_destination_component(self, component: ET.Element) -> Destination:
        """Parse a destination component."""
        name = component.get("name") or ""
        component_class = component.get("componentClassID") or ""
        
        # Determine component type
        if "OLE DB" in component_class or "OLEDB" in component_class:
            comp_type = "OLE DB Destination"
        elif "Flat File" in component_class:
            comp_type = "Flat File Destination"
        elif "Excel" in component_class:
            comp_type = "Excel Destination"
        elif "ADO NET" in component_class:
            comp_type = "ADO.NET Destination"
        else:
            comp_type = component_class
        
        # Get connection reference
        connection_ref = None
        connections = component.find("connections")
        if connections is not None:
            conn = connections.find("connection")
            if conn is not None:
                connection_ref = conn.get("connectionManagerID")
        
        # Get table name
        table_name = None
        access_mode = None
        
        properties = component.find("properties")
        if properties is not None:
            for prop in properties.findall("property"):
                prop_name = prop.get("name") or ""
                if prop_name == "OpenRowset":
                    table_name = prop.text
                elif prop_name == "AccessMode":
                    access_mode = prop.text
        
        # Parse column mappings
        columns = self._parse_column_mappings(component)
        
        return Destination(
            name=name,
            component_type=comp_type,
            connection_ref=connection_ref,
            table_name=table_name,
            access_mode=access_mode,
            columns=columns,
        )
    
    def _parse_transform_component(self, component: ET.Element) -> Transform:
        """Parse a transformation component."""
        name = component.get("name") or ""
        component_class = component.get("componentClassID") or ""
        description = component.get("description")
        
        # Extract component type name
        comp_type = component_class.split(".")[-1] if "." in component_class else component_class
        
        # Extract properties
        properties = {}
        props_elem = component.find("properties")
        if props_elem is not None:
            for prop in props_elem.findall("property"):
                prop_name = prop.get("name")
                if prop_name:
                    properties[prop_name] = prop.text
        
        # B3c: Extract expressions (Derived Column, Conditional Split, etc.)
        expressions = self._parse_transform_expressions(component)
        
        # B3c: Extract lookup-specific details
        lookup_table = None
        join_keys = []
        if "Lookup" in component_class:
            lookup_table, join_keys = self._parse_lookup_details(component)
        
        # B3c: Parse input/output columns
        input_columns = self._parse_input_columns(component)
        output_columns = self._parse_output_columns(component)
        
        return Transform(
            name=name,
            component_type=comp_type,
            description=description,
            properties=properties,
            expressions=expressions,
            lookup_table=lookup_table,
            join_keys=join_keys,
            input_columns=input_columns,
            output_columns=output_columns,
        )
    
    def _parse_output_columns(self, component: ET.Element) -> list[Column]:
        """Parse output columns from a component."""
        columns = []
        
        outputs = component.find("outputs")
        if outputs is None:
            return columns
        
        for output in outputs.findall("output"):
            output_columns = output.find("outputColumns")
            if output_columns is None:
                continue
            
            for col in output_columns.findall("outputColumn"):
                columns.append(Column(
                    name=col.get("name") or "",
                    data_type=col.get("dataType"),
                    length=int(col.get("length") or 0) or None,
                    precision=int(col.get("precision") or 0) or None,
                    scale=int(col.get("scale") or 0) or None,
                ))
        
        return columns
    
    def _parse_input_columns(self, component: ET.Element) -> list[Column]:
        """Parse input columns from a component."""
        columns = []
        
        inputs = component.find("inputs")
        if inputs is None:
            return columns
        
        for inp in inputs.findall("input"):
            input_columns = inp.find("inputColumns")
            if input_columns is None:
                continue
            
            for col in input_columns.findall("inputColumn"):
                columns.append(Column(
                    name=col.get("cachedName") or col.get("name") or "",
                    data_type=col.get("cachedDataType") or col.get("dataType"),
                    length=int(col.get("cachedLength") or col.get("length") or 0) or None,
                    precision=int(col.get("cachedPrecision") or col.get("precision") or 0) or None,
                    scale=int(col.get("cachedScale") or col.get("scale") or 0) or None,
                ))
        
        return columns
    
    def _parse_column_mappings(self, component: ET.Element) -> list[ColumnMapping]:
        """Parse input-to-output column mappings."""
        mappings = []
        
        inputs = component.find("inputs")
        if inputs is None:
            return mappings
        
        for inp in inputs.findall("input"):
            input_columns = inp.find("inputColumns")
            if input_columns is None:
                continue
            
            for col in input_columns.findall("inputColumn"):
                # Get external metadata column (destination column)
                ext_col_id = col.get("externalMetadataColumnId")
                source_col = col.get("cachedName") or col.get("name") or ""
                
                # Try to find destination column name
                dest_col = source_col  # Default to same name
                
                # Look in external metadata
                ext_metadata = inp.find("externalMetadataColumns")
                if ext_metadata is not None and ext_col_id:
                    for ext_col in ext_metadata.findall("externalMetadataColumn"):
                        if ext_col.get("id") == ext_col_id:
                            dest_col = ext_col.get("name") or dest_col
                            break
                
                mappings.append(ColumnMapping(
                    source_column=source_col,
                    destination_column=dest_col,
                ))
        
        return mappings
    
    # -------------------------------------------------------------------------
    # Precedence Constraints
    # -------------------------------------------------------------------------
    
    def _parse_precedence_constraints(
        self, root: ET.Element, warnings: list[str]
    ) -> list[PrecedenceConstraint]:
        """Parse precedence constraints between tasks."""
        constraints = []
        
        for pc in root.findall(f".//{self.DTS_PREFIX}PrecedenceConstraint"):
            try:
                from_task = self._get_dts_attr(pc, "From") or ""
                to_task = self._get_dts_attr(pc, "To") or ""
                
                # Clean up task references (remove package prefix)
                from_task = from_task.split("\\")[-1] if "\\" in from_task else from_task
                to_task = to_task.split("\\")[-1] if "\\" in to_task else to_task
                
                value = self._get_dts_attr(pc, "Value")
                expression = self._get_dts_attr(pc, "Expression")
                
                constraint_type = "Success"  # Default
                if value == "1":
                    constraint_type = "Failure"
                elif value == "2":
                    constraint_type = "Completion"
                elif expression:
                    constraint_type = "Expression"
                
                constraints.append(PrecedenceConstraint(
                    from_task=from_task,
                    to_task=to_task,
                    constraint_type=constraint_type,
                    expression=expression,
                ))
            except Exception as e:
                warnings.append(f"Failed to parse precedence constraint: {e}")
        
        return constraints
    
    # -------------------------------------------------------------------------
    # Annotations
    # -------------------------------------------------------------------------
    
    def _parse_annotations(self, root: ET.Element, warnings: list[str]) -> list[Annotation]:
        """Parse developer annotations."""
        annotations = []
        
        # Find DesignTimeProperties which contains annotation layouts
        for annotation in root.findall(f".//{self.DTS_PREFIX}AnnotationLayout"):
            try:
                text_elem = annotation.find(f"{self.DTS_PREFIX}Text")
                text = text_elem.text if text_elem is not None else ""
                
                if text:
                    annotations.append(Annotation(text=text))
            except Exception as e:
                warnings.append(f"Failed to parse annotation: {e}")
        
        return annotations
    
    # -------------------------------------------------------------------------
    # B3c: SSIS Data Type Mapping
    # -------------------------------------------------------------------------
    
    def _map_ssis_data_type(self, data_type: str | None) -> str | None:
        """Map SSIS DTS:DataType numeric codes to readable names.
        
        SSIS stores data types as numeric codes in the XML.
        """
        if data_type is None:
            return None
        
        # SSIS data type codes (from Microsoft documentation)
        type_map = {
            "2": "Int16",
            "3": "Int32",
            "4": "Single",
            "5": "Double",
            "6": "Currency",
            "7": "DateTime",
            "8": "String",
            "11": "Boolean",
            "13": "Object",
            "14": "Decimal",
            "16": "Int8",
            "17": "UInt8",
            "18": "UInt16",
            "19": "UInt32",
            "20": "Int64",
            "21": "UInt64",
            "72": "Guid",
            "129": "Char",
            "130": "WChar",
            "131": "Numeric",
            "133": "DBDate",
            "134": "DBTime",
            "135": "DBTimestamp",
        }
        
        return type_map.get(data_type, f"Type_{data_type}")
    
    # -------------------------------------------------------------------------
    # B3c: Unparsed Features Collection
    # -------------------------------------------------------------------------
    
    def _collect_unparsed_features(
        self,
        root: ET.Element,
        tasks: list[Task],
        unparsed_features: list[UnparsedFeature],
    ) -> None:
        """Collect features that couldn't be fully parsed.
        
        This is critical for LLM prompts: instead of silently omitting features,
        we explicitly list what wasn't parsed so the LLM can flag risks.
        """
        # Track Script Tasks with code we couldn't extract
        script_tasks = [t for t in tasks if t.task_type == TaskType.SCRIPT]
        if script_tasks:
            for task in script_tasks:
                # Check if we have script content
                has_code = task.properties.get("script_code") or task.properties.get("script_language")
                if not has_code:
                    unparsed_features.append(UnparsedFeature(
                        feature="script_task_code",
                        count=1,
                        location=f"Task: {task.name}",
                        note=f"Script Task '{task.name}' contains code that may need manual review. "
                             "The script logic must be analyzed for migration to Databricks/PySpark.",
                    ))
        
        # Track Event Handlers (not fully parsed)
        event_handlers = root.findall(f".//{self.DTS_PREFIX}EventHandler")
        if event_handlers:
            unparsed_features.append(UnparsedFeature(
                feature="event_handlers",
                count=len(event_handlers),
                location="Package level",
                note=f"Package has {len(event_handlers)} event handler(s) (OnError, OnPreExecute, etc.) "
                     "that may contain important error handling or logging logic.",
            ))
        
        # Track Log Providers (not parsed)
        log_providers = root.findall(f".//{self.DTS_PREFIX}LogProvider")
        if log_providers:
            unparsed_features.append(UnparsedFeature(
                feature="log_providers",
                count=len(log_providers),
                location="Package level",
                note=f"Package has {len(log_providers)} log provider(s) configured. "
                     "Logging behavior should be replicated in target.",
            ))
        
        # Track Package Configurations (external config files)
        configs = root.findall(f".//{self.DTS_PREFIX}Configuration")
        if configs:
            unparsed_features.append(UnparsedFeature(
                feature="package_configurations",
                count=len(configs),
                location="Package level",
                note=f"Package has {len(configs)} external configuration(s). "
                     "These may reference environment variables, XML files, or SQL tables.",
            ))
        
        # Track expressions on containers/tasks that may affect behavior
        for elem in root.iter():
            prop_exprs = elem.findall(f"{self.DTS_PREFIX}PropertyExpression")
            if prop_exprs:
                for prop_expr in prop_exprs:
                    prop_name = self._get_dts_attr(prop_expr, "Name") or prop_expr.get("Name")
                    if prop_name and prop_expr.text:
                        # Don't add each one, just flag if there are dynamic expressions
                        task_name = self._get_dts_attr(elem, "ObjectName") or "Unknown"
                        if not any(f.feature == "dynamic_expressions" for f in unparsed_features):
                            # Count total expressions
                            all_exprs = root.findall(f".//{self.DTS_PREFIX}PropertyExpression")
                            unparsed_features.append(UnparsedFeature(
                                feature="dynamic_expressions",
                                count=len(all_exprs),
                                location="Multiple tasks/containers",
                                note=f"Package uses {len(all_exprs)} SSIS expression(s) for dynamic property values. "
                                     "These need translation to Databricks widgets or Python variables.",
                            ))
                        break
    
    # -------------------------------------------------------------------------
    # B3c: Script Task Parsing
    # -------------------------------------------------------------------------
    
    def _parse_script_task(self, elem: ET.Element) -> dict[str, Any]:
        """Parse Script Task to extract script code and language.
        
        Script Tasks contain embedded C# or VB.NET code that represents
        custom business logic. This is critical for migration analysis.
        """
        script_props: dict[str, Any] = {}
        
        object_data = elem.find(f"{self.DTS_PREFIX}ObjectData")
        if object_data is None:
            return script_props
        
        # Find ScriptProject element
        script_project = object_data.find(".//ScriptProject")
        if script_project is not None:
            script_props["script_language"] = script_project.get("Language") or "Unknown"
            script_props["project_name"] = script_project.get("Name")
        
        # Try to find embedded script code
        # SSIS stores scripts in various formats depending on version
        
        # Method 1: BinaryItem (compiled - can't extract source)
        binary_items = object_data.findall(".//BinaryItem")
        if binary_items:
            script_props["is_binary"] = True
            script_props["binary_items_count"] = len(binary_items)
        
        # Method 2: ProjectItem with source code
        project_items = object_data.findall(".//ProjectItem")
        source_files = []
        for item in project_items:
            item_name = item.get("Name") or ""
            if item_name.endswith((".cs", ".vb", ".py")):
                # Try to get the code
                code = item.text
                if code:
                    source_files.append({
                        "filename": item_name,
                        "code": code,
                        "language": self._infer_script_language(item_name),
                    })
        
        if source_files:
            script_props["source_files"] = source_files
            script_props["script_code"] = source_files[0].get("code") if source_files else None
        
        # Method 3: ScriptTaskProjectItem (SSIS 2012+)
        script_items = object_data.findall(".//ScriptTaskProjectItem")
        for item in script_items:
            item_name = item.get("FileName") or item.get("Name") or ""
            if item_name.endswith((".cs", ".vb")):
                # The actual code might be in CDATA or text
                code = item.text
                if code and not script_props.get("script_code"):
                    script_props["script_code"] = code
                    script_props["script_language"] = self._infer_script_language(item_name)
        
        # Extract ReadOnlyVariables and ReadWriteVariables
        for prop_name in ["ReadOnlyVariables", "ReadWriteVariables"]:
            prop_elem = object_data.find(f".//*[@Name='{prop_name}']")
            if prop_elem is not None and prop_elem.text:
                script_props[prop_name.lower()] = prop_elem.text.split(",")
        
        return script_props
    
    def _infer_script_language(self, filename: str) -> str:
        """Infer script language from filename extension."""
        filename = filename.lower()
        if filename.endswith(".cs"):
            return "C#"
        elif filename.endswith(".vb"):
            return "VB.NET"
        elif filename.endswith(".py"):
            return "Python"
        else:
            return "Unknown"
    
    # -------------------------------------------------------------------------
    # B3c: Data Flow Path Parsing
    # -------------------------------------------------------------------------
    
    def _parse_data_flow_paths(self, pipeline: ET.Element) -> list[DataFlowPath]:
        """Parse data flow paths (component wiring topology).
        
        Paths connect outputs of one component to inputs of another,
        defining the data flow order through the pipeline.
        """
        paths = []
        
        paths_elem = pipeline.find("paths")
        if paths_elem is None:
            return paths
        
        for path in paths_elem.findall("path"):
            try:
                # Path references components by ID, but we need names
                start_id = path.get("startId") or ""
                end_id = path.get("endId") or ""
                
                # startId format: "Package\DataFlow\Component.Outputs[Output Name]"
                # endId format: "Package\DataFlow\Component.Inputs[Input Name]"
                
                from_component = ""
                from_output = "Output"
                to_component = ""
                to_input = "Input"
                
                # Parse start (from)
                if "." in start_id:
                    from_part = start_id.split(".")
                    from_component = from_part[0].split("\\")[-1] if "\\" in from_part[0] else from_part[0]
                    if len(from_part) > 1 and "[" in from_part[1]:
                        from_output = from_part[1].split("[")[1].rstrip("]")
                
                # Parse end (to)
                if "." in end_id:
                    to_part = end_id.split(".")
                    to_component = to_part[0].split("\\")[-1] if "\\" in to_part[0] else to_part[0]
                    if len(to_part) > 1 and "[" in to_part[1]:
                        to_input = to_part[1].split("[")[1].rstrip("]")
                
                if from_component and to_component:
                    paths.append(DataFlowPath(
                        from_component=from_component,
                        from_output=from_output,
                        to_component=to_component,
                        to_input=to_input,
                    ))
            except Exception:
                pass  # Skip malformed paths
        
        return paths
    
    # -------------------------------------------------------------------------
    # B3c: Enhanced Transform Expression Parsing
    # -------------------------------------------------------------------------
    
    def _parse_transform_expressions(self, component: ET.Element) -> dict[str, str]:
        """Extract expressions from Derived Column, Conditional Split, etc.
        
        These expressions contain business logic that must be translated
        to equivalent PySpark/SQL expressions.
        """
        expressions: dict[str, str] = {}
        component_class = component.get("componentClassID") or ""
        
        # Derived Column expressions
        if "Derived" in component_class or "DerivedColumn" in component_class:
            outputs = component.find("outputs")
            if outputs is not None:
                for output in outputs.findall("output"):
                    for col in output.findall(".//outputColumn"):
                        col_name = col.get("name") or ""
                        # Expression is in properties
                        props = col.find("properties")
                        if props is not None:
                            for prop in props.findall("property"):
                                if prop.get("name") == "Expression":
                                    expr = prop.text
                                    if expr:
                                        expressions[col_name] = expr
        
        # Conditional Split expressions
        elif "ConditionalSplit" in component_class:
            outputs = component.find("outputs")
            if outputs is not None:
                for output in outputs.findall("output"):
                    output_name = output.get("name") or ""
                    if output_name.lower() == "default output":
                        continue
                    # Expression is in output properties
                    props = output.find("properties")
                    if props is not None:
                        for prop in props.findall("property"):
                            if prop.get("name") == "Expression":
                                expr = prop.text
                                if expr:
                                    expressions[f"condition:{output_name}"] = expr
        
        # Lookup expressions (match conditions)
        elif "Lookup" in component_class:
            props = component.find("properties")
            if props is not None:
                for prop in props.findall("property"):
                    prop_name = prop.get("name") or ""
                    if "JoinKey" in prop_name or "SqlCommand" in prop_name:
                        if prop.text:
                            expressions[prop_name] = prop.text
        
        return expressions
    
    def _parse_lookup_details(self, component: ET.Element) -> tuple[str | None, list[str]]:
        """Extract lookup table and join keys from Lookup transform."""
        lookup_table = None
        join_keys = []
        
        props = component.find("properties")
        if props is not None:
            for prop in props.findall("property"):
                prop_name = prop.get("name") or ""
                if prop_name == "SqlCommand" and prop.text:
                    # Try to extract table from SQL
                    sql = prop.text
                    match = re.search(r"FROM\s+(\[?\w+\]?\.\[?\w+\]?|\[?\w+\]?)", sql, re.IGNORECASE)
                    if match:
                        lookup_table = match.group(1).replace("[", "").replace("]", "")
        
        # Join keys from input columns with JoinToReferenceColumn
        inputs = component.find("inputs")
        if inputs is not None:
            for inp in inputs.findall("input"):
                for col in inp.findall(".//inputColumn"):
                    props = col.find("properties")
                    if props is not None:
                        for prop in props.findall("property"):
                            if prop.get("name") == "JoinToReferenceColumn" and prop.text:
                                source_col = col.get("cachedName") or col.get("name") or ""
                                join_keys.append(f"{source_col}={prop.text}")
        
        return lookup_table, join_keys
    
    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    
    def _get_dts_attr(self, elem: ET.Element, attr_name: str) -> str | None:
        """Get DTS-namespaced attribute value."""
        return elem.get(f"{self.DTS_PREFIX}{attr_name}")
