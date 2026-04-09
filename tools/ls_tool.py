"""Local ls tool for listing project files.

The tool behaves like a minimal shell ls and returns sorted entries for stable test output.
"""

from __future__ import annotations

import glob
import os

from tools.is_path_safe import is_path_safe

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "ls",
        "description": "List files in a directory (default current directory).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Defaults to current directory.",
                }
            },
            "required": [],
        },
    },
}


def run_ls(path: str = ".") -> str:
    """List files in the given directory and return sorted basenames.

    >>> import tempfile
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d)
    ...     _ = (p / "b.txt").write_text("b", encoding="utf-8")
    ...     _ = (p / "a.txt").write_text("a", encoding="utf-8")
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     print(run_ls("."))
    ...     os.chdir(old)
    a.txt
    b.txt
    >>> run_ls("../")
    'ERROR: unsafe path'
    """
    if not is_path_safe(path):
        return "ERROR: unsafe path"

    entries = glob.glob(os.path.join(path, "*"))
    names = [os.path.basename(entry.rstrip("/")) for entry in entries]
    names.sort()
    return "\n".join(names)
