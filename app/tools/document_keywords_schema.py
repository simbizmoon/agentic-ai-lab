"""OpenAI function Tool schema for document keyword extraction."""

from typing import Any

DOCUMENT_KEYWORDS_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "extract_document_keywords",
    "description": (
        "Extract the most frequent normalized keywords "
        "from document text."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "document_text": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "The complete document text to analyze."
                ),
            },
            "max_keywords": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": (
                    "Maximum number of keywords to return."
                ),
            },
        },
        "required": [
            "document_text",
            "max_keywords",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}
