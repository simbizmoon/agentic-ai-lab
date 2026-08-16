from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.research.local_document_access_policy import LocalDocumentAccessResult
from app.research.parsed_document_cache import (
    PARSED_DOCUMENT_CACHE_SCHEMA_VERSION,
    ParsedDocumentCacheEntry,
    ParsedDocumentCacheIdentity,
    ParsedDocumentParserIdentity,
    build_local_document_parser_identity,
    identity_from_validated_source,
)
from app.schemas.parsed_local_document import ParsedLocalDocument
from app.schemas.research_source_document import ResearchSourceContentType


def _digest(value: bytes = b"same bytes") -> str:
    return hashlib.sha256(value).hexdigest()


def _identity(
    *, parser: ParsedDocumentParserIdentity | None = None
) -> ParsedDocumentCacheIdentity:
    return ParsedDocumentCacheIdentity(
        raw_content_sha256=_digest(),
        raw_file_size_bytes=10,
        parser=parser or build_local_document_parser_identity(".txt"),
    )


def test_same_raw_and_parser_identity_have_same_key() -> None:
    assert _identity().cache_key == _identity().cache_key


def test_identity_is_path_neutral_for_same_bytes() -> None:
    first = identity_from_validated_source(
        LocalDocumentAccessResult(
            resolved_path=Path("/one/document.txt"),
            file_size_bytes=10,
            content_sha256=_digest(),
        )
    )
    second = identity_from_validated_source(
        LocalDocumentAccessResult(
            resolved_path=Path("/two/copy.txt"),
            file_size_bytes=10,
            content_sha256=_digest(),
        )
    )

    assert first == second
    assert first.cache_key == second.cache_key
    assert "path" not in first.model_dump_json()
    assert "filename" not in first.model_dump_json()


def test_validated_text_and_markdown_sources_have_different_identity() -> None:
    text = identity_from_validated_source(
        LocalDocumentAccessResult(
            resolved_path=Path("/documents/source.txt"),
            file_size_bytes=10,
            content_sha256=_digest(),
        )
    )
    markdown = identity_from_validated_source(
        LocalDocumentAccessResult(
            resolved_path=Path("/documents/source.md"),
            file_size_bytes=10,
            content_sha256=_digest(),
        )
    )

    assert text.parser != markdown.parser
    assert text.cache_key != markdown.cache_key


def test_identity_helper_requires_access_result() -> None:
    with pytest.raises(TypeError, match="LocalDocumentAccessResult"):
        identity_from_validated_source(Path("/documents/source.txt"))  # type: ignore[arg-type]


def test_raw_content_change_changes_key() -> None:
    changed = _identity().model_copy(update={"raw_content_sha256": _digest(b"changed")})
    assert changed.cache_key != _identity().cache_key


def test_raw_file_size_change_changes_key() -> None:
    changed = _identity().model_copy(update={"raw_file_size_bytes": 11})
    assert changed.cache_key != _identity().cache_key


def test_parser_revision_change_changes_key() -> None:
    parser = build_local_document_parser_identity(".txt").model_copy(
        update={"parser_revision": 2}
    )
    assert _identity(parser=parser).cache_key != _identity().cache_key


def test_text_and_markdown_have_different_keys() -> None:
    text = _identity(parser=build_local_document_parser_identity(".txt"))
    markdown = _identity(parser=build_local_document_parser_identity(".md"))
    assert text.cache_key != markdown.cache_key


def test_pdf_dependency_change_changes_key() -> None:
    first = _identity(
        parser=build_local_document_parser_identity(
            ".pdf", pdf_dependency_identity="pypdf==1"
        )
    )
    second = _identity(
        parser=build_local_document_parser_identity(
            ".pdf", pdf_dependency_identity="pypdf==2"
        )
    )
    assert first.cache_key != second.cache_key


def test_parser_configuration_change_changes_key() -> None:
    parser = build_local_document_parser_identity(".txt").model_copy(
        update={"configuration_identity": "utf8-exact-v2"}
    )
    assert _identity(parser=parser).cache_key != _identity().cache_key


def test_entry_rejects_key_or_content_type_mismatch() -> None:
    identity = _identity()
    parsed = ParsedLocalDocument(
        content="# Heading",
        content_type=ResearchSourceContentType.MARKDOWN,
    )
    with pytest.raises(ValidationError, match="content type"):
        ParsedDocumentCacheEntry(
            schema_version=PARSED_DOCUMENT_CACHE_SCHEMA_VERSION,
            cache_key=identity.cache_key,
            identity=identity,
            parsed_document=parsed,
        )

    parsed = ParsedLocalDocument(
        content="text",
        content_type=ResearchSourceContentType.TEXT,
    )
    with pytest.raises(ValidationError, match="cache key"):
        ParsedDocumentCacheEntry(
            schema_version=PARSED_DOCUMENT_CACHE_SCHEMA_VERSION,
            cache_key="0" * 64,
            identity=identity,
            parsed_document=parsed,
        )


def test_identity_and_entry_are_strict_and_frozen() -> None:
    identity = _identity()
    with pytest.raises(ValidationError):
        ParsedDocumentCacheIdentity.model_validate(
            {**identity.model_dump(), "unknown": "field"}
        )
    with pytest.raises(ValidationError):
        identity.raw_file_size_bytes = 11  # type: ignore[misc]
