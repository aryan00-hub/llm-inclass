"""Tool for running doctests on a given Python file."""

import subprocess

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "doctests",
        "description": "Run doctests with --verbose on a Python file and return the output.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the Python file to test.",
                }
            },
            "required": ["path"],
        },
    },
}


def is_path_safe(path: str) -> bool:
    """Return True if path is relative and contains no directory traversal.

    >>> is_path_safe("tools/ls_tool.py")
    True
    >>> is_path_safe("/etc/passwd")
    False
    >>> is_path_safe("../secret.py")
    False
    >>> is_path_safe("some/../file.py")
    False
    """
    if path.startswith("/"):
        return False
    if ".." in path.split("/"):
        return False
    return True


def run_doctests(path: str) -> str:
    """Run doctests with --verbose on path and return combined output.

    >>> run_doctests("/etc/passwd")
    'ERROR: unsafe path'
    >>> run_doctests("../bad.py")
    'ERROR: unsafe path'
    >>> import os
    >>> import tempfile
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "sample.py"
    ...     _ = p.write_text(
    ...         "def add(a, b):\\n"
    ...         "    \\"\\"\\"\\n"
    ...         "    >>> add(1, 2)\\n"
    ...         "    3\\n"
    ...         "    \\"\\"\\"\\n"
    ...         "    return a + b\\n",
    ...         encoding="utf-8",
    ...     )
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     out = run_doctests("sample.py")
    ...     os.chdir(old)
    >>> out.endswith("Test passed.")
    True
    """
    if not is_path_safe(path):
        return "ERROR: unsafe path"
    result = subprocess.run(
        ["python3", "-m", "doctest", path, "-v"],
        capture_output=True,
        text=True,
    )
    return (result.stdout + result.stderr).strip()
