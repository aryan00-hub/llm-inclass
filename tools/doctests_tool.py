"""Run doctests for a python module with verbose output.

This tool executes pytest doctests and returns the command output so the agent can verify pass/fail status.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.is_path_safe import is_path_safe

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "doctests",
        "description": "Run verbose doctests on a python file path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Python file path to test.",
                }
            },
            "required": ["path"],
        },
    },
}


def run_doctests(path: str) -> str:
    """Run pytest doctests with --verbose for a single safe local path.

    >>> run_doctests("../chat.py")
    'ERROR: unsafe path'
    >>> run_doctests("missing_file.py")
    'ERROR: file not found'
    >>> import tempfile, os
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "ok.py"
    ...     content = "\\n".join(['\"\"\"x', '', '>>> 1+1', '2', '\"\"\"', ''])
    ...     _ = p.write_text(content, encoding="utf-8")
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     out = run_doctests("ok.py")
    ...     os.chdir(old)
    >>> "1 passed" in out
    True
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     out2 = run_doctests(".")
    ...     os.chdir(old)
    >>> out2
    'ERROR: path is a directory'
    """
    if not is_path_safe(path):
        return "ERROR: unsafe path"

    file_path = Path(path)
    if not file_path.exists():
        return "ERROR: file not found"
    if file_path.is_dir():
        return "ERROR: path is a directory"

    cmd = [sys.executable, "-m", "pytest", path, "--doctest-modules", "--verbose"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return output.strip()
