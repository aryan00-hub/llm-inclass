"""Write one or many files, then commit them to git.

This tool writes UTF-8 contents to project-local files,
stages/commits changes, and optionally runs doctests for python files.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

try:
    from git import Repo
except Exception:  # pragma: no cover - optional local fallback
    Repo = None

from tools.doctests_tool import run_doctests
from tools.is_path_safe import is_path_safe

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "write_files",
        "description": "Write multiple files and commit them with one message.",
        "parameters": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "contents": {"type": "string"},
                        },
                        "required": ["path", "contents"],
                    },
                    "description": "List of file objects each with path and contents.",
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


def _git_commit(paths: list[str], commit_message: str) -> str:
    """Stage paths and create a commit using the docchat message prefix.

    >>> import tempfile, os, subprocess
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = subprocess.check_call(["git", "init", "-q"])
    ...     _ = subprocess.check_call(["git", "config", "user.email", "bot@example.com"])
    ...     _ = subprocess.check_call(["git", "config", "user.name", "Doc Bot"])
    ...     p = Path("a.txt")
    ...     _ = p.write_text("x", encoding="utf-8")
    ...     msg = _git_commit(["a.txt"], "add a")
    ...     os.chdir(old)
    >>> msg.startswith("Committed")
    True
    """
    if Repo is not None:  # pragma: no cover
        repo = Repo(Path.cwd())
        repo.index.add(paths)
        commit = repo.index.commit(f"[docchat] {commit_message}")
        return f"Committed {commit.hexsha[:7]}"

    subprocess.check_call(["git", "add", *paths])
    subprocess.check_call(["git", "commit", "-m", f"[docchat] {commit_message}"])
    sha = (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
        .strip()
    )
    return f"Committed {sha}"


def run_write_files(files: list[dict[str, str]], commit_message: str) -> str:
    """Write all requested files safely, commit once, and run doctests on python files.

    >>> run_write_files([], "noop")
    'ERROR: files must be a non-empty list'
    >>> run_write_files([{"path": "../x.txt", "contents": "bad"}], "x")
    'ERROR: unsafe path: ../x.txt'
    >>> import tempfile, os, subprocess
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = subprocess.check_call(["git", "init", "-q"])
    ...     _ = subprocess.check_call(["git", "config", "user.email", "bot@example.com"])
    ...     _ = subprocess.check_call(["git", "config", "user.name", "Doc Bot"])
    ...     _ = Path("d").mkdir()
    ...     bad = run_write_files([{"path": "d", "contents": "x"}], "bad")
    ...     os.chdir(old)
    >>> bad
    'ERROR: path is a directory: d'
    >>> import tempfile, os, subprocess
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = subprocess.check_call(["git", "init", "-q"])
    ...     _ = subprocess.check_call(["git", "config", "user.email", "bot@example.com"])
    ...     _ = subprocess.check_call(["git", "config", "user.name", "Doc Bot"])
    ...     out = run_write_files(
    ...         [
    ...             {"path": "a.txt", "contents": "hello"},
    ...             {"path": "b.txt", "contents": "world"},
    ...         ],
    ...         "write sample files",
    ...     )
    ...     ok_a = Path("a.txt").read_text(encoding="utf-8")
    ...     ok_b = Path("b.txt").read_text(encoding="utf-8")
    ...     os.chdir(old)
    >>> ok_a
    'hello'
    >>> ok_b
    'world'
    >>> "Committed" in out
    True
    >>> "Doctests for" in out
    False
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = subprocess.check_call(["git", "init", "-q"])
    ...     _ = subprocess.check_call(["git", "config", "user.email", "bot@example.com"])
    ...     _ = subprocess.check_call(["git", "config", "user.name", "Doc Bot"])
    ...     out2 = run_write_files([{"path": "pkg/x.py", "contents": "print(1)\\n"}], "add py")
    ...     made = Path("pkg/x.py").exists()
    ...     os.chdir(old)
    >>> made
    True
    >>> "Doctests for pkg/x.py:" in out2
    True
    >>> "pytest" in out2
    True
    """
    if not isinstance(files, list) or not files:
        return "ERROR: files must be a non-empty list"

    paths: list[str] = []
    py_files: list[str] = []

    for item in files:
        path = str(item.get("path", ""))
        contents = str(item.get("contents", ""))

        if not is_path_safe(path):
            return f"ERROR: unsafe path: {path}"

        file_path = Path(path)
        if file_path.exists() and file_path.is_dir():
            return f"ERROR: path is a directory: {path}"

        if file_path.parent != Path("."):
            file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(contents, encoding="utf-8")
        paths.append(path)

        if file_path.suffix == ".py":
            py_files.append(path)

    commit_status = _git_commit(paths, commit_message)

    lines = [commit_status]
    for py_file in py_files:
        lines.append(f"Doctests for {py_file}:")
        lines.append(run_doctests(py_file))

    return "\n".join(lines)
