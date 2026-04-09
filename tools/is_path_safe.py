"""Path safety helper for all local file tools.

This module prevents absolute-path reads and directory traversal attempts so
tool calls stay inside the current project folder.
"""

from __future__ import annotations

import os
from pathlib import PurePosixPath


def is_path_safe(path: str) -> bool:
    """Return True only for project-local paths without absolute or traversal segments.

    >>> is_path_safe("README.md")
    True
    >>> is_path_safe("docs/*.md")
    True
    >>> is_path_safe("/etc/passwd")
    False
    >>> is_path_safe("../secret.txt")
    False
    >>> is_path_safe("a/../b.txt")
    False
    >>> is_path_safe(r"..\\secret.txt")
    False
    >>> is_path_safe("")
    False
    """
    if not path:
        return False

    if os.path.isabs(path):
        return False

    norm = path.replace("\\", "/")
    parts = PurePosixPath(norm).parts
    return ".." not in parts
