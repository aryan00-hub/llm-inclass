"""Local image loader tool for multimodal chat.

This tool validates a local image path and converts the file to a data URL for model input.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from tools.is_path_safe import is_path_safe

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "load_image",
        "description": "Load a local image into chat context for visual questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to a local image file.",
                }
            },
            "required": ["path"],
        },
    },
}

# it's not obvious to me that this works based on the test cases,
# and you don't have any documentation proving it works,
# so I'm not awarding credit for it;
# you are welcome to improve it for the second part of the project
# and get points for it

def load_image_as_data_url(path: str) -> str:
    """Return a data URL for a safe local image path.

    >>> import tempfile
    >>> from pathlib import Path
    >>> png = b"\\x89PNG\\r\\n\\x1a\\nabc"
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "x.png"
    ...     _ = p.write_bytes(png)
    ...     import os
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     out = load_image_as_data_url("x.png")
    ...     os.chdir(old)
    >>> out.startswith("data:image/png;base64,")
    True
    >>> load_image_as_data_url("../secret.png")
    Traceback (most recent call last):
    ...
    ValueError: unsafe path
    >>> load_image_as_data_url("missing.png")
    Traceback (most recent call last):
    ...
    ValueError: file not found
    >>> import tempfile, os
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     _ = Path("folder").mkdir()
    ...     try:
    ...         load_image_as_data_url("folder")
    ...     except ValueError as e:
    ...         print(str(e))
    ...     os.chdir(old)
    path is not a file
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "x.txt"
    ...     _ = p.write_text("hello", encoding="utf-8")
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     try:
    ...         load_image_as_data_url("x.txt")
    ...     except ValueError as e:
    ...         print(str(e))
    ...     os.chdir(old)
    not an image file
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "x.gif"
    ...     _ = p.write_bytes(b"GIF89a")
    ...     old = os.getcwd()
    ...     os.chdir(d)
    ...     try:
    ...         load_image_as_data_url("x.gif")
    ...     except ValueError as e:
    ...         print(str(e))
    ...     os.chdir(old)
    GIF images are not supported; use PNG or JPG
    """
    if not is_path_safe(path):
        raise ValueError("unsafe path")

    file_path = Path(path)
    if not file_path.exists():
        raise ValueError("file not found")
    if not file_path.is_file():
        raise ValueError("path is not a file")

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError("not an image file")
    if file_path.suffix.lower() == ".gif":
        raise ValueError("GIF images are not supported; use PNG or JPG")

    raw = file_path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
