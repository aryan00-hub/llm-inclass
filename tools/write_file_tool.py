"""Write-file tool specs plus a thin wrapper around write_files.

This module keeps the single-file tool interface while delegating core logic to
the multi-file implementation to avoid duplicate write/commit code.
"""

from __future__ import annotations

from tools.write_files_tool import run_write_files as run_write_files_core

TOOL_SPEC_WRITE_FILES = {
    "type": "function",
    "function": {
        "name": "write_files",
        "description": (
            "Write multiple UTF-8 files and commit once. "
            "Use when a task updates more than one file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "description": "List of file objects with path and either contents or diff.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "contents": {
                                "type": "string",
                                "description": "Optional full UTF-8 file contents.",
                            },
                            "diff": {
                                "type": "string",
                                "description": "Optional unified diff patch for updating an existing file.",
                            },
                        },
                        "required": ["path"],
                    },
                },
                "commit_message": {
                    "type": "string",
                    "description": "Commit message suffix; '[docchat] ' is added automatically.",
                },
            },
            "required": ["files", "commit_message"],
        },
    },
}

TOOL_SPEC_WRITE_FILE = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": (
            "Write one UTF-8 file, commit it, and run doctests if it is Python. "
            "Use for a single-file edit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path to write."},
                "contents": {
                    "type": "string",
                    "description": "Optional full UTF-8 file contents.",
                },
                "diff": {
                    "type": "string",
                    "description": "Optional unified diff patch for updating an existing file.",
                },
                "commit_message": {
                    "type": "string",
                    "description": "Commit message suffix; '[docchat] ' is added automatically.",
                },
            },
            "required": ["path", "commit_message"],
        },
    },
}


def run_write_file(
    path: str,
    contents: str | None,
    commit_message: str,
    diff: str | None = None,
) -> str:
    """Write or update one file by delegating to run_write_files.

    >>> run_write_file("../bad.txt", "x", "bad")
    'ERROR: unsafe path: ../bad.txt'
    >>> run_write_file("x.txt", None, "bad")
    'ERROR: each file entry must include either contents or diff'
    >>> import tempfile, os, subprocess
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = subprocess.check_call(["git", "init", "-q"])
    ...     _ = subprocess.check_call(["git", "config", "user.email", "bot@example.com"])
    ...     _ = subprocess.check_call(["git", "config", "user.name", "Doc Bot"])
    ...     out = run_write_file("note.txt", "hello", "add note")
    ...     saved = Path("note.txt").read_text(encoding="utf-8")
    ...     os.chdir(old)
    >>> saved
    'hello'
    >>> out.startswith("Committed")
    True
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = subprocess.check_call(["git", "init", "-q"])
    ...     _ = subprocess.check_call(["git", "config", "user.email", "bot@example.com"])
    ...     _ = subprocess.check_call(["git", "config", "user.name", "Doc Bot"])
    ...     _ = Path("u.txt").write_text("hello\\nworld\\n", encoding="utf-8")
    ...     _ = subprocess.check_call(["git", "add", "u.txt"])
    ...     _ = subprocess.check_call(["git", "commit", "-m", "seed", "-q"])
    ...     out2 = run_write_file(
    ...         "u.txt",
    ...         None,
    ...         "patch one",
    ...         diff="@@ -1,2 +1,2 @@\\n-hello\\n-world\\n+HELLO\\n+WORLD\\n",
    ...     )
    ...     saved2 = Path("u.txt").read_text(encoding="utf-8")
    ...     os.chdir(old)
    >>> saved2
    'HELLO\\nWORLD\\n'
    >>> out2.startswith("Committed")
    True
    """
    item: dict[str, str] = {"path": path}
    if contents is not None:
        item["contents"] = contents
    if diff is not None:
        item["diff"] = diff
    return run_write_files(files=[item], commit_message=commit_message)


def run_write_files(files: list[dict[str, str]], commit_message: str) -> str:
    """Delegate to the canonical write_files implementation.

    >>> run_write_files([], "noop")
    'ERROR: files must be a non-empty list'
    """
    return run_write_files_core(files, commit_message)
