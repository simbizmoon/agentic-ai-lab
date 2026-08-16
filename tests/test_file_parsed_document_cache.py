from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from app.research.file_parsed_document_cache import FileParsedDocumentCache
from app.research.parsed_document_cache import (
    ParsedDocumentCacheEntryTooLargeError,
    ParsedDocumentCacheError,
    ParsedDocumentCacheIdentity,
    build_local_document_parser_identity,
)
from app.schemas.parsed_local_document import ParsedLocalDocument
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentSection,
)


def _identity(
    suffix: str = ".txt", *, raw: bytes = b"cached text"
) -> ParsedDocumentCacheIdentity:
    return ParsedDocumentCacheIdentity(
        raw_content_sha256=hashlib.sha256(raw).hexdigest(),
        raw_file_size_bytes=len(raw),
        parser=build_local_document_parser_identity(
            suffix,
            pdf_dependency_identity="pypdf==test" if suffix == ".pdf" else None,
        ),
    )


def _text_document(content: str = "cached text") -> ParsedLocalDocument:
    return ParsedLocalDocument(
        content=content,
        content_type=ResearchSourceContentType.TEXT,
    )


def _entry_path(
    cache: FileParsedDocumentCache, identity: ParsedDocumentCacheIdentity
) -> Path:
    return cache.directory / f"{identity.cache_key}.json"


def _lock_path(
    cache: FileParsedDocumentCache, identity: ParsedDocumentCacheIdentity
) -> Path:
    return cache.directory / f".{identity.cache_key}.lock"


def test_missing_entry_is_cache_miss(tmp_path: Path) -> None:
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    assert cache.get(_identity()) is None


def test_put_get_and_second_instance_persistent_hit(tmp_path: Path) -> None:
    directory = tmp_path / "cache"
    identity = _identity()
    parsed = _text_document()
    FileParsedDocumentCache(directory=directory).put(identity, parsed)

    loaded = FileParsedDocumentCache(directory=directory).get(identity)
    assert loaded == parsed
    assert loaded is not parsed


@pytest.mark.parametrize(
    "payload",
    [b"{", b"\xff\xfe", b'{"schema_version":1,"schema_version":1}'],
    ids=["malformed-json", "invalid-utf8", "duplicate-key"],
)
def test_corrupt_payload_is_cache_miss(tmp_path: Path, payload: bytes) -> None:
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    identity = _identity()
    cache.put(identity, _text_document())
    _entry_path(cache, identity).write_bytes(payload)
    assert cache.get(identity) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", 2), ("cache_key", "0" * 64)],
)
def test_schema_or_key_mismatch_is_cache_miss(
    tmp_path: Path, field: str, value: object
) -> None:
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    identity = _identity()
    cache.put(identity, _text_document())
    path = _entry_path(cache, identity)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cache.get(identity) is None


def test_requested_identity_mismatch_is_cache_miss(tmp_path: Path) -> None:
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    identity = _identity()
    changed = _identity(raw=b"changed text")
    cache.put(identity, _text_document())
    _entry_path(cache, identity).replace(_entry_path(cache, changed))
    assert cache.get(changed) is None


def test_oversized_stored_entry_is_cache_miss(tmp_path: Path) -> None:
    cache = FileParsedDocumentCache(
        directory=tmp_path / "cache", maximum_entry_bytes=128
    )
    identity = _identity()
    _entry_path(cache, identity).write_bytes(b"x" * 129)
    assert cache.get(identity) is None


def test_oversized_put_is_explicit_error(tmp_path: Path) -> None:
    cache = FileParsedDocumentCache(
        directory=tmp_path / "cache", maximum_entry_bytes=128
    )
    with pytest.raises(ParsedDocumentCacheEntryTooLargeError):
        cache.put(_identity(), _text_document())


