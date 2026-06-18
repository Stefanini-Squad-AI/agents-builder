"""Type mapping for SSIS → SQL Server → Databricks conversions.

Provides bidirectional mappings between:
- SSIS data types (dt_str, dt_i4, dt_numeric, etc.)
- SQL Server data types (varchar, int, decimal, etc.)
- Databricks/Spark data types (STRING, INT, DECIMAL, etc.)

Used by:
- StructuralComparator: to match SSIS columns against DB columns
- Analysis prompts: to explain type implications to LLM
- Code generation: to generate correct Databricks DDL
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SSISDataType(str, Enum):
    """SSIS Integration Services data types.
    
    These are the numeric codes used in SSIS XML (DTS:DataType attribute)
    mapped to their human-readable names.
    """
    
    # String types
    DT_STR = "dt_str"              # Non-Unicode string (ANSI)
    DT_WSTR = "dt_wstr"            # Unicode string
    DT_TEXT = "dt_text"            # Non-Unicode text stream
    DT_NTEXT = "dt_ntext"          # Unicode text stream
    
    # Integer types
    DT_I1 = "dt_i1"                # 1-byte signed integer
    DT_I2 = "dt_i2"                # 2-byte signed integer
    DT_I4 = "dt_i4"                # 4-byte signed integer
    DT_I8 = "dt_i8"                # 8-byte signed integer
    DT_UI1 = "dt_ui1"              # 1-byte unsigned integer
    DT_UI2 = "dt_ui2"              # 2-byte unsigned integer
    DT_UI4 = "dt_ui4"              # 4-byte unsigned integer
    DT_UI8 = "dt_ui8"              # 8-byte unsigned integer
    
    # Floating point types
    DT_R4 = "dt_r4"                # Single-precision float
    DT_R8 = "dt_r8"                # Double-precision float
    DT_NUMERIC = "dt_numeric"      # Exact numeric with precision and scale
    DT_DECIMAL = "dt_decimal"      # Exact numeric (synonym for dt_numeric)
    DT_CY = "dt_cy"                # Currency (8-byte, 4 decimal places)
    
    # Boolean
    DT_BOOL = "dt_bool"            # Boolean
    
    # Date/Time types
    DT_DATE = "dt_date"            # Date only
    DT_DBDATE = "dt_dbdate"        # Database date
    DT_DBTIME = "dt_dbtime"        # Database time
    DT_DBTIME2 = "dt_dbtime2"      # Database time with fractional seconds
    DT_DBTIMESTAMP = "dt_dbtimestamp"        # Date and time
    DT_DBTIMESTAMP2 = "dt_dbtimestamp2"      # Date and time with fractional seconds
    DT_DBTIMESTAMPOFFSET = "dt_dbtimestampoffset"  # Date, time, and time zone
    DT_FILETIME = "dt_filetime"    # Windows FILETIME
    
    # Binary types
    DT_BYTES = "dt_bytes"          # Binary data
    DT_IMAGE = "dt_image"          # Binary image stream
    
    # Other types
    DT_GUID = "dt_guid"            # GUID/UUID
    DT_NULL = "dt_null"            # Null
    DT_EMPTY = "dt_empty"          # Empty


# SSIS numeric type codes → human-readable names
SSIS_TYPE_CODE_MAP: dict[int, str] = {
    2: "dt_i2",           # smallint
    3: "dt_i4",           # int
    4: "dt_r4",           # real
    5: "dt_r8",           # float
    6: "dt_cy",           # currency
    7: "dt_date",         # date
    8: "dt_str",          # non-unicode string
    11: "dt_bool",        # boolean
    13: "dt_dbtime",      # time
    14: "dt_decimal",     # decimal
    16: "dt_i1",          # tinyint
    17: "dt_ui1",         # unsigned tinyint
    18: "dt_ui2",         # unsigned smallint
    19: "dt_ui4",         # unsigned int
    20: "dt_i8",          # bigint
    21: "dt_ui8",         # unsigned bigint
    72: "dt_guid",        # uniqueidentifier
    128: "dt_bytes",      # binary
    129: "dt_str",        # char/varchar (ANSI)
    130: "dt_wstr",       # nchar/nvarchar (Unicode)
    131: "dt_numeric",    # numeric
    133: "dt_dbdate",     # date only
    134: "dt_dbtime",     # time only
    135: "dt_dbtimestamp", # datetime
    141: "dt_dbtimestamp2", # datetime2
    145: "dt_dbtimestampoffset", # datetimeoffset
    146: "dt_dbtime2",    # time with precision
}


@dataclass
class TypeMapping:
    """A mapping between SSIS, SQL Server, and Databricks types."""
    
    ssis_type: str
    sql_server_type: str
    databricks_type: str
    notes: str | None = None
    precision_handling: str | None = None


# Comprehensive type mapping table
TYPE_MAPPINGS: list[TypeMapping] = [
    # String types
    TypeMapping("dt_str", "varchar", "STRING", "ANSI string → UTF-8"),
    TypeMapping("dt_str", "char", "STRING", "Fixed-length ANSI → STRING"),
    TypeMapping("dt_wstr", "nvarchar", "STRING", "Unicode string"),
    TypeMapping("dt_wstr", "nchar", "STRING", "Fixed-length Unicode → STRING"),
    TypeMapping("dt_text", "text", "STRING", "Legacy text type (deprecated)"),
    TypeMapping("dt_ntext", "ntext", "STRING", "Legacy Unicode text (deprecated)"),
    
    # Integer types
    TypeMapping("dt_i1", "tinyint", "TINYINT"),
    TypeMapping("dt_i2", "smallint", "SMALLINT"),
    TypeMapping("dt_i4", "int", "INT"),
    TypeMapping("dt_i8", "bigint", "BIGINT"),
    TypeMapping("dt_ui1", "tinyint", "SMALLINT", "Unsigned → next larger signed"),
    TypeMapping("dt_ui2", "smallint", "INT", "Unsigned → next larger signed"),
    TypeMapping("dt_ui4", "int", "BIGINT", "Unsigned → next larger signed"),
    TypeMapping("dt_ui8", "bigint", "DECIMAL(20,0)", "No unsigned 64-bit in Spark"),
    
    # Floating point types
    TypeMapping("dt_r4", "real", "FLOAT", "32-bit float"),
    TypeMapping("dt_r4", "float(24)", "FLOAT", "SQL Server real alias"),
    TypeMapping("dt_r8", "float", "DOUBLE", "64-bit float"),
    TypeMapping("dt_r8", "float(53)", "DOUBLE", "SQL Server float default"),
    TypeMapping("dt_numeric", "decimal", "DECIMAL", "Preserves precision/scale", "DECIMAL(p,s)"),
    TypeMapping("dt_numeric", "numeric", "DECIMAL", "Synonym for decimal", "DECIMAL(p,s)"),
    TypeMapping("dt_decimal", "decimal", "DECIMAL", precision_handling="DECIMAL(p,s)"),
    TypeMapping("dt_cy", "money", "DECIMAL(19,4)", "Currency fixed precision"),
    TypeMapping("dt_cy", "smallmoney", "DECIMAL(10,4)", "Small currency"),
    
    # Boolean
    TypeMapping("dt_bool", "bit", "BOOLEAN"),
    
    # Date/Time types
    TypeMapping("dt_date", "date", "DATE"),
    TypeMapping("dt_dbdate", "date", "DATE"),
    TypeMapping("dt_dbtime", "time", "STRING", "No TIME type in Delta, use STRING", "HH:mm:ss.SSSSSSS"),
    TypeMapping("dt_dbtime2", "time", "STRING", "Time with precision → STRING"),
    TypeMapping("dt_dbtimestamp", "datetime", "TIMESTAMP"),
    TypeMapping("dt_dbtimestamp", "smalldatetime", "TIMESTAMP", "Less precision"),
    TypeMapping("dt_dbtimestamp2", "datetime2", "TIMESTAMP", "Higher precision datetime"),
    TypeMapping("dt_dbtimestampoffset", "datetimeoffset", "TIMESTAMP", "Loses timezone offset!"),
    TypeMapping("dt_filetime", "bigint", "BIGINT", "Windows FILETIME as ticks"),
    
    # Binary types
    TypeMapping("dt_bytes", "binary", "BINARY"),
    TypeMapping("dt_bytes", "varbinary", "BINARY"),
    TypeMapping("dt_image", "image", "BINARY", "Legacy image type (deprecated)"),
    
    # Other types
    TypeMapping("dt_guid", "uniqueidentifier", "STRING", "GUID as 36-char string"),
]


# Quick lookup dictionaries
_SSIS_TO_DATABRICKS: dict[str, str] = {}
_SQL_TO_DATABRICKS: dict[str, str] = {}
_SSIS_TO_SQL: dict[str, str] = {}

for m in TYPE_MAPPINGS:
    if m.ssis_type not in _SSIS_TO_DATABRICKS:
        _SSIS_TO_DATABRICKS[m.ssis_type] = m.databricks_type
    if m.sql_server_type not in _SQL_TO_DATABRICKS:
        _SQL_TO_DATABRICKS[m.sql_server_type] = m.databricks_type
    if m.ssis_type not in _SSIS_TO_SQL:
        _SSIS_TO_SQL[m.ssis_type] = m.sql_server_type


def ssis_to_databricks(
    ssis_type: str,
    precision: int | None = None,
    scale: int | None = None,
    length: int | None = None,
) -> str:
    """Convert SSIS data type to Databricks data type.
    
    Args:
        ssis_type: SSIS type name (e.g., "dt_i4", "dt_numeric")
        precision: Numeric precision (for decimal types)
        scale: Numeric scale (for decimal types)
        length: String/binary length (currently ignored, Databricks uses unbounded)
    
    Returns:
        Databricks type string (e.g., "INT", "DECIMAL(18,4)")
    """
    ssis_type_lower = ssis_type.lower()
    base_type = _SSIS_TO_DATABRICKS.get(ssis_type_lower, "STRING")
    
    # Handle decimal/numeric with precision and scale
    if base_type == "DECIMAL" and precision is not None:
        scale = scale or 0
        return f"DECIMAL({precision},{scale})"
    
    return base_type


def sql_server_to_databricks(
    sql_type: str,
    precision: int | None = None,
    scale: int | None = None,
    max_length: int | None = None,
) -> str:
    """Convert SQL Server data type to Databricks data type.
    
    Args:
        sql_type: SQL Server type name (e.g., "int", "varchar", "decimal")
        precision: Numeric precision
        scale: Numeric scale
        max_length: Max length for string types
    
    Returns:
        Databricks type string
    """
    # Normalize: lowercase and strip size specifications
    sql_type_lower = sql_type.lower().strip()
    
    # Handle types with size specifications like "varchar(100)"
    base_type = sql_type_lower.split("(")[0].strip()
    
    db_type = _SQL_TO_DATABRICKS.get(base_type, "STRING")
    
    # Handle decimal/numeric with precision and scale
    if base_type in ("decimal", "numeric") and precision is not None:
        scale = scale or 0
        return f"DECIMAL({precision},{scale})"
    
    return db_type


def ssis_type_code_to_name(code: int) -> str:
    """Convert SSIS numeric type code to human-readable name.
    
    Args:
        code: SSIS DTS:DataType numeric code (e.g., 3 for int)
    
    Returns:
        Human-readable type name (e.g., "dt_i4")
    """
    return SSIS_TYPE_CODE_MAP.get(code, f"unknown_{code}")


def are_types_compatible(ssis_type: str, sql_type: str) -> bool:
    """Check if an SSIS type is compatible with a SQL Server type.
    
    Used by structural comparison to detect type mismatches.
    
    Args:
        ssis_type: SSIS type name
        sql_type: SQL Server type name
    
    Returns:
        True if types are compatible, False otherwise
    """
    ssis_lower = ssis_type.lower()
    sql_lower = sql_type.lower().split("(")[0].strip()
    
    # Find all mappings for this SSIS type
    for m in TYPE_MAPPINGS:
        if m.ssis_type == ssis_lower and m.sql_server_type == sql_lower:
            return True
    
    # Special cases: string types are generally compatible
    string_ssis = {"dt_str", "dt_wstr", "dt_text", "dt_ntext"}
    string_sql = {"varchar", "nvarchar", "char", "nchar", "text", "ntext"}
    if ssis_lower in string_ssis and sql_lower in string_sql:
        return True
    
    # Integer types with same or larger size are compatible
    int_order = ["dt_i1", "dt_ui1", "dt_i2", "dt_ui2", "dt_i4", "dt_ui4", "dt_i8", "dt_ui8"]
    sql_int_map = {
        "tinyint": 0, "smallint": 2, "int": 4, "bigint": 6
    }
    if ssis_lower in int_order and sql_lower in sql_int_map:
        ssis_idx = int_order.index(ssis_lower) if ssis_lower in int_order else -1
        sql_idx = sql_int_map.get(sql_lower, -1)
        if ssis_idx >= 0 and sql_idx >= 0:
            # SQL type should be at least as large
            return sql_idx >= (ssis_idx // 2) * 2
    
    return False


def get_type_mapping_notes(ssis_type: str) -> str | None:
    """Get migration notes for an SSIS type.
    
    Args:
        ssis_type: SSIS type name
    
    Returns:
        Notes about the type mapping, or None
    """
    ssis_lower = ssis_type.lower()
    for m in TYPE_MAPPINGS:
        if m.ssis_type == ssis_lower:
            return m.notes
    return None
