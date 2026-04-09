"""Local cat tool for reading text files.

The tool reads UTF-8 text by default, falls back to UTF-16, and returns friendly error strings for failures.
"""

from __future__ import annotations

from pathlib import Path

from tools.is_path_safe import is_path_safe

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "cat",
        "description": "Read a text file and return its contents.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the file to read.",
                }
            },
            "required": ["path"],
        },
    },
}


def run_cat(path: str) -> str:
    """Read a file and return text, or an error string if it cannot be read.

    >>> import tempfile
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d)
    ...     f = p / "note.txt"
    ...     _ = f.write_text("hello\\nworld", encoding="utf-8")
    ...     old = Path.cwd()
    ...     import os
    ...     os.chdir(d)
    ...     print(run_cat("note.txt"))
    ...     os.chdir(old)
    hello
    world
    >>> run_cat("../secret.txt")
    'ERROR: unsafe path'
    >>> run_cat("missing.txt")
    'ERROR: file not found'
    >>> import tempfile, os
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d)
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = p.joinpath("u16.txt").write_text("hola", encoding="utf-16")
    ...     run_cat("u16.txt")
    ...     os.chdir(old)
    'hola'
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d)
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = p.joinpath("bad.txt").write_bytes(b"\\xff")
    ...     run_cat("bad.txt")
    ...     os.chdir(old)
    'ERROR: cannot decode file'
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     run_cat(".")
    ...     os.chdir(old)
    'ERROR: path is a directory'
    """
    if not is_path_safe(path):
        return "ERROR: unsafe path"

    file_path = Path(path)

    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "ERROR: file not found"
    except IsADirectoryError:
        return "ERROR: path is a directory"
    except UnicodeDecodeError:
        try:
            return file_path.read_text(encoding="utf-16")
        except UnicodeDecodeError:
            return "ERROR: cannot decode file"
