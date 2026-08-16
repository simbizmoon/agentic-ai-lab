"""Resolve the persistent AIRA parsed-document cache directory."""

from __future__ import annotations

import os
from pathlib import Path


class ParsedDocumentCacheConfigurationError(ValueError):
    """Raised when parsed-document cache configuration is invalid."""


def resolve_parsed_document_cache_directory() -> Path:
    """Return the configured persistent parsed-document cache directory."""

    xdg_cache_home = os.getenv("XDG_CACHE_HOME", "")
    if xdg_cache_home.strip():
        configured_root = Path(xdg_cache_home)
        if not configured_root.is_absolute():
            raise ParsedDocumentCacheConfigurationError(
                "XDG_CACHE_HOME must be an absolute path"
            )
        return configured_root / "aira" / "parsed-documents"
    return Path("~/.cache/aira/parsed-documents").expanduser()
