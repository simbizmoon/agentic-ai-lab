"""Tests for the path-neutral Local document parsing boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.research.local_document_access_policy import (
    LocalDocumentAccessGate,
    LocalDocumentAccessPolicy,
)
from app.research.local_document_adapter import LocalDocumentAdapter
from app.research.local_document_parser import LocalDocumentParser
from app.schemas.parsed_local_document import ParsedLocalDocument
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentSection,
)
from tests.test_local_hwpx_text_extractor import write_hwpx
from tests.test_local_pdf_text_extractor import write_pdf


def validated(path: Path, *, root: Path):
    policy = LocalDocumentAccessPolicy(
        allowed_roots=(root,),
        maximum_file_bytes=32 * 1024 * 1024,
    )
    return LocalDocumentAccessGate(policy).validate(path)


@pytest.mark.parametrize(
    ("suffix", "content_type"),
    [
        (".txt", ResearchSourceContentType.TEXT),
        (".md", ResearchSourceContentType.MARKDOWN),
        (".markdown", ResearchSourceContentType.MARKDOWN),
    ],
)
def test_parser_preserves_utf8_text_without_path_metadata(
    tmp_path: Path,
    suffix: str,
    content_type: ResearchSourceContentType,
) -> None:
    path = tmp_path / f"document{suffix}"
    content = "# Heading\n\nExact UTF-8 content."
    path.write_text(content, encoding="utf-8")

    parsed = LocalDocumentParser().parse(validated(path, root=tmp_path))

    assert parsed.content == content
    assert parsed.content_type is content_type
    assert parsed.sections == []
    assert parsed.format_metadata == {}
    assert "path" not in parsed.model_dump()
    assert "filename" not in parsed.model_dump()


def test_identical_bytes_at_different_paths_share_parsed_output_only(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "document.txt"
    second = second_dir / "document.txt"
    content = "Identical normalized Local document content."
    first.write_text(content, encoding="utf-8")
    second.write_text(content, encoding="utf-8")

    parser = LocalDocumentParser()
    first_parsed = parser.parse(validated(first, root=tmp_path))
    second_parsed = parser.parse(validated(second, root=tmp_path))
    first_bundle = LocalDocumentAdapter(parser=parser).load((first,))
    second_bundle = LocalDocumentAdapter(parser=parser).load((second,))

    assert first_parsed == second_parsed
    assert first_bundle.document_records[0].content == content
    assert second_bundle.document_records[0].content == content
    assert (
        first_bundle.source_records[0].metadata["local_path"]
        != second_bundle.source_records[0].metadata["local_path"]
    )
    assert (
        first_bundle.source_records[0].source_id
        != second_bundle.source_records[0].source_id
    )
    assert first_bundle.source_records[0].url != second_bundle.source_records[0].url


def test_parser_preserves_pdf_page_provenance(tmp_path: Path) -> None:
    path = tmp_path / "pages.pdf"
    first = "First PDF page."
    third = "Third PDF page."
    write_pdf(path, [first, None, third])

    parsed = LocalDocumentParser().parse(validated(path, root=tmp_path))

    assert parsed.content_type is ResearchSourceContentType.PDF_TEXT
    assert parsed.content == f"{first}\n\n{third}"
    assert parsed.format_metadata == {
        "pdf_page_count": "3",
        "pdf_text_page_count": "2",
        "pdf_blank_page_count": "1",
    }
    assert [section.section_id for section in parsed.sections] == [
        "page-001",
        "page-003",
    ]
    assert [section.metadata["page_number"] for section in parsed.sections] == [
        "1",
        "3",
    ]
    for section in parsed.sections:
        assert (
            parsed.content[section.start_character : section.end_character]
            == section.content
        )


def test_parser_preserves_hwpx_body_section_provenance(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sections.hwpx"
    first = "First HWPX section."
    third = "Third HWPX section."
    write_hwpx(
        path,
        sections={
            "Contents/section0.xml": (first,),
            "Contents/section1.xml": (),
            "Contents/section2.xml": (third,),
        },
    )

    parsed = LocalDocumentParser().parse(validated(path, root=tmp_path))

    assert parsed.content_type is ResearchSourceContentType.HWPX_TEXT
    assert parsed.content == f"{first}\n\n{third}"
    assert parsed.format_metadata == {
        "hwpx_section_count": "3",
        "hwpx_text_section_count": "2",
        "hwpx_blank_section_count": "1",
    }
    assert [section.metadata["hwpx_section_index"] for section in parsed.sections] == [
        "1",
        "3",
    ]
    assert [section.metadata["hwpx_package_path"] for section in parsed.sections] == [
        "Contents/section0.xml",
        "Contents/section2.xml",
    ]
    for section in parsed.sections:
        assert (
            parsed.content[section.start_character : section.end_character]
            == section.content
        )


def test_parsed_document_is_strict_frozen_and_rejects_unknown_fields() -> None:
    parsed = ParsedLocalDocument(
        content="Stable content.",
        content_type=ResearchSourceContentType.TEXT,
    )

    with pytest.raises(ValidationError):
        parsed.content = "Changed."  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ParsedLocalDocument(
            content="Stable content.",
            content_type=ResearchSourceContentType.TEXT,
            unexpected="value",  # type: ignore[call-arg]
        )


def test_parsed_document_rejects_section_content_range_mismatch() -> None:
    section = ResearchSourceDocumentSection(
        section_id="section-001",
        content="other",
        order=1,
        start_character=0,
        end_character=5,
    )

    with pytest.raises(
        ValidationError,
        match="section must match its range",
    ):
        ParsedLocalDocument(
            content="value",
            content_type=ResearchSourceContentType.TEXT,
            sections=[section],
        )
