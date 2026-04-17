"""Write or update files, then commit them to git.

This tool supports either full contents writes or diff-based updates,
stages/commits changes, and optionally runs doctests for python files.
"""

from __future__ import annotations

from pathlib import Path

from git import Repo

from tools.doctests_tool import run_doctests
from tools.is_path_safe import is_path_safe

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "write_files",
        "description": (
            "Write or update multiple files and commit them with one message. "
            "Use 'contents' for full-file rewrites and 'diff' for smaller updates."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
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
                                "description": (
                                    "Optional unified diff patch for updating an existing file."
                                ),
                            },
                        },
                        "required": ["path"],
                    },
                    "description": "List of file objects; each item must include path and either contents or diff.",
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
    repo = Repo(Path.cwd())
    repo.index.add(paths)
    commit = repo.index.commit(f"[docchat] {commit_message}")
    return f"Committed {commit.hexsha[:7]}"


def _find_subsequence(haystack: list[str], needle: list[str], start: int = 0) -> int:
    """Return index of first exact needle match in haystack at/after start.

    >>> _find_subsequence(["a", "b", "c"], ["b", "c"])
    1
    >>> _find_subsequence(["a", "b"], ["x"])
    -1
    """
    if not needle:
        return start
    limit = len(haystack) - len(needle) + 1
    for idx in range(max(0, start), max(0, limit)):
        if haystack[idx: idx + len(needle)] == needle:
            return idx
    return -1


def _apply_unified_diff(original: str, diff_text: str) -> str:
    """Apply a unified diff to text using content matching instead of line numbers.

    This intentionally ignores hunk line numbers so it still works with mildly
    broken LLM-generated diffs that have correct content but wrong counts.

    >>> src = "a\\nline one\\nline two\\nz\\n"
    >>> diff = \"\"\"@@ -2,2 +2,2 @@
    ... -line one
    ... -line two
    ... +line 1
    ... +line 2
    ... \"\"\"
    >>> _apply_unified_diff(src, diff)
    'a\\nline 1\\nline 2\\nz\\n'
    >>> _apply_unified_diff("x\\n", "")
    Traceback (most recent call last):
    ...
    ValueError: empty diff
    >>> _apply_unified_diff("x\\n", "@@ -1,1 +1,1 @@\\n-y\\n+z\\n")
    Traceback (most recent call last):
    ...
    ValueError: diff hunk not found in file
    """
    if not diff_text.strip():
        raise ValueError("empty diff")

    lines = original.splitlines(keepends=True)
    diff_lines = diff_text.splitlines(keepends=True)
    cursor = 0
    i = 0
    saw_hunk = False

    while i < len(diff_lines):
        if not diff_lines[i].startswith("@@"):
            i += 1
            continue
        saw_hunk = True
        i += 1

        old_block: list[str] = []
        new_block: list[str] = []
        while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
            line = diff_lines[i]
            if not line:
                i += 1
                continue
            prefix = line[:1]
            body = line[1:] if prefix in {" ", "+", "-"} else line
            if prefix in {" ", "-"}:
                old_block.append(body)
            if prefix in {" ", "+"}:
                new_block.append(body)
            i += 1

        match = _find_subsequence(lines, old_block, cursor)
        if match < 0:
            raise ValueError("diff hunk not found in file")
        lines[match: match + len(old_block)] = new_block
        cursor = match + len(new_block)

    if not saw_hunk:
        raise ValueError("invalid diff format")
    return "".join(lines)


def _render_file_contents(path: Path, item: dict[str, str]) -> str:
    """Return final file text from either contents or diff input.

    >>> _render_file_contents(Path("x.txt"), {"contents": "hello"})
    'hello'
    >>> _render_file_contents(Path("x.txt"), {})
    Traceback (most recent call last):
    ...
    ValueError: each file entry must include either contents or diff
    """
    has_contents = "contents" in item and item.get("contents") is not None
    has_diff = "diff" in item and item.get("diff") is not None

    if has_contents and has_diff:
        raise ValueError("provide either contents or diff, not both")
    if not has_contents and not has_diff:
        raise ValueError("each file entry must include either contents or diff")

    if has_contents:
        return str(item.get("contents", ""))

    if not path.exists():
        raise ValueError(f"file not found for diff update: {path}")
    if path.is_dir():
        raise ValueError(f"path is a directory: {path}")
    old_text = path.read_text(encoding="utf-8")
    return _apply_unified_diff(old_text, str(item.get("diff", "")))


def run_write_files(files: list[dict[str, str]], commit_message: str) -> str:
    """Write all requested files safely, commit once, and run doctests on python files.

    >>> run_write_files([], "noop")
    'ERROR: files must be a non-empty list'
    >>> run_write_files([{"path": "../x.txt", "contents": "bad"}], "x")
    'ERROR: unsafe path: ../x.txt'
    >>> run_write_files([{"path": "x.txt"}], "missing mode")
    'ERROR: each file entry must include either contents or diff'
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
    >>> "passed" in out2.lower()
    True
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = subprocess.check_call(["git", "init", "-q"])
    ...     _ = subprocess.check_call(["git", "config", "user.email", "bot@example.com"])
    ...     _ = subprocess.check_call(["git", "config", "user.name", "Doc Bot"])
    ...     _ = Path("u.txt").write_text("a\\nb\\n", encoding="utf-8")
    ...     _ = subprocess.check_call(["git", "add", "u.txt"])
    ...     _ = subprocess.check_call(["git", "commit", "-m", "seed", "-q"])
    ...     out3 = run_write_files(
    ...         [{"path": "u.txt", "diff": "@@ -1,2 +1,2 @@\\n-a\\n-b\\n+A\\n+B\\n"}],
    ...         "patch u",
    ...     )
    ...     patched = Path("u.txt").read_text(encoding="utf-8")
    ...     os.chdir(old)
    >>> patched
    'A\\nB\\n'
    >>> "Committed" in out3
    True
    """
    if not isinstance(files, list) or not files:
        return "ERROR: files must be a non-empty list"

    paths: list[str] = []
    py_files: list[str] = []

    for item in files:
        path = str(item.get("path", ""))
        if not is_path_safe(path):
            return f"ERROR: unsafe path: {path}"

        file_path = Path(path)
        if file_path.exists() and file_path.is_dir():
            return f"ERROR: path is a directory: {path}"

        try:
            rendered = _render_file_contents(file_path, item)
        except ValueError as exc:
            return f"ERROR: {exc}"

        if file_path.parent != Path("."):
            file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(rendered, encoding="utf-8")
        paths.append(path)

        if file_path.suffix == ".py":
            py_files.append(path)

    commit_status = _git_commit(paths, commit_message)

    lines = [commit_status]
    for py_file in py_files:
        lines.append(f"Doctests for {py_file}:")
        lines.append(run_doctests(py_file))

    return "\n".join(lines)
