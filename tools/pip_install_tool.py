"""Install Python libraries via pip for agent workflows."""

from __future__ import annotations

import re
import subprocess

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "pip_install",
        "description": (
            "Install a Python package with pip3. "
            "Use only when a required dependency is missing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "library_name": {
                    "type": "string",
                    "description": "Package name for pip3 install, e.g. 'requests'.",
                }
            },
            "required": ["library_name"],
        },
    },
}


_LIB_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def run_pip_install(library_name: str) -> str:
    """Install a single package with pip3 and return command output.

    >>> run_pip_install("../bad")
    'ERROR: invalid library name'
    >>> import subprocess as _sub
    >>> old = _sub.run
    >>> class _R:
    ...     def __init__(self, code, out="", err=""):
    ...         self.returncode = code
    ...         self.stdout = out
    ...         self.stderr = err
    >>> _sub.run = lambda *a, **k: _R(0, "ok install")
    >>> run_pip_install("requests")
    'ok install'
    >>> _sub.run = lambda *a, **k: _R(1, "", "install failed")
    >>> run_pip_install("requests")
    'ERROR: install failed'
    >>> _sub.run = old
    """
    name = library_name.strip()
    if not name or not _LIB_RE.fullmatch(name):
        return "ERROR: invalid library name"

    result = subprocess.run(
        ["pip3", "install", name],
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        if output:
            return f"ERROR: {output}"
        return "ERROR: pip install failed"
    return output or f"Installed {name}"
