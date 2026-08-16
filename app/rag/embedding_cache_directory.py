"""Resolve the persistent AIRA embedding cache directory."""

from __future__ import annotations

import os
from pathlib import Path


class EmbeddingCacheConfigurationError(ValueError):
    """Raised when embedding cache configuration is invalid."""


def resolve_embedding_cache_directory() -> Path:
    """Return the configured persistent embedding cache directory."""

    xdg_cache_home = os.getenv("XDG_CACHE_HOME", "")
    if xdg_cache_home.strip():
        configured_root = Path(xdg_cache_home)
        if not configured_root.is_absolute():
            raise EmbeddingCacheConfigurationError(
                "XDG_CACHE_HOME must be an absolute path"
            )
        return configured_root / "aira" / "embeddings"

    return Path("~/.cache/aira/embeddings").expanduser()
