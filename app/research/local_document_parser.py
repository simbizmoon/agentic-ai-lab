"""Path-neutral parsing for supported local research documents."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from app.research.local_document_access_policy import LocalDocumentAccessResult
from app.research.local_hwpx_text_extractor import (
    LocalHwpxTextExtractionError,
    LocalHwpxTextExtractor,
)
from app.research.local_pdf_text_extractor import (
    LocalPdfTextExtractionError,
    LocalPdfTextExtractor,
)
from app.schemas.parsed_local_document import ParsedLocalDocument
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentSection,
)

SUPPORTED_LOCAL_DOCUMENT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".md", ".markdown", ".hwpx", ".pdf", ".txt"}
)


class LocalDocumentParser:
    """Parse a canonical local path into reusable content-derived output."""

    def parse(self, source: LocalDocumentAccessResult) -> ParsedLocalDocument:
        """Parse one validated source without retaining its path."""

        if not isinstance(source, LocalDocumentAccessResult):
            raise TypeError("source must be a LocalDocumentAccessResult")
        return self._parse_path(source.resolved_path)

    def parse_path(self, path: Path) -> ParsedLocalDocument:
        """Parse a direct development path outside the production gate."""

        return self._parse_path(path)

    def _parse_path(self, path: Path) -> ParsedLocalDocument:
        resolved = self._validate_path(path)
        suffix = resolved.suffix.casefold()
        if suffix == ".pdf":
            return self._parse_pdf(resolved)
        if suffix == ".hwpx":
            return self._parse_hwpx(resolved)
        return ParsedLocalDocument(
            content=self._read_utf8(resolved),
            content_type=(
                ResearchSourceContentType.MARKDOWN
                if suffix in {".md", ".markdown"}
                else ResearchSourceContentType.TEXT
            ),
        )

    @staticmethod
    def _validate_path(path: Path) -> Path:
        if not isinstance(path, Path):
            raise TypeError("path must be a Path")
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            raise ValueError(f"local document does not exist: {resolved}")
        if not resolved.is_file():
            raise ValueError(f"local document is not a file: {resolved}")
        if resolved.suffix.casefold() not in SUPPORTED_LOCAL_DOCUMENT_SUFFIXES:
            raise ValueError(
                f"local document must be Markdown, text, PDF, or HWPX: {resolved}"
            )
        return resolved

    @staticmethod
    def _read_utf8(path: Path) -> str:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"local document is not valid UTF-8: {path}") from error
        except OSError as error:
            raise ValueError(f"local document could not be read: {path}") from error
        if not content.strip():
            raise ValueError(f"local document must not be empty: {path}")
        return content

    @staticmethod
    def _parse_pdf(path: Path) -> ParsedLocalDocument:
        try:
            result = LocalPdfTextExtractor().extract(path)
        except LocalPdfTextExtractionError as error:
            raise ValueError(f"local PDF could not be read: {path}: {error}") from error

        text_pages = [page for page in result.pages if page.content]
        sections = [
            ResearchSourceDocumentSection(
                section_id=f"page-{page.page_number:03d}",
                heading=None,
                content=page.content,
                order=order,
                start_character=page.start_character,
                end_character=page.end_character,
                metadata={"page_number": str(page.page_number)},
            )
            for order, page in enumerate(text_pages, start=1)
        ]
        page_count = result.total_page_count
        text_page_count = len(text_pages)
        return ParsedLocalDocument(
            content=result.content,
            content_type=ResearchSourceContentType.PDF_TEXT,
            sections=sections,
            format_metadata={
                "pdf_page_count": str(page_count),
                "pdf_text_page_count": str(text_page_count),
                "pdf_blank_page_count": str(page_count - text_page_count),
            },
        )

    @staticmethod
    def _parse_hwpx(path: Path) -> ParsedLocalDocument:
        try:
            result = LocalHwpxTextExtractor().extract(path)
        except LocalHwpxTextExtractionError as error:
            raise ValueError(
                f"local HWPX could not be read: {path}: {error}"
            ) from error

        text_sections = [section for section in result.sections if section.content]
        sections = [
            ResearchSourceDocumentSection(
                section_id=f"hwpx-section-{section.section_index:03d}",
                heading=None,
                content=section.content,
                order=order,
                start_character=section.start_character,
                end_character=section.end_character,
                metadata={
                    "hwpx_section_index": str(section.section_index),
                    "hwpx_package_path": section.package_path,
                },
            )
            for order, section in enumerate(text_sections, start=1)
        ]
        section_count = result.total_section_count
        text_section_count = len(text_sections)
        return ParsedLocalDocument(
            content=result.content,
            content_type=ResearchSourceContentType.HWPX_TEXT,
            sections=sections,
            format_metadata={
                "hwpx_section_count": str(section_count),
                "hwpx_text_section_count": str(text_section_count),
                "hwpx_blank_section_count": str(section_count - text_section_count),
            },
        )