def test_private_modes_under_permissive_umask(tmp_path: Path) -> None:
    previous_umask = os.umask(0)
    try:
        cache = FileParsedDocumentCache(directory=tmp_path / "cache")
        identity = _identity()
        cache.put(identity, _text_document())
    finally:
        os.umask(previous_umask)
    assert stat.S_IMODE(cache.directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(_entry_path(cache, identity).stat().st_mode) == 0o600
    assert stat.S_IMODE(_lock_path(cache, identity).stat().st_mode) == 0o600


def test_existing_broad_directory_is_normalized(tmp_path: Path) -> None:
    directory = tmp_path / "cache"
    directory.mkdir(mode=0o777)
    directory.chmod(0o777)
    cache = FileParsedDocumentCache(directory=directory)
    assert stat.S_IMODE(cache.directory.stat().st_mode) == 0o700


def test_temp_file_is_private_before_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    observed_modes: list[int] = []
    original_replace = os.replace

    def recording_replace(source: Path, destination: Path) -> None:
        observed_modes.append(stat.S_IMODE(Path(source).stat().st_mode))
        original_replace(source, destination)

    monkeypatch.setattr(
        "app.research.file_parsed_document_cache.os.replace", recording_replace
    )
    cache.put(_identity(), _text_document())
    assert observed_modes == [0o600]


def test_directory_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    directory = tmp_path / "cache"
    try:
        directory.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(ParsedDocumentCacheError, match="must not be a symlink"):
        FileParsedDocumentCache(directory=directory)


@pytest.mark.parametrize("kind", ["entry", "lock"])
def test_entry_and_lock_symlinks_are_rejected(tmp_path: Path, kind: str) -> None:
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    identity = _identity()
    target = tmp_path / "external"
    target.write_text("unchanged", encoding="utf-8")
    path = (
        _entry_path(cache, identity) if kind == "entry" else _lock_path(cache, identity)
    )
    try:
        path.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(ParsedDocumentCacheError, match="unsafe|symlink"):
        cache.put(identity, _text_document())
    assert target.read_text(encoding="utf-8") == "unchanged"


def test_directory_chmod_failure_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_chmod(path: Path, mode: int) -> None:
        raise OSError("chmod failed")

    monkeypatch.setattr("app.research.file_parsed_document_cache.os.chmod", fail_chmod)
    with pytest.raises(ParsedDocumentCacheError, match="could not be prepared"):
        FileParsedDocumentCache(directory=tmp_path / "cache")


@pytest.mark.parametrize("operation", ["fsync", "replace"])
def test_write_failures_are_explicit_and_temp_is_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")

    def fail(*args: object) -> None:
        raise OSError(f"{operation} failed")

    monkeypatch.setattr(f"app.research.file_parsed_document_cache.os.{operation}", fail)
    with pytest.raises(ParsedDocumentCacheError, match="could not be written"):
        cache.put(_identity(), _text_document())
    assert not list(cache.directory.glob("*.tmp"))


def test_genuine_read_failure_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    identity = _identity()
    cache.put(identity, _text_document())

    def fail_read(path: Path) -> bytes:
        raise OSError("read failed")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(ParsedDocumentCacheError, match="could not be read"):
        cache.get(identity)


@pytest.mark.parametrize(
    ("suffix", "content_type", "content", "section"),
    [
        (
            ".pdf",
            ResearchSourceContentType.PDF_TEXT,
            "First page\n\nThird page",
            ResearchSourceDocumentSection(
                section_id="page-003",
                content="Third page",
                order=2,
                start_character=12,
                end_character=22,
                metadata={"page_number": "3"},
            ),
        ),
        (
            ".hwpx",
            ResearchSourceContentType.HWPX_TEXT,
            "First section\n\nSecond section",
            ResearchSourceDocumentSection(
                section_id="hwpx-section-002",
                content="Second section",
                order=2,
                start_character=15,
                end_character=29,
                metadata={
                    "hwpx_section_index": "2",
                    "hwpx_package_path": "Contents/section1.xml",
                },
            ),
        ),
    ],
)
def test_structured_provenance_round_trip(
    tmp_path: Path,
    suffix: str,
    content_type: ResearchSourceContentType,
    content: str,
    section: ResearchSourceDocumentSection,
) -> None:
    first_content = content.split("\n\n", maxsplit=1)[0]
    parsed = ParsedLocalDocument(
        content=content,
        content_type=content_type,
        sections=[
            ResearchSourceDocumentSection(
                section_id="page-001" if suffix == ".pdf" else "hwpx-section-001",
                content=first_content,
                order=1,
                start_character=0,
                end_character=len(first_content),
                metadata=(
                    {"page_number": "1"}
                    if suffix == ".pdf"
                    else {
                        "hwpx_section_index": "1",
                        "hwpx_package_path": "Contents/section0.xml",
                    }
                ),
            ),
            section,
        ],
    )
    identity = _identity(suffix, raw=content.encode())
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    cache.put(identity, parsed)
    loaded = cache.get(identity)
    assert loaded == parsed
    assert loaded is not None
    assert (
        loaded.content[section.start_character : section.end_character]
        == section.content
    )
    serialized = loaded.model_dump_json()
    for forbidden in ("local_path", "source_id", "execution_id", "research_origin"):
        assert forbidden not in serialized
