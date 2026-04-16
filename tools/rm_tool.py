"""Remove files with safe globs and commit the deletion.

This tool deletes matched files via os.remove, blocks unsafe paths,
and commits removals with a standard docchat message.
"""

from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path

from git import Repo

from tools.is_path_safe import is_path_safe

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "rm",
        "description": "Delete one or more files using a safe path or glob and commit the change.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path or glob to remove.",
                }
            },
            "required": ["path"],
        },
    },
}


def run_rm(path: str) -> str:
    """Remove files matched by path/glob and create a commit.

    >>> run_rm("../*.txt")
    'ERROR: unsafe path'
    >>> import tempfile, os, subprocess
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = subprocess.check_call(["git", "init", "-q"])
    ...     _ = subprocess.check_call(["git", "config", "user.email", "bot@example.com"])
    ...     _ = subprocess.check_call(["git", "config", "user.name", "Doc Bot"])
    ...     p1 = Path("a.txt")
    ...     p2 = Path("b.txt")
    ...     _ = p1.write_text("a", encoding="utf-8")
    ...     _ = p2.write_text("b", encoding="utf-8")
    ...     _ = subprocess.check_call(["git", "add", "a.txt", "b.txt"])
    ...     _ = subprocess.check_call(["git", "commit", "-m", "seed", "-q"])
    ...     out = run_rm("*.txt")
    ...     missing = (not p1.exists()) and (not p2.exists())
    ...     os.chdir(old)
    >>> missing
    True
    >>> out.startswith("Removed 2 file(s)")
    True
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = subprocess.check_call(["git", "init", "-q"])
    ...     out2 = run_rm("*.txt")
    ...     os.chdir(old)
    >>> out2
    'ERROR: no files matched'
    """
    if not is_path_safe(path):
        return "ERROR: unsafe path"

    candidates = sorted(glob.glob(path))
    files = [p for p in candidates if Path(p).is_file()]
    if not files:
        return "ERROR: no files matched"

    for file_path in files:
        os.remove(file_path)

    repo = Repo(Path.cwd())
    repo.index.remove(files, working_tree=True)
    repo.index.commit(f"[docchat] rm {path}")
    return f"Removed {len(files)} file(s) and committed [docchat] rm {path}"
