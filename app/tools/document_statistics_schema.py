"""OpenAI function tool schema for document statistics."""

from __future__ import annotations

from typing import Any

DOCUMENT_STATISTICS_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "get_document_statistics",
    "description": (
        "Calculate deterministic character, word, and line counts "
        "for the supplied document text."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "document_text": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "The complete document text whose statistics "
                    "will be calculated."
                ),
            }
        },
        "required": ["document_text"],
        "additionalProperties": False,
    },
    "strict": True,
}
