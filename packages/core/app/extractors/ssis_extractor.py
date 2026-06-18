"""SSIS Package (.dtsx) extractor.

Parses SQL Server Integration Services packages and produces a structured
markdown document with:
  - Package metadata (name, creation date, version)
  - Variables with types and default values
  - Tasks/Executables with descriptions (including nested containers)
  - Embedded SQL statements (decoded from XML entities)
  - Parameter and Result bindings (variable <-> SQL mappings)
  - Data Flow components with column mappings
  - Workflow dependencies (precedence constraints)
  - Connection manager references (both package-level and project-level)
  - Script Task code (decoded from Base64)
  - For/ForEach Loop details (expressions and variable mappings)
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from app.extractors.base import ExtractionResult, Extractor, truncate_markdown

# XML namespaces used in SSIS packages
NS = {
    "DTS": "www.microsoft.com/SqlServer/Dts",
    "SQLTask": "www.microsoft.com/sqlserver/dts/tasks/sqltask",
}

# Mapping of SSIS task CreationName to friendly names
TASK_TYPES = {
    "Microsoft.ExecuteSQLTask": "Execute SQL Task",
    "Microsoft.Pipeline": "Data Flow Task",
    "Microsoft.ScriptTask": "Script Task",
    "Microsoft.SendMailTask": "Send Mail Task",
    "Microsoft.FileSystemTask": "File System Task",
    "Microsoft.FtpTask": "FTP Task",
    "Microsoft.BulkInsertTask": "Bulk Insert Task",
    "Microsoft.ExecutePackageTask": "Execute Package Task",
    "Microsoft.ExecuteProcessTask": "Execute Process Task",
    "Microsoft.ExpressionTask": "Expression Task",
    "Microsoft.WmiDataReaderTask": "WMI Data Reader Task",
    "Microsoft.XmlTask": "XML Task",
    "Microsoft.TransferDatabaseTask": "Transfer Database Task",
    "Microsoft.TransferLoginsTask": "Transfer Logins Task",
    "Microsoft.TransferObjectsTask": "Transfer Objects Task",
    "STOCK:SEQUENCE": "Sequence Container",
    "STOCK:FORLOOP": "For Loop Container",
    "STOCK:FOREACHLOOP": "For Each Loop Container",
}

# ForEach enumerator type mappings
FOREACH_ENUM_TYPES = {
    "Microsoft.ForEachFileEnumerator": "File Enumerator",
    "Microsoft.ForEachItemEnumerator": "Item Enumerator",
    "Microsoft.ForEachADOEnumerator": "ADO Enumerator",
    "Microsoft.ForEachSMOEnumerator": "SMO Enumerator",
    "Microsoft.ForEachNodeListEnumerator": "NodeList Enumerator",
    "Microsoft.ForEachFromVariableEnumerator": "From Variable Enumerator",
}

# DTS DataType codes to friendly names
DATATYPE_MAP = {
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
    "16": "SByte",
    "17": "Byte",
    "18": "Char",
    "19": "UInt64",
    "20": "Int64",
    "21": "UInt32",
    "22": "UInt16",
}


def _get_attr(elem: ET.Element, attr: str, ns_prefix: str = "DTS") -> str | None:
    """Get an attribute with namespace prefix."""
    return elem.get(f"{{{NS[ns_prefix]}}}{attr}")


def _decode_sql(sql: str | None) -> str:
    """Decode XML-encoded SQL and clean up whitespace."""
    if not sql:
        return ""
    # Decode XML entities (&#xA; -> newline, &lt; -> <, etc.)
    decoded = html.unescape(sql)
    # Normalize line endings
    decoded = decoded.replace("\r\n", "\n").replace("\r", "\n")
    return decoded.strip()


def _extract_task_name(refid: str) -> str:
    """Extract task name from refId like 'Package\\TaskName'."""
    if "\\" in refid:
        return refid.split("\\")[-1]
    return refid


class SSISExtractor(Extractor):
    """Extractor for SSIS .dtsx packages."""

    name = "ssis"

    def can_handle(self, mime_type: str | None, ext: str) -> bool:
        return ext == "dtsx"

    def extract(self, path: Path) -> ExtractionResult:
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ET.ParseError as e:
            return ExtractionResult(
                content_md=f"# SSIS Package Parse Error\n\nFailed to parse XML: {e}",
                content_md_truncated=False,
                extractor_used=self.name,
                error=f"XML parse error: {e}",
            )

        md_parts = []

        # Package metadata
        pkg_name = _get_attr(root, "ObjectName") or path.stem
        creation_date = _get_attr(root, "CreationDate") or "Unknown"
        version_build = _get_attr(root, "VersionBuild") or "?"
        creator = _get_attr(root, "CreatorName") or "Unknown"

        md_parts.append(f"# SSIS Package: {pkg_name}\n")
        md_parts.append("## Package Metadata\n")
        md_parts.append(f"- **Created:** {creation_date}")
        md_parts.append(f"- **Creator:** {creator}")
        md_parts.append(f"- **Version Build:** {version_build}")
        md_parts.append("")

        # Variables
        variables = self._extract_variables(root)
        if variables:
            md_parts.append("## Variables\n")
            md_parts.append("| Name | Type | Default Value |")
            md_parts.append("|------|------|---------------|")
            for var in variables:
                # Escape pipe characters in values — full content, no truncation
                default = var["default"].replace("|", "\\|")
                md_parts.append(f"| {var['name']} | {var['type']} | {default} |")
            md_parts.append("")

        # Tasks/Executables (including nested containers)
        tasks = self._extract_tasks(root)
        if tasks:
            md_parts.append("## Tasks\n")
            for i, task in enumerate(tasks, 1):
                indent = "  " * task.get("depth", 0)
                md_parts.append(f"{indent}### {i}. {task['name']}")
                md_parts.append(f"{indent}**Type:** {task['type']}")
                if task.get("description"):
                    md_parts.append(f"{indent}\n*{task['description']}*")

                # Loop details
                if task.get("loop_details"):
                    loop = task["loop_details"]
                    if loop.get("init_expression") or loop.get("eval_expression"):
                        md_parts.append(f"{indent}\n**Loop Configuration:**")
                        if loop.get("init_expression"):
                            md_parts.append(f"{indent}- Init: `{loop['init_expression']}`")
                        if loop.get("eval_expression"):
                            md_parts.append(f"{indent}- Condition: `{loop['eval_expression']}`")
                        if loop.get("assign_expression"):
                            md_parts.append(f"{indent}- Increment: `{loop['assign_expression']}`")
                    if loop.get("enumerator_type"):
                        md_parts.append(f"{indent}- Enumerator: {loop['enumerator_type']}")
                    if loop.get("variable_mappings"):
                        md_parts.append(f"{indent}- Variable Mappings:")
                        for m in loop["variable_mappings"]:
                            md_parts.append(f'{indent}  - Index {m["index"]} → `{m["variable"]}`')

                # Script task info summary
                if task.get("script_info"):
                    script = task["script_info"]
                    md_parts.append(f"{indent}\n**Script:** {script['language']}")
                    if script.get("read_only_vars"):
                        md_parts.append(f"{indent}- Read-Only Vars: {', '.join(script['read_only_vars'])}")
                    if script.get("read_write_vars"):
                        md_parts.append(f"{indent}- Read-Write Vars: {', '.join(script['read_write_vars'])}")

                md_parts.append("")

        # Script Task Code (separate detailed section)
        script_tasks = [t for t in tasks if t.get("script_info", {}).get("code")]
        if script_tasks:
            md_parts.append("## Script Task Code\n")
            for task in script_tasks:
                script = task["script_info"]
                md_parts.append(f"### {task['name']}\n")
                lang_ext = "csharp" if script["language"] == "C#" else "vb"
                # Full code — no truncation for richer LLM context
                md_parts.append(f"```{lang_ext}")
                md_parts.append(script["code"])
                md_parts.append("```\n")

        # Workflow (Precedence Constraints)
        workflow = self._extract_workflow(root)
        if workflow:
            md_parts.append("## Workflow (Task Dependencies)\n")
            md_parts.append("```")
            for dep in workflow:
                md_parts.append(f"{dep['from']} --> {dep['to']}")
            md_parts.append("```\n")

        # SQL Statements
        sql_statements = self._extract_sql_statements(root)
        if sql_statements:
            md_parts.append("## SQL Statements\n")
            for stmt in sql_statements:
                md_parts.append(f"### {stmt['task_name']}\n")
                md_parts.append("```sql")
                md_parts.append(stmt["sql"])
                md_parts.append("```\n")

        # Parameter and Result Bindings
        bindings = self._extract_bindings(root)
        if bindings:
            md_parts.append("## Parameter & Result Bindings\n")
            md_parts.append("*Shows how variables map to SQL parameters and results*\n")
            for task_name, task_bindings in bindings.items():
                md_parts.append(f"### {task_name}\n")
                if task_bindings.get("params"):
                    md_parts.append("**Input Parameters:**")
                    md_parts.append("| Param | Variable | Direction |")
                    md_parts.append("|-------|----------|-----------|")
                    for p in task_bindings["params"]:
                        md_parts.append(f"| `?` (#{p['name']}) | `{p['variable']}` | {p['direction']} |")
                    md_parts.append("")
                if task_bindings.get("results"):
                    md_parts.append("**Output Results:**")
                    md_parts.append("| Result Name | Variable |")
                    md_parts.append("|-------------|----------|")
                    for r in task_bindings["results"]:
                        md_parts.append(f"| {r['name']} | `{r['variable']}` |")
                    md_parts.append("")

        # Data Flow Components
        data_flows = self._extract_data_flows(root)
        if data_flows:
            md_parts.append("## Data Flow Tasks\n")
            for df in data_flows:
                md_parts.append(f"### {df['name']}\n")
                if df.get("components"):
                    md_parts.append("| Component | Type | Connection | In Cols | Out Cols |")
                    md_parts.append("|-----------|------|------------|---------|----------|")
                    for comp in df["components"]:
                        conn = comp.get("connection", "-") or "-"
                        in_cols = comp.get("input_columns", 0)
                        out_cols = comp.get("output_columns", 0)
                        md_parts.append(f"| {comp['name']} | {comp['type']} | {conn} | {in_cols} | {out_cols} |")
                    md_parts.append("")
                    # Show data flow pipeline
                    if len(df["components"]) > 1:
                        md_parts.append("**Pipeline:**")
                        md_parts.append("```")
                        sources = [c for c in df["components"] if "Source" in c["type"]]
                        transforms = [c for c in df["components"] if "Source" not in c["type"] and "Destination" not in c["type"]]
                        dests = [c for c in df["components"] if "Destination" in c["type"]]
                        flow_parts = []
                        if sources:
                            flow_parts.append(" | ".join(s["name"] for s in sources))
                        if transforms:
                            flow_parts.append(" | ".join(t["name"] for t in transforms))
                        if dests:
                            flow_parts.append(" | ".join(d["name"] for d in dests))
                        md_parts.append(" --> ".join(flow_parts))
                        md_parts.append("```\n")

        # Connection Managers (package-level)
        connections = self._extract_connections(root)
        if connections:
            md_parts.append("## Connection Managers\n")
            md_parts.append("| ID | Name | Type |")
            md_parts.append("|----|------|------|")
            for conn in connections:
                # Full ID — no truncation for accurate reference matching
                md_parts.append(f"| {conn['id']} | {conn['name']} | {conn['type']} |")
            md_parts.append("")

        # Task Connection References (including project-level connections)
        task_connections = self._extract_task_connections(root)
        if task_connections:
            md_parts.append("## Connection References\n")
            md_parts.append("*Connections referenced by tasks (may include project-level connections)*\n")
            md_parts.append("| Connection | Reference | Used By |")
            md_parts.append("|------------|-----------|---------|")
            for conn in task_connections:
                # Full reference — no truncation for accurate matching
                md_parts.append(f"| {conn['name']} | {conn['ref_id']} | {conn['task']} |")
            md_parts.append("")

        content = "\n".join(md_parts)
        truncated_content, was_truncated = truncate_markdown(content)

        return ExtractionResult(
            content_md=truncated_content,
            content_md_truncated=was_truncated,
            extractor_used=self.name,
        )

    def _extract_variables(self, root: ET.Element) -> list[dict]:
        """Extract package variables."""
        variables = []
        for var_elem in root.iter(f"{{{NS['DTS']}}}Variable"):
            name = _get_attr(var_elem, "ObjectName")
            namespace = _get_attr(var_elem, "Namespace") or "User"
            if not name or namespace == "System":
                continue

            value_elem = var_elem.find(f"{{{NS['DTS']}}}VariableValue")
            datatype_code = value_elem.get(f"{{{NS['DTS']}}}DataType") if value_elem is not None else None
            datatype = DATATYPE_MAP.get(datatype_code, datatype_code or "Unknown")
            default_value = value_elem.text if value_elem is not None and value_elem.text else ""

            variables.append({
                "name": name,
                "type": datatype,
                "default": default_value,
                "namespace": namespace,
            })
        return variables

    def _extract_tasks(self, root: ET.Element) -> list[dict]:
        """Extract executable tasks recursively, including nested containers."""
        tasks = []
        executables = root.find(f"{{{NS['DTS']}}}Executables")
        if executables is None:
            return tasks

        self._extract_tasks_recursive(executables, tasks, depth=0)
        return tasks

    def _extract_tasks_recursive(
        self, executables: ET.Element, tasks: list[dict], depth: int
    ) -> None:
        """Recursively extract tasks from containers."""
        for exec_elem in executables.findall(f"{{{NS['DTS']}}}Executable"):
            refid = _get_attr(exec_elem, "refId") or ""
            name = _get_attr(exec_elem, "ObjectName") or _extract_task_name(refid)
            creation_name = _get_attr(exec_elem, "CreationName") or ""
            description = _get_attr(exec_elem, "Description") or ""

            task_type = TASK_TYPES.get(creation_name, creation_name)

            task_info = {
                "name": name,
                "type": task_type,
                "description": description,
                "creation_name": creation_name,
                "depth": depth,
            }

            # Add loop-specific details
            if creation_name == "STOCK:FORLOOP":
                task_info["loop_details"] = self._extract_for_loop_details(exec_elem)
            elif creation_name == "STOCK:FOREACHLOOP":
                task_info["loop_details"] = self._extract_foreach_loop_details(exec_elem)
            elif creation_name == "Microsoft.ScriptTask":
                task_info["script_info"] = self._extract_script_task_info(exec_elem)

            tasks.append(task_info)

            # Recursively process nested executables (containers)
            nested_execs = exec_elem.find(f"{{{NS['DTS']}}}Executables")
            if nested_execs is not None:
                self._extract_tasks_recursive(nested_execs, tasks, depth + 1)

    def _extract_for_loop_details(self, exec_elem: ET.Element) -> dict:
        """Extract For Loop container details (init, eval, assign expressions)."""
        details = {
            "init_expression": "",
            "eval_expression": "",
            "assign_expression": "",
        }
        for prop in exec_elem.findall(f"{{{NS['DTS']}}}Property"):
            prop_name = _get_attr(prop, "Name") or ""
            if prop_name == "InitExpression":
                details["init_expression"] = prop.text or ""
            elif prop_name == "EvalExpression":
                details["eval_expression"] = prop.text or ""
            elif prop_name == "AssignExpression":
                details["assign_expression"] = prop.text or ""
        return details

    def _extract_foreach_loop_details(self, exec_elem: ET.Element) -> dict:
        """Extract ForEach Loop container details."""
        details = {
            "enumerator_type": "Unknown",
            "variable_mappings": [],
        }

        # Get enumerator type
        for_each_enum = exec_elem.find(f"{{{NS['DTS']}}}ForEachEnumerator")
        if for_each_enum is not None:
            enum_creation = _get_attr(for_each_enum, "CreationName") or ""
            details["enumerator_type"] = FOREACH_ENUM_TYPES.get(enum_creation, enum_creation)

        # Get variable mappings
        mappings = exec_elem.find(f"{{{NS['DTS']}}}ForEachVariableMappings")
        if mappings is not None:
            for mapping in mappings.findall(f"{{{NS['DTS']}}}ForEachVariableMapping"):
                var_name = _get_attr(mapping, "VariableName") or ""
                value_index = _get_attr(mapping, "ValueIndex") or ""
                if var_name:
                    details["variable_mappings"].append({
                        "variable": var_name,
                        "index": value_index,
                    })

        return details

    def _extract_script_task_info(self, exec_elem: ET.Element) -> dict:
        """Extract Script Task information including code."""
        info = {
            "language": "Unknown",
            "entry_method": "",
            "code": "",
            "read_only_vars": [],
            "read_write_vars": [],
        }

        obj_data = exec_elem.find(f"{{{NS['DTS']}}}ObjectData")
        if obj_data is None:
            return info

        script_proj = obj_data.find("ScriptProject")
        if script_proj is None:
            return info

        # Get language and variables from ScriptProject attributes
        lang = script_proj.get("Language", "")
        if lang == "CSharp":
            info["language"] = "C#"
        elif lang == "VisualBasic":
            info["language"] = "VB.NET"
        else:
            info["language"] = lang or "Unknown"

        # Get read-only/read-write variables
        ro_vars = script_proj.get("ReadOnlyVariables", "")
        rw_vars = script_proj.get("ReadWriteVariables", "")
        if ro_vars:
            info["read_only_vars"] = [v.strip() for v in ro_vars.split(",") if v.strip()]
        if rw_vars:
            info["read_write_vars"] = [v.strip() for v in rw_vars.split(",") if v.strip()]

        # Find ScriptMain code in ProjectItem elements
        # The code is stored as CDATA or plain text in ProjectItem with Name="ScriptMain.cs"
        for proj_item in script_proj.findall("ProjectItem"):
            item_name = proj_item.get("Name", "")
            if "ScriptMain" in item_name:
                # The text content might be the actual code (CDATA)
                if proj_item.text:
                    code = proj_item.text.strip()
                    # Clean up any BOM or control characters
                    code = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", code)
                    info["code"] = code
                break

        return info

    def _extract_workflow(self, root: ET.Element) -> list[dict]:
        """Extract precedence constraints (task dependencies)."""
        workflow = []
        constraints = root.find(f"{{{NS['DTS']}}}PrecedenceConstraints")
        if constraints is None:
            return workflow

        for constraint in constraints.findall(f"{{{NS['DTS']}}}PrecedenceConstraint"):
            from_ref = _get_attr(constraint, "From") or ""
            to_ref = _get_attr(constraint, "To") or ""

            from_name = _extract_task_name(from_ref)
            to_name = _extract_task_name(to_ref)

            if from_name and to_name:
                workflow.append({
                    "from": from_name,
                    "to": to_name,
                })
        return workflow

    def _extract_sql_statements(self, root: ET.Element) -> list[dict]:
        """Extract SQL statements from Execute SQL Tasks."""
        statements = []

        for exec_elem in root.iter(f"{{{NS['DTS']}}}Executable"):
            creation_name = _get_attr(exec_elem, "CreationName") or ""
            if creation_name != "Microsoft.ExecuteSQLTask":
                continue

            task_name = _get_attr(exec_elem, "ObjectName") or "Unknown Task"

            # Find SQLTask:SqlTaskData element
            obj_data = exec_elem.find(f"{{{NS['DTS']}}}ObjectData")
            if obj_data is None:
                continue

            sql_task = obj_data.find(f"{{{NS['SQLTask']}}}SqlTaskData")
            if sql_task is None:
                continue

            sql_source = sql_task.get(f"{{{NS['SQLTask']}}}SqlStatementSource")
            if sql_source:
                decoded_sql = _decode_sql(sql_source)
                if decoded_sql:
                    statements.append({
                        "task_name": task_name,
                        "sql": decoded_sql,
                    })

        return statements

    def _extract_connections(self, root: ET.Element) -> list[dict]:
        """Extract connection manager references."""
        connections = []
        conn_managers = root.find(f"{{{NS['DTS']}}}ConnectionManagers")
        if conn_managers is None:
            return connections

        for conn in conn_managers.findall(f"{{{NS['DTS']}}}ConnectionManager"):
            conn_id = _get_attr(conn, "DTSID") or ""
            name = _get_attr(conn, "ObjectName") or ""
            creation_name = _get_attr(conn, "CreationName") or ""

            connections.append({
                "id": conn_id.strip("{}"),
                "name": name,
                "type": creation_name,
            })
        return connections

    def _extract_bindings(self, root: ET.Element) -> dict[str, dict]:
        """Extract parameter and result bindings from SQL Tasks.

        Returns a dict keyed by task name, with 'params' and 'results' lists.
        """
        bindings: dict[str, dict] = {}

        for exec_elem in root.iter(f"{{{NS['DTS']}}}Executable"):
            creation_name = _get_attr(exec_elem, "CreationName") or ""
            if creation_name != "Microsoft.ExecuteSQLTask":
                continue

            task_name = _get_attr(exec_elem, "ObjectName") or "Unknown Task"

            obj_data = exec_elem.find(f"{{{NS['DTS']}}}ObjectData")
            if obj_data is None:
                continue

            sql_task = obj_data.find(f"{{{NS['SQLTask']}}}SqlTaskData")
            if sql_task is None:
                continue

            params = []
            results = []

            # Extract parameter bindings (input variables)
            for binding in sql_task.findall(f"{{{NS['SQLTask']}}}ParameterBinding"):
                param_name = binding.get(f"{{{NS['SQLTask']}}}ParameterName") or ""
                var_name = binding.get(f"{{{NS['SQLTask']}}}DtsVariableName") or ""
                direction = binding.get(f"{{{NS['SQLTask']}}}ParameterDirection") or "Input"
                if param_name and var_name:
                    params.append({
                        "name": param_name,
                        "variable": var_name,
                        "direction": direction,
                    })

            # Extract result bindings (output variables)
            for binding in sql_task.findall(f"{{{NS['SQLTask']}}}ResultBinding"):
                result_name = binding.get(f"{{{NS['SQLTask']}}}ResultName") or ""
                var_name = binding.get(f"{{{NS['SQLTask']}}}DtsVariableName") or ""
                if result_name and var_name:
                    results.append({
                        "name": result_name,
                        "variable": var_name,
                    })

            if params or results:
                bindings[task_name] = {"params": params, "results": results}

        return bindings

    def _extract_data_flows(self, root: ET.Element) -> list[dict]:
        """Extract Data Flow Task components (sources, transforms, destinations)."""
        data_flows = []

        for exec_elem in root.iter(f"{{{NS['DTS']}}}Executable"):
            creation_name = _get_attr(exec_elem, "CreationName") or ""
            if creation_name != "Microsoft.Pipeline":
                continue

            task_name = _get_attr(exec_elem, "ObjectName") or "Unknown Data Flow"

            obj_data = exec_elem.find(f"{{{NS['DTS']}}}ObjectData")
            if obj_data is None:
                continue

            # Pipeline element is not namespaced
            pipeline = obj_data.find("pipeline")
            if pipeline is None:
                continue

            components_elem = pipeline.find("components")
            if components_elem is None:
                continue

            components = []
            for comp in components_elem.findall("component"):
                comp_name = comp.get("name") or "Unknown"
                comp_contact = comp.get("contactInfo") or ""
                # Extract component type from contactInfo (e.g., "OLE DB Source;...")
                comp_type = comp_contact.split(";")[0] if comp_contact else "Unknown"

                # Check for connection reference
                connection = None
                conns_elem = comp.find("connections")
                if conns_elem is not None:
                    conn_elem = conns_elem.find("connection")
                    if conn_elem is not None:
                        connection = conn_elem.get("description") or conn_elem.get("name")
                        # Also try connectionManagerRefId for project-level connections
                        if not connection:
                            conn_ref = conn_elem.get("connectionManagerRefId", "")
                            if conn_ref:
                                # Extract name from "Project.ConnectionManagers[Name]"
                                match = re.search(r"\[([^\]]+)\]", conn_ref)
                                if match:
                                    connection = match.group(1)

                # Extract column counts
                input_cols = 0
                output_cols = 0
                inputs_elem = comp.find("inputs")
                if inputs_elem is not None:
                    for inp in inputs_elem.findall("input"):
                        cols = inp.find("inputColumns")
                        if cols is not None:
                            input_cols += len(list(cols))
                outputs_elem = comp.find("outputs")
                if outputs_elem is not None:
                    for out in outputs_elem.findall("output"):
                        cols = out.find("outputColumns")
                        if cols is not None:
                            output_cols += len(list(cols))

                components.append({
                    "name": comp_name,
                    "type": comp_type,
                    "connection": connection,
                    "input_columns": input_cols,
                    "output_columns": output_cols,
                })

            if components:
                data_flows.append({
                    "name": task_name,
                    "components": components,
                })

        return data_flows

    def _extract_task_connections(self, root: ET.Element) -> list[dict]:
        """Extract connection references used by tasks (including project-level connections)."""
        connections = []
        seen_refs = set()

        for exec_elem in root.iter(f"{{{NS['DTS']}}}Executable"):
            task_name = _get_attr(exec_elem, "ObjectName") or "Unknown"

            # Check for connection references in ObjectData
            obj_data = exec_elem.find(f"{{{NS['DTS']}}}ObjectData")
            if obj_data is None:
                continue

            for child in obj_data.iter():
                # Look for connectionManagerRefId attribute (project-level connections)
                conn_ref = child.get("connectionManagerRefId", "")
                if conn_ref and conn_ref not in seen_refs:
                    seen_refs.add(conn_ref)
                    # Extract friendly name from "Project.ConnectionManagers[Name]"
                    match = re.search(r"\[([^\]]+)\]", conn_ref)
                    friendly_name = match.group(1) if match else conn_ref
                    connections.append({
                        "name": friendly_name,
                        "ref_id": conn_ref,
                        "task": task_name,
                    })

                # Look for Connection attribute (SqlTaskData)
                conn_guid = child.get("Connection", "")
                if conn_guid and conn_guid not in seen_refs:
                    seen_refs.add(conn_guid)
                    # Full GUID as name — no truncation for accurate matching
                    connections.append({
                        "name": conn_guid,
                        "ref_id": conn_guid,
                        "task": task_name,
                    })

        return connections
