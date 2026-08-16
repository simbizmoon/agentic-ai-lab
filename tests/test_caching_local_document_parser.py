"""Tests for validated-source parsed-document caching composition."""

from __future__ import annotations

import multiprocessing
import time
from pathlib import Path
from queue import Empty

import pytest

from app.research.caching_local_document_parser import CachingLocalDocumentParser
from app.research.file_parsed_document_cache import FileParsedDocumentCache
from app.research.local_document_access_policy import (
    LocalDocumentAccessGate,
    LocalDocumentAccessPolicy,
    LocalDocumentAccessResult,
)
from app.research.local_document_parser import LocalDocumentParser
from app.research.parsed_document_cache import (
    ParsedDocumentCacheError,
    identity_from_validated_source,
)
from app.schemas.parsed_local_document import ParsedLocalDocument
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentSection,
)


def _validated(path: Path, *, root: Path) -> LocalDocumentAccessResult:
    return LocalDocumentAccessGate(
        LocalDocumentAccessPolicy(
            allowed_roots=(root.resolve(),),
            maximum_file_bytes=1024 * 1024,
        )
    ).validate(path)


class RecordingLocalDocumentParser(LocalDocumentParser):
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.calls: list[LocalDocumentAccessResult] = []
        self._failure = failure

    def parse(self, source: LocalDocumentAccessResult) -> ParsedLocalDocument:
        self.calls.append(source)
        if self._failure is not None:
            raise self._failure
        return super().parse(source)


class WrongContentTypeParser(LocalDocumentParser):
    def parse(self, source: LocalDocumentAccessResult) -> ParsedLocalDocument:
        return ParsedLocalDocument(
            content="wrong",
            content_type=ResearchSourceContentType.MARKDOWN,
        )


class ProcessRecordingParser(LocalDocumentParser):
    def __init__(self, counter_path: Path) -> None:
        self._counter_path = counter_path

    def parse(self, source: LocalDocumentAccessResult) -> ParsedLocalDocument:
        with self._counter_path.open("a", encoding="utf-8") as counter:
            counter.write("parsed\n")
            counter.flush()
        time.sleep(0.2)
        return ParsedLocalDocument(
            content="shared process content",
            content_type=ResearchSourceContentType.TEXT,
        )


def _process_parse(
    cache_directory: Path,
    counter_path: Path,
    source: LocalDocumentAccessResult,
    start: multiprocessing.synchronize.Event,
    results: multiprocessing.queues.Queue,
) -> None:
    start.wait()
    parsed = CachingLocalDocumentParser(
        parser=ProcessRecordingParser(counter_path),
        cache=FileParsedDocumentCache(directory=cache_directory),
    ).parse(source)
    results.put(parsed.content)


