"""Write a single UTF-8 file and commit via the write_files wrapper.

This thin wrapper exists to make single-file edits easy for the model while reusing write_files logic.
"""

from __future__ import annotations

from tools.write_files_tool import run_write_files

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write one file, commit it, and run doctests if it is python.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "contents": {"type": "string"},
                "commit_message": {"type": "string"},
            },
            "required": ["path", "contents", "commit_message"],
        },
    },
}


def run_write_file(path: str, contents: str, commit_message: str) -> str:
    """Write one file by delegating to run_write_files.

    >>> run_write_file("../bad.py", "x", "bad")
    'ERROR: unsafe path: ../bad.py'
    """
    return run_write_files(
        files=[{"path": path, "contents": contents}],
        commit_message=commit_message,
    )
