"""Parsed-document cache decorator for validated local sources."""

from __future__ import annotations

from pathlib import Path

from app.research.local_document_access_policy import LocalDocumentAccessResult
from app.research.local_document_parser import LocalDocumentParser
from app.research.parsed_document_cache import (
    ParsedDocumentCache,
    ParsedDocumentCacheEntryTooLargeError,
    identity_from_validated_source,
)
from app.schemas.parsed_local_document import ParsedLocalDocument


class CachingLocalDocumentParser(LocalDocumentParser):
    """Avoid repeated parsing for identical validated source identities."""

    def __init__(
        self,
        *,
        parser: LocalDocumentParser,
        cache: ParsedDocumentCache,
    ) -> None:
        if not isinstance(parser, LocalDocumentParser):
            raise TypeError("parser must be a LocalDocumentParser")
        if not isinstance(cache, ParsedDocumentCache):
            raise TypeError("cache must be a ParsedDocumentCache")
        self._parser = parser
        self._cache = cache

    def parse(self, source: LocalDocumentAccessResult) -> ParsedLocalDocument:
        """Return a cached parse or compute it once under a per-key lock."""

        if not isinstance(source, LocalDocumentAccessResult):
            raise TypeError("source must be a LocalDocumentAccessResult")
        identity = identity_from_validated_source(source)
        cached = self._cache.get(identity)
        if cached is not None:
            return cached

        with self._cache.exclusive_entry(identity) as entry:
            cached = entry.get()
            if cached is not None:
                return cached
            parsed = self._parser.parse(source)
            if parsed.content_type != identity.parser.content_type:
                raise ValueError(
                    "parsed document content type does not match parser identity"
                )
            try:
                entry.put(parsed)
            except ParsedDocumentCacheEntryTooLargeError:
                return parsed.model_copy(deep=True)
            return parsed.model_copy(deep=True)

    def parse_path(self, path: Path) -> ParsedLocalDocument:
        """Keep the bare development path on the uncached parser boundary."""

        return self._parser.parse_path(path)
