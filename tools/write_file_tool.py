"""Tool for writing multiple files and committing them via git."""

import os

import git

TOOL_SPEC_WRITE_FILES = {
    "type": "function",
    "function": {
        "name": "write_files",
        "description": (
            "Write multiple files to disk and commit them all in one git commit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "description": "List of files to write, each with a path and contents key.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "contents": {"type": "string"},
                        },
                        "required": ["path", "contents"],
                    },
                },
                "commit_message": {
                    "type": "string",
                    "description": "Git commit message (will be prefixed with [docchat]).",
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
            "Write a single file to disk, git commit it, "
            "and run doctests if it is a Python file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to write the file to.",
                },
                "contents": {
                    "type": "string",
                    "description": "UTF-8 text contents to write.",
                },
                "commit_message": {
                    "type": "string",
                    "description": "Git commit message (will be prefixed with [docchat]).",
                },
            },
            "required": ["path", "contents", "commit_message"],
        },
    },
}


def is_path_safe(path: str) -> bool:
    """Return True if path is relative and contains no directory traversal.

    >>> is_path_safe("hello.py")
    True
    >>> is_path_safe("/abs/path.py")
    False
    >>> is_path_safe("../escape.py")
    False
    >>> is_path_safe("a/b/../c.py")
    False
    """
    if path.startswith("/"):
        return False
    if ".." in path.split("/"):
        return False
    return True


def run_write_files(files: list[dict], commit_message: str) -> str:
    """Write each file in the list and commit them all together.

    >>> import tempfile, os, git as gitlib
    >>> with tempfile.TemporaryDirectory() as d:
    ...     repo = gitlib.Repo.init(d)
    ...     _ = repo.config_writer().set_value("user", "name", "test").release()
    ...     _ = repo.config_writer().set_value("user", "email", "t@t.com").release()
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     result = run_write_files([{"path": "hello.txt", "contents": "hi"}], "add hello")
    ...     os.chdir(old)
    >>> "hello.txt" in result
    True
    >>> with tempfile.TemporaryDirectory() as d:
    ...     repo = gitlib.Repo.init(d)
    ...     _ = repo.config_writer().set_value("user", "name", "test").release()
    ...     _ = repo.config_writer().set_value("user", "email", "t@t.com").release()
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     result = run_write_files([{"path": "../bad.txt", "contents": "x"}], "bad")
    ...     os.chdir(old)
    >>> result
    'ERROR: unsafe path: ../bad.txt'
    """
    for f in files:
        if not is_path_safe(f["path"]):
            return f"ERROR: unsafe path: {f['path']}"

    written = []
    for f in files:
        path = f["path"]
        contents = f["contents"]
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(contents)
        written.append(path)

    repo = git.Repo(".")
    repo.index.add(written)
    repo.index.commit(f"[docchat] {commit_message}")

    return f"Written and committed: {', '.join(written)}"


def run_write_file(path: str, contents: str, commit_message: str) -> str:
    """Write a single file, commit it, and run doctests if it is a Python file.

    >>> import tempfile, os, git as gitlib
    >>> with tempfile.TemporaryDirectory() as d:
    ...     repo = gitlib.Repo.init(d)
    ...     _ = repo.config_writer().set_value("user", "name", "test").release()
    ...     _ = repo.config_writer().set_value("user", "email", "t@t.com").release()
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     result = run_write_file("note.txt", "hello", "add note")
    ...     os.chdir(old)
    >>> "note.txt" in result
    True
    >>> run_write_file("/etc/passwd", "x", "bad")
    'ERROR: unsafe path: /etc/passwd'
    """
    return run_write_files([{"path": path, "contents": contents}], commit_message)

