"""Tests for local research document conversion."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.research.in_memory_research_source_search_tool import (
    InMemoryResearchSourceSearchTool,
)
from app.research.local_document_access_policy import (
    LocalDocumentAccessGate,
    LocalDocumentAccessPolicy,
    LocalDocumentAccessResult,
)
from app.research.local_document_adapter import (
    LocalDocumentAdapter,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_query import ResearchSearchQuery
from app.schemas.research_source_document import (
    ResearchSourceContentType,
)
from tests.test_local_hwpx_text_extractor import write_hwpx
from tests.test_local_pdf_text_extractor import write_pdf


def _validated_result(path: Path) -> LocalDocumentAccessResult:
    policy = LocalDocumentAccessPolicy(
        allowed_roots=(path.parent,),
        maximum_file_bytes=32 * 1024 * 1024,
    )
    return LocalDocumentAccessGate(policy).validate(path)


def test_adapter_load_validated_preserves_raw_file_provenance(
    tmp_path: Path,
) -> None:
    path = tmp_path / "raw-source.txt"
    raw_content = b"raw source bytes"
    path.write_bytes(raw_content)

    bundle = LocalDocumentAdapter().load_validated(
        (_validated_result(path),)
    )

    expected_digest = hashlib.sha256(raw_content).hexdigest()
    for metadata in (
        bundle.source_records[0].metadata,
        bundle.document_records[0].metadata,
    ):
        assert metadata["local_file_size_bytes"] == str(len(raw_content))
        assert metadata["local_content_sha256"] == expected_digest


@pytest.mark.parametrize("suffix", [".pdf", ".hwpx"])
def test_validated_metadata_coexists_with_structured_format_provenance(
    tmp_path: Path,
    suffix: str,
) -> None:
    path = tmp_path / f"structured{suffix}"
    if suffix == ".pdf":
        write_pdf(path, ["PDF evidence."])
        format_key = "pdf_page_count"
        section_metadata = {"page_number": "1"}
    else:
        write_hwpx(
            path,
            sections={"Contents/section0.xml": ("HWPX evidence.",)},
        )
        format_key = "hwpx_section_count"
        section_metadata = {
            "hwpx_section_index": "1",
            "hwpx_package_path": "Contents/section0.xml",
        }

    bundle = LocalDocumentAdapter().load_validated(
        (_validated_result(path),)
    )
    document = bundle.document_records[0]

    assert document.metadata["local_file_size_bytes"] == str(path.stat().st_size)
    assert len(document.metadata["local_content_sha256"]) == 64
    assert document.metadata[format_key] == "1"
    assert document.sections[0].metadata == section_metadata


def test_adapter_loads_markdown_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "grounded-research.md"
    path.write_text(
        (
            "# Grounded Research\n\n"
            "Grounded research connects claims to "
            "traceable evidence and citations."
        ),
        encoding="utf-8",
    )

    bundle = LocalDocumentAdapter().load((path,))

    assert len(bundle.source_records) == 1
    assert len(bundle.document_records) == 1

    source = bundle.source_records[0]
    document = bundle.document_records[0]

    assert source.title == "Grounded Research"
    assert source.source_type is ResearchSourceType.OTHER
    assert source.url.startswith(
        "https://local.aira.invalid/source/"
    )
    assert source.metadata["local_path"] == str(
        path.resolve()
    )
    assert source.metadata["research_origin"] == "local"
    assert "grounded" in source.keywords

    assert document.source_id == source.source_id
    assert document.url == source.url
    assert "traceable evidence" in document.content
    assert document.language == "en"
    assert document.metadata["filename"] == path.name


def test_adapter_origin_survives_in_memory_candidate_search(
    tmp_path: Path,
) -> None:
    path = tmp_path / "local-origin.txt"
    path.write_text("Local origin evidence.", encoding="utf-8")
    bundle = LocalDocumentAdapter().load((path,))
    query = ResearchSearchQuery(
        query_id="query-local-origin",
        request_id="request-local-origin",
        task_id="task-local-origin",
        query_text="local origin evidence",
    )

    result = InMemoryResearchSourceSearchTool(
        records=bundle.source_records
    ).search(query)

    assert result.candidates[0].metadata["research_origin"] == "local"


def test_adapter_uses_filename_when_heading_is_missing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "agent_memory_notes.md"
    path.write_text(
        "Agent memory preserves useful prior context.",
        encoding="utf-8",
    )

    bundle = LocalDocumentAdapter().load((path,))

    assert (
        bundle.source_records[0].title
        == "agent memory notes"
    )


def test_adapter_detects_korean_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "연구자료.txt"
    path.write_text(
        (
            "근거 기반 연구는 출처와 증거를 연결하고 "
            "주장을 검증하는 과정이다."
        ),
        encoding="utf-8",
    )

    bundle = LocalDocumentAdapter().load((path,))

    assert bundle.document_records[0].language == "ko"


def test_adapter_loads_multiple_documents(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.txt"

    first.write_text(
        "# First Source\n\nEvidence from the first source.",
        encoding="utf-8",
    )
    second.write_text(
        "Evidence from the second source.",
        encoding="utf-8",
    )

    bundle = LocalDocumentAdapter().load(
        (
            first,
            second,
        )
    )

    assert len(bundle.source_records) == 2
    assert len(bundle.document_records) == 2
    assert (
        bundle.source_records[0].source_id
        != bundle.source_records[1].source_id
    )


def test_adapter_source_ids_are_stable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.md"
    path.write_text(
        "# Stable Source\n\nStable content.",
        encoding="utf-8",
    )

    adapter = LocalDocumentAdapter()

    first = adapter.load((path,))
    second = adapter.load((path,))

    assert (
        first.source_records[0].source_id
        == second.source_records[0].source_id
    )


def test_adapter_rejects_empty_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "empty.md"
    path.write_text(" \n\n ", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        LocalDocumentAdapter().load((path,))


def test_adapter_rejects_non_utf8_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.txt"
    path.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(
        ValueError,
        match="not valid UTF-8",
    ):
        LocalDocumentAdapter().load((path,))


def test_adapter_rejects_duplicate_paths(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.md"
    path.write_text(
        "# Source\n\nTraceable evidence.",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="duplicate local document",
    ):
        LocalDocumentAdapter().load(
            (
                path,
                path,
            )
        )


@pytest.mark.parametrize("suffix", [".hwp", ".docx"])
def test_adapter_rejects_unsupported_suffix(
    tmp_path: Path,
    suffix: str,
) -> None:
    path = tmp_path / f"source{suffix}"
    path.write_bytes(b"document")

    with pytest.raises(
        ValueError,
        match="Markdown, text, PDF, or HWPX",
    ):
        LocalDocumentAdapter().load((path,))


def test_adapter_loads_one_page_pdf(
    tmp_path: Path,
) -> None:
    path = tmp_path / "hybrid-routing.pdf"
    content = (
        "AIRA uses OpenAI evidence relevance and local bounded "
        "workers."
    )
    write_pdf(path, [content])

    bundle = LocalDocumentAdapter().load((path,))

    source = bundle.source_records[0]
    document = bundle.document_records[0]
    section = document.sections[0]

    assert source.title == "hybrid-routing"
    assert source.snippet == content
    assert "openai" in source.keywords
    assert source.metadata["local_path"] == str(path.resolve())
    assert source.metadata["filename"] == path.name
    assert source.metadata["adapter"] == "local-document"
    assert source.metadata["pdf_page_count"] == "1"
    assert source.metadata["pdf_text_page_count"] == "1"
    assert source.metadata["pdf_blank_page_count"] == "0"
    assert document.content_type is ResearchSourceContentType.PDF_TEXT
    assert document.content == content
    assert document.language == "en"
    assert document.metadata == source.metadata
    assert section.section_id == "page-001"
    assert section.heading is None
    assert section.order == 1
    assert section.metadata == {"page_number": "1"}
    assert document.content[
        section.start_character:section.end_character
    ] == section.content


def test_adapter_preserves_pdf_page_provenance(
    tmp_path: Path,
) -> None:
    path = tmp_path / "physical-pages.pdf"
    first = "First readable page."
    third = "Third readable page."
    write_pdf(path, [first, None, third])

    document = LocalDocumentAdapter().load(
        (path,)
    ).document_records[0]

    assert document.metadata["pdf_page_count"] == "3"
    assert document.metadata["pdf_text_page_count"] == "2"
    assert document.metadata["pdf_blank_page_count"] == "1"
    assert document.content == f"{first}\n\n{third}"
    assert [section.section_id for section in document.sections] == [
        "page-001",
        "page-003",
    ]
    assert [section.order for section in document.sections] == [1, 2]
    assert [
        section.metadata["page_number"]
        for section in document.sections
    ] == ["1", "3"]
    for section in document.sections:
        assert document.content[
            section.start_character:section.end_character
        ] == section.content


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("malformed", "could not be opened or parsed"),
        ("blank", "no extractable nonblank text"),
        ("encrypted", "encrypted PDF requires credentials"),
    ],
)
def test_adapter_translates_pdf_extraction_failures(
    tmp_path: Path,
    fixture: str,
    message: str,
) -> None:
    path = tmp_path / f"{fixture}.pdf"
    if fixture == "malformed":
        path.write_bytes(b"not a PDF")
    elif fixture == "encrypted":
        write_pdf(path, ["Protected text."], password="secret")
    else:
        write_pdf(path, [None])

    with pytest.raises(ValueError, match=message) as error_info:
        LocalDocumentAdapter().load((path,))

    assert "local PDF could not be read" in str(error_info.value)


def test_adapter_loads_one_section_hwpx(
    tmp_path: Path,
) -> None:
    path = tmp_path / "hybrid-routing.hwpx"
    content = (
        "에이라는 로컬 근거와 주장을 안전하게 연결하며 "
        "AIRA 연구 결과를 생성한다."
    )
    write_hwpx(
        path,
        sections={"Contents/section0.xml": (content,)},
    )

    bundle = LocalDocumentAdapter().load((path,))

    source = bundle.source_records[0]
    document = bundle.document_records[0]
    section = document.sections[0]
    assert source.title == "hybrid-routing"
    assert source.snippet == content
    assert "aira" in source.keywords
    assert "연구" in source.keywords
    assert source.metadata["local_path"] == str(path.resolve())
    assert source.metadata["filename"] == path.name
    assert source.metadata["adapter"] == "local-document"
    assert source.metadata["hwpx_section_count"] == "1"
    assert source.metadata["hwpx_text_section_count"] == "1"
    assert source.metadata["hwpx_blank_section_count"] == "0"
    assert document.content_type is ResearchSourceContentType.HWPX_TEXT
    assert document.content == content
    assert document.language == "ko"
    assert document.metadata == source.metadata
    assert section.section_id == "hwpx-section-001"
    assert section.heading is None
    assert section.order == 1
    assert section.metadata == {
        "hwpx_section_index": "1",
        "hwpx_package_path": "Contents/section0.xml",
    }
    assert document.content[
        section.start_character:section.end_character
    ] == section.content


def test_adapter_preserves_hwpx_body_section_provenance(
    tmp_path: Path,
) -> None:
    path = tmp_path / "body-sections.hwpx"
    first = "First readable body section."
    third = "Third readable body section."
    write_hwpx(
        path,
        sections={
            "Contents/section0.xml": (first,),
            "Contents/section1.xml": (),
            "Contents/section2.xml": (third,),
        },
    )

    document = LocalDocumentAdapter().load(
        (path,)
    ).document_records[0]

    assert document.content == f"{first}\n\n{third}"
    assert document.metadata["hwpx_section_count"] == "3"
    assert document.metadata["hwpx_text_section_count"] == "2"
    assert document.metadata["hwpx_blank_section_count"] == "1"
    assert [section.section_id for section in document.sections] == [
        "hwpx-section-001",
        "hwpx-section-003",
    ]
    assert [section.order for section in document.sections] == [1, 2]
    assert [
        section.metadata["hwpx_section_index"]
        for section in document.sections
    ] == ["1", "3"]
    assert [
        section.metadata["hwpx_package_path"]
        for section in document.sections
    ] == [
        "Contents/section0.xml",
        "Contents/section2.xml",
    ]
    for section in document.sections:
        assert document.content[
            section.start_character:section.end_character
        ] == section.content


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("malformed", "not a valid ZIP archive"),
        ("unsafe", "unsafe member path"),
        ("no-text", "no extractable nonblank body text"),
    ],
)
def test_adapter_translates_hwpx_extraction_failures(
    tmp_path: Path,
    fixture: str,
    message: str,
) -> None:
    path = tmp_path / f"{fixture}.hwpx"
    if fixture == "malformed":
        path.write_bytes(b"not an HWPX package")
    elif fixture == "unsafe":
        write_hwpx(
            path,
            sections={"Contents/section0.xml": ("Text.",)},
            extra_members={"../outside.xml": "unsafe"},
        )
    else:
        write_hwpx(
            path,
            sections={"Contents/section0.xml": ()},
        )

    with pytest.raises(ValueError, match=message) as error_info:
        LocalDocumentAdapter().load((path,))

    assert "local HWPX could not be read" in str(error_info.value)


def test_adapter_requires_at_least_one_document() -> None:
    with pytest.raises(
        ValueError,
        match="at least one local document",
    ):
        LocalDocumentAdapter().load(())
