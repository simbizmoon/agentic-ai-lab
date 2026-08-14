"""Convert supported local files into research records."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Final
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from app.research.local_hwpx_text_extractor import (
    LocalHwpxTextExtractionError,
    LocalHwpxTextExtractor,
)
from app.research.local_pdf_text_extractor import (
    LocalPdfTextExtractionError,
    LocalPdfTextExtractor,
)
from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentRecord,
)
from app.schemas.in_memory_research_source import (
    InMemoryResearchSourceRecord,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentSection,
)

_SUPPORTED_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".md",
        ".markdown",
        ".hwpx",
        ".pdf",
        ".txt",
    }
)

_MARKDOWN_HEADING_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*#\s+(.+?)\s*$",
    re.MULTILINE,
)

_WORD_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[0-9A-Za-z가-힣]+"
)

_MAX_SNIPPET_LENGTH: Final[int] = 240
_MAX_KEYWORDS: Final[int] = 20


class LocalDocumentBundle(BaseModel):
    """Research records created from local documents."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_records: list[InMemoryResearchSourceRecord] = Field(
        min_length=1
    )
    document_records: list[
        InMemoryResearchDocumentRecord
    ] = Field(min_length=1)


class LocalDocumentAdapter:
    """Load supported local files for research."""

    def load(
        self,
        paths: tuple[Path, ...],
    ) -> LocalDocumentBundle:
        """Read local documents and build research records."""

        if not paths:
            raise ValueError(
                "at least one local document is required"
            )

        source_records: list[InMemoryResearchSourceRecord] = []
        document_records: list[
            InMemoryResearchDocumentRecord
        ] = []
        seen_paths: set[Path] = set()

        for position, path in enumerate(paths, start=1):
            resolved = self._validate_path(path)

            if resolved in seen_paths:
                raise ValueError(
                    f"duplicate local document: {resolved}"
                )

            seen_paths.add(resolved)

            content, sections, format_metadata = (
                self._read_document(resolved)
            )
            source_id = self._source_id(
                path=resolved,
                position=position,
            )
            title = self._title(
                path=resolved,
                content=content,
            )
            location = self._location(source_id)
            metadata = {
                "local_path": str(resolved),
                "filename": resolved.name,
                "adapter": "local-document",
                **format_metadata,
            }

            source_records.append(
                InMemoryResearchSourceRecord(
                    source_id=source_id,
                    title=title,
                    url=location,
                    source_type=ResearchSourceType.OTHER,
                    snippet=self._snippet(content),
                    keywords=self._keywords(
                        title=title,
                        content=content,
                    ),
                    author=None,
                    publisher="Local document",
                    published_at=None,
                    metadata=metadata,
                )
            )

            document_records.append(
                InMemoryResearchDocumentRecord(
                    source_id=source_id,
                    url=location,
                    content_type=self._content_type(resolved),
                    content=content,
                    sections=sections,
                    language=self._language(content),
                    metadata=metadata,
                )
            )

        return LocalDocumentBundle(
            source_records=source_records,
            document_records=document_records,
        )

    @staticmethod
    def _validate_path(path: Path) -> Path:
        """Validate and resolve one local document path."""

        if not isinstance(path, Path):
            raise TypeError("path must be a Path")

        resolved = path.expanduser().resolve()

        if not resolved.exists():
            raise ValueError(
                f"local document does not exist: {resolved}"
            )

        if not resolved.is_file():
            raise ValueError(
                f"local document is not a file: {resolved}"
            )

        if resolved.suffix.casefold() not in _SUPPORTED_SUFFIXES:
            raise ValueError(
                "local document must be Markdown, text, PDF, or HWPX: "
                f"{resolved}"
            )

        return resolved

    @classmethod
    def _read_document(
        cls,
        path: Path,
    ) -> tuple[
        str,
        list[ResearchSourceDocumentSection],
        dict[str, str],
    ]:
        """Read content and optional format-specific structure."""

        suffix = path.suffix.casefold()
        if suffix == ".hwpx":
            return cls._read_hwpx(path)
        if suffix != ".pdf":
            return cls._read_content(path), [], {}

        try:
            result = LocalPdfTextExtractor().extract(path)
        except LocalPdfTextExtractionError as error:
            raise ValueError(
                f"local PDF could not be read: {path}: {error}"
            ) from error

        text_pages = [page for page in result.pages if page.content]
        sections = [
            ResearchSourceDocumentSection(
                section_id=f"page-{page.page_number:03d}",
                heading=None,
                content=page.content,
                order=order,
                start_character=page.start_character,
                end_character=page.end_character,
                metadata={
                    "page_number": str(page.page_number),
                },
            )
            for order, page in enumerate(text_pages, start=1)
        ]
        page_count = result.total_page_count
        text_page_count = len(text_pages)
        metadata = {
            "pdf_page_count": str(page_count),
            "pdf_text_page_count": str(text_page_count),
            "pdf_blank_page_count": str(
                page_count - text_page_count
            ),
        }

        return result.content, sections, metadata

    @staticmethod
    def _read_hwpx(
        path: Path,
    ) -> tuple[
        str,
        list[ResearchSourceDocumentSection],
        dict[str, str],
    ]:
        """Read HWPX text and preserve nonblank body sections."""

        try:
            result = LocalHwpxTextExtractor().extract(path)
        except LocalHwpxTextExtractionError as error:
            raise ValueError(
                f"local HWPX could not be read: {path}: {error}"
            ) from error

        text_sections = [
            section for section in result.sections if section.content
        ]
        sections = [
            ResearchSourceDocumentSection(
                section_id=(
                    f"hwpx-section-{section.section_index:03d}"
                ),
                heading=None,
                content=section.content,
                order=order,
                start_character=section.start_character,
                end_character=section.end_character,
                metadata={
                    "hwpx_section_index": str(
                        section.section_index
                    ),
                    "hwpx_package_path": section.package_path,
                },
            )
            for order, section in enumerate(
                text_sections,
                start=1,
            )
        ]
        section_count = result.total_section_count
        text_section_count = len(text_sections)
        metadata = {
            "hwpx_section_count": str(section_count),
            "hwpx_text_section_count": str(text_section_count),
            "hwpx_blank_section_count": str(
                section_count - text_section_count
            ),
        }

        return result.content, sections, metadata

    @staticmethod
    def _read_content(path: Path) -> str:
        """Read one UTF-8 document."""

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                f"local document is not valid UTF-8: {path}"
            ) from error
        except OSError as error:
            raise ValueError(
                f"local document could not be read: {path}"
            ) from error

        if not content.strip():
            raise ValueError(
                f"local document must not be empty: {path}"
            )

        return content

    @staticmethod
    def _source_id(
        *,
        path: Path,
        position: int,
    ) -> str:
        """Return a stable source identifier."""

        digest = hashlib.sha256(
            str(path).encode("utf-8")
        ).hexdigest()[:12]

        return f"local-source-{position:03d}-{digest}"

    @staticmethod
    def _location(source_id: str) -> str:
        """Return an internal HTTPS source location."""

        return (
            "https://local.aira.invalid/source/"
            f"{quote(source_id, safe='')}"
        )

    @classmethod
    def _title(
        cls,
        *,
        path: Path,
        content: str,
    ) -> str:
        """Extract a readable document title."""

        if path.suffix.casefold() in {".md", ".markdown"}:
            match = _MARKDOWN_HEADING_PATTERN.search(content)

            if match is not None:
                title = match.group(1).strip()

                if title:
                    return title

        if path.suffix.casefold() in {".pdf", ".hwpx"}:
            return path.stem

        return (
            path.stem
            .replace("_", " ")
            .replace("-", " ")
            .strip()
        )

    @classmethod
    def _snippet(cls, content: str) -> str:
        """Create a compact searchable snippet."""

        normalized = " ".join(content.split())

        if len(normalized) <= _MAX_SNIPPET_LENGTH:
            return normalized

        return (
            normalized[: _MAX_SNIPPET_LENGTH - 1].rstrip()
            + "…"
        )

    @classmethod
    def _keywords(
        cls,
        *,
        title: str,
        content: str,
    ) -> list[str]:
        """Extract deterministic searchable keywords."""

        candidates = _WORD_PATTERN.findall(
            f"{title} {content}"
        )

        keywords: list[str] = []
        seen: set[str] = set()

        for candidate in candidates:
            normalized = candidate.casefold()

            if len(normalized) < 2:
                continue

            if normalized in seen:
                continue

            seen.add(normalized)
            keywords.append(normalized)

            if len(keywords) >= _MAX_KEYWORDS:
                break

        return keywords

    @staticmethod
    def _content_type(
        path: Path,
    ) -> ResearchSourceContentType:
        """Map a local suffix to a research content type."""

        if path.suffix.casefold() in {".md", ".markdown"}:
            return ResearchSourceContentType.MARKDOWN

        if path.suffix.casefold() == ".pdf":
            return ResearchSourceContentType.PDF_TEXT

        if path.suffix.casefold() == ".hwpx":
            return ResearchSourceContentType.HWPX_TEXT

        return ResearchSourceContentType.TEXT

    @staticmethod
    def _language(content: str) -> str:
        """Return a basic deterministic language hint."""

        korean_count = len(
            re.findall(r"[가-힣]", content)
        )
        latin_count = len(
            re.findall(r"[A-Za-z]", content)
        )

        if korean_count > latin_count:
            return "ko"

        if latin_count > 0:
            return "en"

        return "und"