def test_miss_parses_once_and_second_call_hits(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("cached local content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    parser = RecordingLocalDocumentParser()
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    caching_parser = CachingLocalDocumentParser(parser=parser, cache=cache)

    first = caching_parser.parse(source)
    second = caching_parser.parse(source)

    assert first == second
    assert parser.calls == [source]
    assert cache.get(identity_from_validated_source(source)) == first


def test_new_parser_and_cache_instance_gets_persistent_hit(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("persistent parsed content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    directory = tmp_path / "cache"
    first_parser = RecordingLocalDocumentParser()
    expected = CachingLocalDocumentParser(
        parser=first_parser,
        cache=FileParsedDocumentCache(directory=directory),
    ).parse(source)
    second_parser = RecordingLocalDocumentParser()

    actual = CachingLocalDocumentParser(
        parser=second_parser,
        cache=FileParsedDocumentCache(directory=directory),
    ).parse(source)

    assert actual == expected
    assert first_parser.calls == [source]
    assert second_parser.calls == []


def test_changed_source_identity_is_a_miss(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("first", encoding="utf-8")
    first_source = _validated(source_path, root=tmp_path)
    parser = RecordingLocalDocumentParser()
    caching_parser = CachingLocalDocumentParser(
        parser=parser,
        cache=FileParsedDocumentCache(directory=tmp_path / "cache"),
    )
    caching_parser.parse(first_source)
    source_path.write_text("second and changed", encoding="utf-8")
    second_source = _validated(source_path, root=tmp_path)

    caching_parser.parse(second_source)

    assert parser.calls == [first_source, second_source]


def test_parser_identity_change_is_a_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("identity content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    parser = RecordingLocalDocumentParser()
    caching_parser = CachingLocalDocumentParser(
        parser=parser,
        cache=FileParsedDocumentCache(directory=tmp_path / "cache"),
    )
    caching_parser.parse(source)
    original_identity = identity_from_validated_source(source)
    changed_identity = original_identity.model_copy(
        update={
            "parser": original_identity.parser.model_copy(update={"parser_revision": 2})
        }
    )
    monkeypatch.setattr(
        "app.research.caching_local_document_parser.identity_from_validated_source",
        lambda _: changed_identity,
    )

    caching_parser.parse(source)

    assert parser.calls == [source, source]


def test_text_and_markdown_do_not_collide(tmp_path: Path) -> None:
    text_path = tmp_path / "source.txt"
    markdown_path = tmp_path / "source.md"
    content = "identical bytes"
    text_path.write_text(content, encoding="utf-8")
    markdown_path.write_text(content, encoding="utf-8")
    text_source = _validated(text_path, root=tmp_path)
    markdown_source = _validated(markdown_path, root=tmp_path)
    parser = RecordingLocalDocumentParser()
    caching_parser = CachingLocalDocumentParser(
        parser=parser,
        cache=FileParsedDocumentCache(directory=tmp_path / "cache"),
    )

    text = caching_parser.parse(text_source)
    markdown = caching_parser.parse(markdown_source)

    assert text.content_type is ResearchSourceContentType.TEXT
    assert markdown.content_type is ResearchSourceContentType.MARKDOWN
    assert parser.calls == [text_source, markdown_source]


def test_same_bytes_different_paths_reuse_path_neutral_entry(tmp_path: Path) -> None:
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"
    first_directory.mkdir()
    second_directory.mkdir()
    first_path = first_directory / "source.txt"
    second_path = second_directory / "copy.txt"
    content = "same path-neutral bytes"
    first_path.write_text(content, encoding="utf-8")
    second_path.write_text(content, encoding="utf-8")
    first_source = _validated(first_path, root=tmp_path)
    second_source = _validated(second_path, root=tmp_path)
    parser = RecordingLocalDocumentParser()
    caching_parser = CachingLocalDocumentParser(
        parser=parser,
        cache=FileParsedDocumentCache(directory=tmp_path / "cache"),
    )

    first = caching_parser.parse(first_source)
    second = caching_parser.parse(second_source)

    assert first == second
    assert parser.calls == [first_source]
    assert "local_path" not in second.model_dump()
    assert "filename" not in second.model_dump()


def test_bare_path_uses_direct_parser_without_cache(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("direct content", encoding="utf-8")
    caching_parser = CachingLocalDocumentParser(
        parser=LocalDocumentParser(),
        cache=FileParsedDocumentCache(directory=tmp_path / "cache"),
    )
    with pytest.raises(TypeError, match="LocalDocumentAccessResult"):
        caching_parser.parse(source_path)  # type: ignore[arg-type]

    assert caching_parser.parse_path(source_path).content == "direct content"
    assert list((tmp_path / "cache").glob("*.json")) == []


def test_malformed_entry_recomputes_and_repairs(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("repair content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    identity = identity_from_validated_source(source)
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    entry_path = cache.directory / f"{identity.cache_key}.json"
    entry_path.write_text("{", encoding="utf-8")
    parser = RecordingLocalDocumentParser()

    actual = CachingLocalDocumentParser(parser=parser, cache=cache).parse(source)

    assert parser.calls == [source]
    assert cache.get(identity) == actual


def test_parser_failure_does_not_write_final_entry(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("failure content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    parser = RecordingLocalDocumentParser(failure=ValueError("parse failed"))

    with pytest.raises(ValueError, match="parse failed"):
        CachingLocalDocumentParser(parser=parser, cache=cache).parse(source)

    assert cache.get(identity_from_validated_source(source)) is None
    assert list(cache.directory.glob("*.json")) == []


def test_wrong_parsed_content_type_is_not_cached(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    with pytest.raises(ValueError, match="content type"):
        CachingLocalDocumentParser(parser=WrongContentTypeParser(), cache=cache).parse(
            source
        )
    assert list(cache.directory.glob("*.json")) == []


def test_unsafe_cache_lock_is_explicit_and_parser_is_not_called(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    identity = identity_from_validated_source(source)
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    external = tmp_path / "external"
    external.write_text("unchanged", encoding="utf-8")
    lock_path = cache.directory / f".{identity.cache_key}.lock"
    try:
        lock_path.symlink_to(external)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    parser = RecordingLocalDocumentParser()

    with pytest.raises(ParsedDocumentCacheError, match="unsafe"):
        CachingLocalDocumentParser(parser=parser, cache=cache).parse(source)

    assert parser.calls == []
    assert external.read_text(encoding="utf-8") == "unchanged"


def test_cache_lock_failure_is_explicit_and_parser_is_not_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    parser = RecordingLocalDocumentParser()
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")

    def fail_lock(file_descriptor: int, operation: int) -> None:
        raise OSError("lock failed")

    monkeypatch.setattr(
        "app.research.file_parsed_document_cache.fcntl.flock", fail_lock
    )
    with pytest.raises(ParsedDocumentCacheError, match="could not be acquired"):
        CachingLocalDocumentParser(parser=parser, cache=cache).parse(source)
    assert parser.calls == []


def test_generic_cache_write_failure_remains_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    parser = RecordingLocalDocumentParser()
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")

    def fail_write(*, entry_path: Path, serialized: str) -> None:
        raise ParsedDocumentCacheError("write failed")

    monkeypatch.setattr(cache, "_write_entry", fail_write)
    with pytest.raises(ParsedDocumentCacheError, match="write failed"):
        CachingLocalDocumentParser(parser=parser, cache=cache).parse(source)
    assert parser.calls == [source]


def test_oversized_parse_is_returned_uncached_and_recomputed(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("valid but not cacheable", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    parser = RecordingLocalDocumentParser()
    cache = FileParsedDocumentCache(
        directory=tmp_path / "cache", maximum_entry_bytes=128
    )
    caching_parser = CachingLocalDocumentParser(parser=parser, cache=cache)

    first = caching_parser.parse(source)
    second = caching_parser.parse(source)

    assert first == second
    assert parser.calls == [source, source]
    assert list(cache.directory.glob("*.json")) == []


def test_cache_hits_return_deep_safe_values(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("section content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    identity = identity_from_validated_source(source)
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    parsed = ParsedLocalDocument(
        content="section content",
        content_type=ResearchSourceContentType.TEXT,
        sections=[
            ResearchSourceDocumentSection(
                section_id="section-001",
                content="section content",
                order=1,
                start_character=0,
                end_character=15,
            )
        ],
    )
    cache.put(identity, parsed)
    caching_parser = CachingLocalDocumentParser(
        parser=RecordingLocalDocumentParser(), cache=cache
    )

    first = caching_parser.parse(source)
    first.sections.clear()
    second = caching_parser.parse(source)

    assert len(second.sections) == 1


def test_same_key_is_parsed_once_across_processes(tmp_path: Path) -> None:
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("fork multiprocessing is unavailable")
    source_path = tmp_path / "source.txt"
    source_path.write_text("shared process content", encoding="utf-8")
    source = _validated(source_path, root=tmp_path)
    cache_directory = tmp_path / "cache"
    counter_path = tmp_path / "parse-count"
    context = multiprocessing.get_context("fork")
    start = context.Event()
    results = context.Queue()
    processes = [
        context.Process(
            target=_process_parse,
            args=(cache_directory, counter_path, source, start, results),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    try:
        outputs = [results.get(timeout=2) for _ in processes]
    except Empty as error:
        raise AssertionError("worker did not return a result") from error

    assert outputs == ["shared process content", "shared process content"]
    assert counter_path.read_text(encoding="utf-8").splitlines() == ["parsed"]


def test_different_keys_use_different_lock_files(tmp_path: Path) -> None:
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("first", encoding="utf-8")
    second_path.write_text("second", encoding="utf-8")
    parser = RecordingLocalDocumentParser()
    cache = FileParsedDocumentCache(directory=tmp_path / "cache")
    caching_parser = CachingLocalDocumentParser(parser=parser, cache=cache)

    caching_parser.parse(_validated(first_path, root=tmp_path))
    caching_parser.parse(_validated(second_path, root=tmp_path))

    assert len(list(cache.directory.glob(".*.lock"))) == 2
