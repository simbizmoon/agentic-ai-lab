"""Convert supported local files into research records."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Final
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from app.research.local_document_access_policy import (
    LocalDocumentAccessResult,
)
from app.research.local_document_parser import (
    SUPPORTED_LOCAL_DOCUMENT_SUFFIXES,
    LocalDocumentParser,
)
from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentRecord,
)
from app.schemas.in_memory_research_source import (
    InMemoryResearchSourceRecord,
)
from app.schemas.research_request import ResearchSourceType

_MARKDOWN_HEADING_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*#\s+(.+?)\s*$",
    re.MULTILINE,
)

_WORD_PATTERN: Final[re.Pattern[str]] = re.compile(r"[0-9A-Za-z가-힣]+")

_MAX_SNIPPET_LENGTH: Final[int] = 240
_MAX_KEYWORDS: Final[int] = 20


class LocalDocumentBundle(BaseModel):
    """Research records created from local documents."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_records: list[InMemoryResearchSourceRecord] = Field(min_length=1)
    document_records: list[InMemoryResearchDocumentRecord] = Field(min_length=1)


class LocalDocumentAdapter:
    """Load supported local files for research."""

    def __init__(self, *, parser: LocalDocumentParser | None = None) -> None:
        self._parser = parser or LocalDocumentParser()

    def load(
        self,
        paths: tuple[Path, ...],
    ) -> LocalDocumentBundle:
        """Read local documents and build research records."""

        return self._load(paths, access_results_by_path={})

    def load_validated(
        self,
        access_results: tuple[LocalDocumentAccessResult, ...],
    ) -> LocalDocumentBundle:
        """Read documents carrying validated raw-file provenance."""

        if not access_results:
            raise ValueError("at least one validated local document is required")
        if any(
            not isinstance(result, LocalDocumentAccessResult)
            for result in access_results
        ):
            raise TypeError(
                "access_results must contain LocalDocumentAccessResult values"
            )
        results_by_path = {result.resolved_path: result for result in access_results}
        if len(results_by_path) != len(access_results):
            raise ValueError("duplicate validated local document")
        return self._load(
            tuple(result.resolved_path for result in access_results),
            access_results_by_path=results_by_path,
        )

    def _load(
        self,
        paths: tuple[Path, ...],
        *,
        access_results_by_path: dict[Path, LocalDocumentAccessResult],
    ) -> LocalDocumentBundle:
        """Build records with optional validated raw-file provenance."""

        if not paths:
            raise ValueError("at least one local document is required")

        source_records: list[InMemoryResearchSourceRecord] = []
        document_records: list[InMemoryResearchDocumentRecord] = []
        seen_paths: set[Path] = set()

        for position, path in enumerate(paths, start=1):
            resolved = self._validate_path(path)

            if resolved in seen_paths:
                raise ValueError(f"duplicate local document: {resolved}")

            seen_paths.add(resolved)

            access_result = access_results_by_path.get(resolved)
            parser = getattr(self, "_parser", None) or LocalDocumentParser()
            parsed = (
                parser.parse(access_result)
                if access_result is not None
                else parser.parse_path(resolved)
            )
            content = parsed.content
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
                "research_origin": "local",
                **self._access_metadata(access_results_by_path.get(resolved)),
                **parsed.format_metadata,
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
                    content_type=parsed.content_type,
                    content=content,
                    sections=[
                        section.model_copy(deep=True) for section in parsed.sections
                    ],
                    language=self._language(content),
                    metadata=metadata,
                )
            )

        return LocalDocumentBundle(
            source_records=source_records,
            document_records=document_records,
        )

    @staticmethod
    def _access_metadata(
        result: LocalDocumentAccessResult | None,
    ) -> dict[str, str]:
        if result is None:
            return {}
        return {
            "local_file_size_bytes": str(result.file_size_bytes),
            "local_content_sha256": result.content_sha256,
        }

    @staticmethod
    def _validate_path(path: Path) -> Path:
        """Validate and resolve one local document path."""

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
    def _source_id(
        *,
        path: Path,
        position: int,
    ) -> str:
        """Return a stable source identifier."""

        digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]

        return f"local-source-{position:03d}-{digest}"

    @staticmethod
    def _location(source_id: str) -> str:
        """Return an internal HTTPS source location."""

        return f"https://local.aira.invalid/source/{quote(source_id, safe='')}"

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

        return path.stem.replace("_", " ").replace("-", " ").strip()

    @classmethod
    def _snippet(cls, content: str) -> str:
        """Create a compact searchable snippet."""

        normalized = " ".join(content.split())

        if len(normalized) <= _MAX_SNIPPET_LENGTH:
            return normalized

        return normalized[: _MAX_SNIPPET_LENGTH - 1].rstrip() + "…"

    @classmethod
    def _keywords(
        cls,
        *,
        title: str,
        content: str,
    ) -> list[str]:
        """Extract deterministic searchable keywords."""

        candidates = _WORD_PATTERN.findall(f"{title} {content}")

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
    def _language(content: str) -> str:
        """Return a basic deterministic language hint."""

        korean_count = len(re.findall(r"[가-힣]", content))
        latin_count = len(re.findall(r"[A-Za-z]", content))

        if korean_count > latin_count:
            return "ko"

        if latin_count > 0:
            return "en"

        return "und"
