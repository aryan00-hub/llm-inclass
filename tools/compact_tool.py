"""Local compact tool spec for summarizing conversation history.

This tool asks the chat agent to compress prior messages into a short summary to reduce context size.
"""

from __future__ import annotations

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "compact",
        "description": "Summarize current chat history into 1-5 lines and replace memory.",
        # you also need in the description why/when to use a tool
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def compact_usage_text() -> str:
    """Return one-line usage guidance for the compact tool.

    >>> compact_usage_text()
    '/compact'
    """
    return "/compact"
    # the code for actually compacting should be here
