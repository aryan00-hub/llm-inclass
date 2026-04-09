"""Local grep tool for regex search across files.

The tool expands glob patterns, scans matched files line by line, and returns matching lines only.
"""

from __future__ import annotations

import glob
import re
from pathlib import Path

from tools.is_path_safe import is_path_safe

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": "Search files for regex matches and return matching lines.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "File path or glob pattern to search.",
                },
            },
            "required": ["pattern", "path"],
        },
    },
}


def _read_text_with_fallback(path: Path) -> str:
    """Read text using UTF-8 and fallback to UTF-16 for compatibility.

    >>> import tempfile
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "u16.txt"
    ...     _ = p.write_text("hola", encoding="utf-16")
    ...     _read_text_with_fallback(p)
    'hola'
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-16")


def run_grep(pattern: str, path: str) -> str:
    """Return lines matching regex from all files matched by the provided glob.

    >>> import tempfile
    >>> import os
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d)
    ...     _ = (p / "a.txt").write_text("cat\\ndog\\n", encoding="utf-8")
    ...     _ = (p / "b.txt").write_text("dog\\nmouse\\n", encoding="utf-8")
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     print(run_grep("dog", "*.txt"))
    ...     os.chdir(old)
    a.txt:dog
    b.txt:dog
    >>> run_grep("dog", "../*.txt")
    'ERROR: unsafe path'
    >>> run_grep("[", "*.txt")
    'ERROR: invalid regex'
    >>> import tempfile
    >>> import os
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d)
    ...     _ = (p / "dir").mkdir()
    ...     _ = (p / "x.txt").write_text("alpha\\n", encoding="utf-8")
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     run_grep("alpha", "*")
    ...     os.chdir(old)
    'x.txt:alpha'
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d)
    ...     _ = (p / "bad.txt").write_bytes(b"\\xff")
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     run_grep("x", "*.txt")
    ...     os.chdir(old)
    ''
    """
    if not is_path_safe(path):
        return "ERROR: unsafe path"

    try:
        regex = re.compile(pattern)
    except re.error:
        return "ERROR: invalid regex"

    matches: list[str] = []
    for file_name in sorted(glob.glob(path)):
        file_path = Path(file_name)
        if not file_path.is_file():
            continue

        try:
            content = _read_text_with_fallback(file_path)
        except Exception:
            continue

        for line in content.splitlines():
            if regex.search(line):
                matches.append(f"{file_name}:{line}")

    return "\n".join(matches)
