"""Parser implementations for different ETL technologies."""

from app.modules.migration_workbench.analysis.parsers.base import ParserInterface
from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser


def get_parser(technology: str) -> ParserInterface:
    """Get parser for a given technology.
    
    Args:
        technology: Technology slug (e.g., 'ssis', 'airflow')
        
    Returns:
        Parser instance for the technology
        
    Raises:
        ValueError: If no parser exists for the technology
    """
    parsers = {
        "ssis": SSISParser,
    }
    
    parser_class = parsers.get(technology.lower())
    if not parser_class:
        raise ValueError(f"No parser available for technology: {technology}")
    
    return parser_class()


__all__ = [
    "ParserInterface",
    "SSISParser",
    "get_parser",
]
