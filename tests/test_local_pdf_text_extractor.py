"""Tests for local text-based PDF extraction."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from app.research.local_pdf_text_extractor import (
    PAGE_SEPARATOR,
    LocalPdfTextExtractionError,
    LocalPdfTextExtractor,
)


def write_pdf(
    path: Path,
    pages: list[str | None],
    *,
    password: str | None = None,
) -> None:
    """Write a deterministic PDF with optional page text."""

    writer = PdfWriter()

    for text in pages:
        page = writer.add_blank_page(
            width=612,
            height=792,
        )
        if text is None:
            continue

        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): font}
                )
            }
        )
        stream = DecodedStreamObject()
        escaped = (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        stream.set_data(
            f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode(
                "ascii"
            )
        )
        page[NameObject("/Contents")] = writer._add_object(
            stream
        )

    if password is not None:
        writer.encrypt(password)

    with path.open("wb") as output:
        writer.write(output)


def test_extracts_one_page_text_pdf(tmp_path: Path) -> None:
    path = tmp_path / "one-page.pdf"
    write_pdf(path, ["  One page of PDF text.  "])

    result = LocalPdfTextExtractor().extract(path)

    assert result.content == "One page of PDF text."
    assert result.total_page_count == 1
    assert result.pages[0].page_number == 1
    assert result.pages[0].start_character == 0
    assert result.pages[0].end_character == len(result.content)


def test_extracts_ordered_pages_with_exact_offsets(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multiple-pages.pdf"
    first = "First physical page."
    second = "Second physical page."
    write_pdf(path, [first, second])

    result = LocalPdfTextExtractor().extract(path)

    assert result.content == f"{first}{PAGE_SEPARATOR}{second}"
    assert result.total_page_count == 2
    assert [page.page_number for page in result.pages] == [1, 2]
    assert result.pages[0].start_character == 0
    assert result.pages[0].end_character == len(first)
    assert result.pages[1].start_character == (
        len(first) + len(PAGE_SEPARATOR)
    )
    assert result.pages[1].end_character == len(result.content)

    for page in result.pages:
        assert result.content[
            page.start_character:page.end_character
        ] == page.content


def test_blank_page_preserves_physical_number_without_text_span(
    tmp_path: Path,
) -> None:
    path = tmp_path / "blank-middle-page.pdf"
    first = "First readable page."
    third = "Third readable page."
    write_pdf(path, [first, None, third])

    result = LocalPdfTextExtractor().extract(path)

    assert result.content == f"{first}{PAGE_SEPARATOR}{third}"
    assert result.total_page_count == 3
    blank = result.pages[1]
    assert blank.page_number == 2
    assert blank.content == ""
    assert blank.start_character == len(first)
    assert blank.end_character == len(first)
    assert result.content[
        blank.start_character:blank.end_character
    ] == blank.content
    assert result.pages[2].page_number == 3


def test_rejects_pdf_without_extractable_text(
    tmp_path: Path,
) -> None:
    path = tmp_path / "blank.pdf"
    write_pdf(path, [None, None])

    with pytest.raises(
        LocalPdfTextExtractionError,
        match="no extractable nonblank text",
    ):
        LocalPdfTextExtractor().extract(path)


@pytest.mark.parametrize(
    ("path_factory", "message"),
    [
        (lambda root: "not-a-path", "path must be a Path"),
        (
            lambda root: root / "missing.pdf",
            "PDF path does not exist",
        ),
        (lambda root: root, "PDF path is not a file"),
    ],
)
def test_rejects_invalid_path(
    tmp_path: Path,
    path_factory: Callable[[Path], object],
    message: str,
) -> None:
    path = path_factory(tmp_path)

    with pytest.raises(
        LocalPdfTextExtractionError,
        match=message,
    ):
        LocalPdfTextExtractor().extract(path)  # type: ignore[arg-type]


def test_rejects_unsupported_suffix(tmp_path: Path) -> None:
    path = tmp_path / "document.txt"
    path.write_text("not a PDF", encoding="utf-8")

    with pytest.raises(
        LocalPdfTextExtractionError,
        match=r"must have a \.pdf suffix",
    ):
        LocalPdfTextExtractor().extract(path)


def test_rejects_malformed_pdf(tmp_path: Path) -> None:
    path = tmp_path / "malformed.pdf"
    path.write_bytes(b"not a PDF")

    with pytest.raises(
        LocalPdfTextExtractionError,
        match="could not be opened or parsed",
    ):
        LocalPdfTextExtractor().extract(path)


def test_does_not_translate_unrelated_extraction_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "programming-error.pdf"
    path.write_bytes(b"path validation only")

    class BrokenPage:
        def extract_text(self) -> str:
            raise RuntimeError("programming defect")

    monkeypatch.setattr(
        "app.research.local_pdf_text_extractor.PdfReader",
        lambda _path: SimpleNamespace(
            is_encrypted=False,
            pages=[BrokenPage()],
        ),
    )

    with pytest.raises(RuntimeError, match="programming defect"):
        LocalPdfTextExtractor().extract(path)


def test_rejects_encrypted_pdf(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    write_pdf(path, ["Protected text."], password="secret")

    with pytest.raises(
        LocalPdfTextExtractionError,
        match="encrypted PDF requires credentials",
    ):
        LocalPdfTextExtractor().extract(path)
