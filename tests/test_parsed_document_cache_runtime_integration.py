"""Runtime integration tests for persistent Local parsed-document caching."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.research.caching_local_document_parser import CachingLocalDocumentParser
from app.research.file_parsed_document_cache import FileParsedDocumentCache
from app.research.integrated_research_handler import IntegratedResearchHandler
from app.research.local_document_access_policy import (
    LocalDocumentAccessGate,
    LocalDocumentAccessPolicy,
    LocalDocumentAccessResult,
)
from app.research.local_document_adapter import LocalDocumentBundle
from app.research.local_document_parser import LocalDocumentParser
from app.research.local_external_send_approval import LocalExternalSendApproval
from app.research.local_research_handler import (
    LocalResearchHandler,
    SemanticLocalResearchHandler,
)
from app.research.research_result_writer import ResearchResultPaths
from app.schemas.parsed_local_document import ParsedLocalDocument
from tests.test_local_hwpx_text_extractor import write_hwpx
from tests.test_local_pdf_text_extractor import write_pdf


class FakePipeline:
    def __init__(self) -> None:
        self.result = object()

    def run(self, request: object, *, workspace_id: str) -> object:
        return self.result


class FakeGuardrail:
    def validate(self, result: object, *, execution_id: str) -> None:
        return None


class FakeWriter:
    def __init__(self, root: Path) -> None:
        self._root = root

    def write(
        self, result: object, *, output_dir: Path, execution_id: str
    ) -> ResearchResultPaths:
        execution_dir = self._root / execution_id
        return ResearchResultPaths(
            execution_dir=execution_dir,
            report_path=execution_dir / "report.md",
            result_path=execution_dir / "result.json",
        )


class CapturingLocalResearchHandler(LocalResearchHandler):
    def __init__(self, *, bundles: list[LocalDocumentBundle], **kwargs: object) -> None:
        self._bundles = bundles
        super().__init__(**kwargs)  # type: ignore[arg-type]

    def _build_pipeline(
        self,
        bundle: LocalDocumentBundle,
        *,
        question: str,
        objective: str,
    ) -> FakePipeline:
        self._bundles.append(bundle)
        return FakePipeline()


class RecordingParser(LocalDocumentParser):
    def __init__(self) -> None:
        self.calls: list[LocalDocumentAccessResult] = []

    def parse(self, source: LocalDocumentAccessResult) -> ParsedLocalDocument:
        self.calls.append(source)
        return super().parse(source)


def _policy(root: Path) -> LocalDocumentAccessPolicy:
    return LocalDocumentAccessPolicy(
        allowed_roots=(root.resolve(),),
        maximum_file_bytes=32 * 1024 * 1024,
    )


def _source(path: Path, policy: LocalDocumentAccessPolicy) -> LocalDocumentAccessResult:
    return LocalDocumentAccessGate(policy).validate(path)


def _handler(
    *,
    execution_id: str,
    cache_directory: Path,
    parser: LocalDocumentParser,
    bundles: list[LocalDocumentBundle],
    tmp_path: Path,
) -> CapturingLocalResearchHandler:
    return CapturingLocalResearchHandler(
        bundles=bundles,
        id_factory=lambda: execution_id,
        writer=FakeWriter(tmp_path),  # type: ignore[arg-type]
        guardrail=FakeGuardrail(),  # type: ignore[arg-type]
        stdout=io.StringIO(),
        parsed_cache_directory_resolver=lambda: cache_directory,
        local_document_parser_factory=lambda: parser,
    )


def _run(
    handler: LocalResearchHandler,
    source: LocalDocumentAccessResult,
    policy: LocalDocumentAccessPolicy,
    tmp_path: Path,
) -> None:
    status = handler(
        "How does cached Local research work?",
        "Explain grounded Local evidence.",
        (source,),
        tmp_path / "reports",
        policy,
        None,
    )
    assert status == 0


def test_deterministic_access_validation_precedes_cache_lookup(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_text("validated content", encoding="utf-8")
    policy = _policy(tmp_path)
    source = _source(path, policy)
    path.unlink()
    calls: list[str] = []
    handler = LocalResearchHandler(
        parsed_cache_directory_resolver=lambda: (
            calls.append("parsed-cache") or tmp_path / "cache"
        )
    )

    with pytest.raises(ValueError, match="does not exist"):
        handler("Question", "Objective", (source,), tmp_path / "out", policy, None)

    assert calls == []


def test_same_bytes_different_paths_reuse_current_runtime_identity(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first" / "source.txt"
    second_path = tmp_path / "second" / "copy.txt"
    first_path.parent.mkdir()
    second_path.parent.mkdir()
    content = "Identical Local bytes with reusable normalized content."
    first_path.write_text(content, encoding="utf-8")
    second_path.write_text(content, encoding="utf-8")
    policy = _policy(tmp_path)
    first_source = _source(first_path, policy)
    second_source = _source(second_path, policy)
    cache_directory = tmp_path / "parsed-cache"
    first_parser = RecordingParser()
    second_parser = RecordingParser()
    bundles: list[LocalDocumentBundle] = []

    _run(
        _handler(
            execution_id="first-run",
            cache_directory=cache_directory,
            parser=first_parser,
            bundles=bundles,
            tmp_path=tmp_path,
        ),
        first_source,
        policy,
        tmp_path,
    )
    _run(
        _handler(
            execution_id="second-run",
            cache_directory=cache_directory,
            parser=second_parser,
            bundles=bundles,
            tmp_path=tmp_path,
        ),
        second_source,
        policy,
        tmp_path,
    )

    assert first_parser.calls == [first_source]
    assert second_parser.calls == []
    first_record = bundles[0].source_records[0]
    second_record = bundles[1].source_records[0]
    assert first_record.metadata["local_path"] == str(first_path.resolve())
    assert second_record.metadata["local_path"] == str(second_path.resolve())
    assert first_record.source_id != second_record.source_id
    assert first_record.url != second_record.url
    assert str(first_path.resolve()) not in second_record.model_dump_json()
    assert bundles[0].document_records[0].content == content
    assert bundles[1].document_records[0].content == content


@pytest.mark.parametrize("format_name", ["pdf", "hwpx"])
def test_structured_format_runtime_persistent_hit_preserves_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    format_name: str,
) -> None:
    path = tmp_path / f"source.{format_name}"
    if format_name == "pdf":
        write_pdf(path, ["First PDF page.", None, "Third PDF page."])
        target = "app.research.local_document_parser.LocalPdfTextExtractor.extract"
        from app.research.local_pdf_text_extractor import LocalPdfTextExtractor

        original_extract = LocalPdfTextExtractor.extract
    else:
        write_hwpx(
            path,
            sections={
                "Contents/section0.xml": ("First HWPX section.",),
                "Contents/section1.xml": (),
                "Contents/section2.xml": ("Third HWPX section.",),
            },
        )
        target = "app.research.local_document_parser.LocalHwpxTextExtractor.extract"
        from app.research.local_hwpx_text_extractor import LocalHwpxTextExtractor

        original_extract = LocalHwpxTextExtractor.extract
    extract_calls = 0

    def recording_extract(extractor: object, source_path: Path):
        nonlocal extract_calls
        extract_calls += 1
        return original_extract(extractor, source_path)

    monkeypatch.setattr(target, recording_extract)
    policy = _policy(tmp_path)
    source = _source(path, policy)
    bundles: list[LocalDocumentBundle] = []
    cache_directory = tmp_path / "parsed-cache"
    for index in range(2):
        _run(
            _handler(
                execution_id=f"{format_name}-{index}",
                cache_directory=cache_directory,
                parser=LocalDocumentParser(),
                bundles=bundles,
                tmp_path=tmp_path,
            ),
            source,
            policy,
            tmp_path,
        )

    assert extract_calls == 1
    document = bundles[1].document_records[0]
    for section in document.sections:
        assert (
            document.content[section.start_character : section.end_character]
            == section.content
        )
    if format_name == "pdf":
        assert [section.metadata["page_number"] for section in document.sections] == [
            "1",
            "3",
        ]
    else:
        assert [
            section.metadata["hwpx_section_index"] for section in document.sections
        ] == ["1", "3"]


def test_semantic_stale_approval_blocks_preexisting_cache_and_providers(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.txt"
    path.write_text("approved bytes", encoding="utf-8")
    policy = _policy(tmp_path)
    source = _source(path, policy)
    approval = LocalExternalSendApproval.for_semantic_local_research((source,))
    cache_directory = tmp_path / "parsed-cache"
    CachingLocalDocumentParser(
        parser=LocalDocumentParser(),
        cache=FileParsedDocumentCache(directory=cache_directory),
    ).parse(source)
    path.write_text("changed bytes", encoding="utf-8")
    calls: list[str] = []
    handler = SemanticLocalResearchHandler(
        parsed_cache_directory_resolver=lambda: (
            calls.append("parsed-cache") or cache_directory
        ),
        embedding_cache_directory_resolver=lambda: (
            calls.append("embedding-cache") or tmp_path / "embedding-cache"
        ),
        settings_loader=lambda: calls.append("settings"),  # type: ignore[arg-type]
        openai_client_factory=lambda settings: calls.append("openai"),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="changed"):
        handler("Question", "Objective", (source,), tmp_path / "out", policy, approval)

    assert calls == []


def test_integrated_stale_approval_blocks_preexisting_cache_and_providers(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.txt"
    path.write_text("approved bytes", encoding="utf-8")
    policy = _policy(tmp_path)
    source = _source(path, policy)
    approval = LocalExternalSendApproval.for_integrated_web_local_research((source,))
    cache_directory = tmp_path / "parsed-cache"
    CachingLocalDocumentParser(
        parser=LocalDocumentParser(),
        cache=FileParsedDocumentCache(directory=cache_directory),
    ).parse(source)
    path.write_text("changed bytes", encoding="utf-8")
    calls: list[str] = []
    handler = IntegratedResearchHandler(
        parsed_cache_directory_resolver=lambda: (
            calls.append("parsed-cache") or cache_directory
        ),
        embedding_cache_directory_resolver=lambda: (
            calls.append("embedding-cache") or tmp_path / "embedding-cache"
        ),
        config_loader=lambda: calls.append("tavily"),  # type: ignore[arg-type]
        settings_loader=lambda: calls.append("settings"),  # type: ignore[arg-type]
        openai_client_factory=lambda settings: calls.append("openai"),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="changed"):
        handler(
            "Question",
            "Objective",
            (source,),
            2,
            2048,
            tmp_path / "out",
            policy,
            approval,
        )

    assert calls == []


def test_general_parsed_cache_failure_is_explicit(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_text("content", encoding="utf-8")
    policy = _policy(tmp_path)
    source = _source(path, policy)

    def fail_cache(directory: Path):
        raise ParsedDocumentCacheError("cache failed")

    from app.research.parsed_document_cache import ParsedDocumentCacheError

    handler = LocalResearchHandler(
        parsed_cache_directory_resolver=lambda: tmp_path / "parsed-cache",
        parsed_cache_factory=fail_cache,
    )
    with pytest.raises(ParsedDocumentCacheError, match="cache failed"):
        handler("Question", "Objective", (source,), tmp_path / "out", policy, None)
