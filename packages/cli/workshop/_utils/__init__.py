"""CLI utility functions."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def open_editor(content: str = "", file_extension: str = ".md") -> str:
    """Open $EDITOR with content and return the edited result.
    
    Args:
        content: Initial content to populate in editor
        file_extension: File extension for temporary file
        
    Returns:
        Edited content from the editor
        
    Raises:
        RuntimeError: If editor fails or is cancelled
    """
    # Get editor from environment
    editor = os.environ.get('EDITOR')
    
    if not editor:
        # Try common editors
        for candidate in ['code', 'vim', 'nano', 'notepad']:
            if _command_exists(candidate):
                editor = candidate
                break
    
    if not editor:
        raise RuntimeError(
            "No editor found. Set EDITOR environment variable or install vim/nano/code."
        )
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(
        mode='w+', 
        suffix=file_extension, 
        delete=False, 
        encoding='utf-8'
    ) as temp_file:
        temp_file.write(content)
        temp_file.flush()
        temp_path = Path(temp_file.name)
    
    try:
        print(f"Opening editor: {editor}")
        print("Save and close the editor to continue...")
        
        # Open editor
        result = subprocess.run([editor, str(temp_path)], check=False)
        
        if result.returncode != 0:
            raise RuntimeError(f"Editor exited with code {result.returncode}")
        
        # Read back the edited content
        edited_content = temp_path.read_text(encoding='utf-8')
        return edited_content
    
    finally:
        # Clean up temporary file
        temp_path.unlink(missing_ok=True)


def _command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    return subprocess.run(
        ["where" if os.name == "nt" else "which", command],
        capture_output=True,
        check=False
    ).returncode == 0


def format_table(data: list[dict], headers: list[str]) -> str:
    """Format data as a simple table.
    
    Args:
        data: List of dictionaries with row data
        headers: Column headers
        
    Returns:
        Formatted table string
    """
    if not data:
        return "No data to display"
    
    # Calculate column widths
    col_widths = {}
    for header in headers:
        col_widths[header] = len(header)
    
    for row in data:
        for header in headers:
            value = str(row.get(header, ""))
            col_widths[header] = max(col_widths[header], len(value))
    
    # Format table
    lines = []
    
    # Header
    header_line = " | ".join(header.ljust(col_widths[header]) for header in headers)
    lines.append(header_line)
    lines.append("-" * len(header_line))
    
    # Rows
    for row in data:
        row_line = " | ".join(
            str(row.get(header, "")).ljust(col_widths[header]) 
            for header in headers
        )
        lines.append(row_line)
    
    return "\n".join(lines)