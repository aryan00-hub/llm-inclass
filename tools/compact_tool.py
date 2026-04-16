"""Local compact tool spec for summarizing conversation history.

This tool asks the chat agent to compress prior messages into a short summary to reduce context size.
"""

from __future__ import annotations

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "compact",
        "description": (
            "Summarize prior chat history into 1-5 lines and replace stored context. "
            "Use this when conversations get long to reduce token usage, speed up replies, "
            "and keep the model focused on recent relevant context."
        ),
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
    >>> 'compact' in compact_usage_text()
    True
    """
    return "/compact"
