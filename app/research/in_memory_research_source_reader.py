"""In-memory implementation of the research source reader port."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from app.research.research_source_reader import (
    ResearchSourceReader,
)
from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentReadMode,
    InMemoryResearchDocumentRecord,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentError,
    ResearchSourceDocumentSection,
    ResearchSourceDocumentStatus,
)


class InMemoryResearchSourceReader(
    ResearchSourceReader
):
    """Read deterministic documents stored in memory."""

    def __init__(
        self,
        *,
        records: list[InMemoryResearchDocumentRecord],
        name: str = "in-memory-reader",
    ) -> None:
        if not name.strip():
            raise ValueError(
                "name must not be blank"
            )

        self._validate_records(records)

        self._records = {
            record.source_id.strip().casefold(): (
                record.model_copy(deep=True)
            )
            for record in records
        }
        self._name = name

    @property
    def name(self) -> str:
        """Return the reader name."""

        return self._name

    def read(
        self,
        candidate: ResearchSourceCandidate,
    ) -> ResearchSourceDocument:
        """Read one source candidate from stored records."""

        record = self._records.get(
            candidate.source_id.strip().casefold()
        )

        if record is None:
            return self._failed_document(
                candidate=candidate,
                error_type="DocumentNotFound",
                message=(
                    "No in-memory document exists "
                    "for the source candidate."
                ),
                retryable=False,
            )

        if (
            self._normalized_url(record.url)
            != candidate.normalized_url()
        ):
            return self._failed_document(
                candidate=candidate,
                error_type="SourceUrlMismatch",
                message=(
                    "Stored document URL does not match "
                    "the source candidate URL."
                ),
                retryable=False,
            )

        if (
            record.read_mode
            is InMemoryResearchDocumentReadMode.FAIL
        ):
            return self._failed_document(
                candidate=candidate,
                error_type=record.failure_type
                or "DocumentReadFailure",
                message=record.failure_message
                or "The document could not be read.",
                retryable=record.retryable,
            )

        content = record.content
        sections = self._build_sections(content)

        return ResearchSourceDocument(
            document_id=self._document_id(candidate),
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=record.content_type,
            content=content,
            language=record.language,
            sections=sections,
            word_count=len(content.split()),
            character_count=len(content),
            reader=self.name,
            error=None,
            metadata={
                **record.metadata,
                "storage": "in-memory",
            },
        )

    def records(
        self,
    ) -> list[InMemoryResearchDocumentRecord]:
        """Return defensive copies of stored records."""

        return [
            record.model_copy(deep=True)
            for record in self._records.values()
        ]

    def _failed_document(
        self,
        *,
        candidate: ResearchSourceCandidate,
        error_type: str,
        message: str,
        retryable: bool,
    ) -> ResearchSourceDocument:
        """Create a structured failed read document."""

        return ResearchSourceDocument(
            document_id=self._document_id(candidate),
            candidate=candidate,
            status=ResearchSourceDocumentStatus.FAILED,
            content_type=ResearchSourceContentType.OTHER,
            content="",
            language=None,
            sections=[],
            word_count=0,
            character_count=0,
            reader=self.name,
            error=ResearchSourceDocumentError(
                error_type=error_type,
                message=message,
                retryable=retryable,
            ),
            metadata={
                "storage": "in-memory",
            },
        )

    @classmethod
    def _build_sections(
        cls,
        content: str,
    ) -> list[ResearchSourceDocumentSection]:
        """Convert nonblank paragraphs into document sections."""

        sections: list[
            ResearchSourceDocumentSection
        ] = []
        search_position = 0

        for paragraph in content.split("\n\n"):
            if not paragraph.strip():
                search_position += len(paragraph) + 2
                continue

            start_character = content.find(
                paragraph,
                search_position,
            )

            if start_character < 0:
                raise ValueError(
                    "paragraph could not be located "
                    "within document content"
                )

            end_character = (
                start_character + len(paragraph)
            )
            section_number = len(sections) + 1

            sections.append(
                ResearchSourceDocumentSection(
                    section_id=(
                        f"section-{section_number:03d}"
                    ),
                    heading=None,
                    content=paragraph,
                    order=section_number,
                    start_character=start_character,
                    end_character=end_character,
                )
            )

            search_position = end_character + 2

        return sections

    @staticmethod
    def _document_id(
        candidate: ResearchSourceCandidate,
    ) -> str:
        """Return a deterministic document identifier."""

        return (
            f"{candidate.request_id.strip()}-document-"
            f"{candidate.source_id.strip()}"
        )

    @classmethod
    def _validate_records(
        cls,
        records: list[InMemoryResearchDocumentRecord],
    ) -> None:
        """Validate record source IDs and URLs."""

        source_ids = [
            record.source_id.strip().casefold()
            for record in records
        ]

        if len(set(source_ids)) != len(source_ids):
            raise ValueError(
                "document record source IDs must be unique"
            )

        urls = [
            cls._normalized_url(record.url)
            for record in records
        ]

        if len(set(urls)) != len(urls):
            raise ValueError(
                "document record URLs must be unique"
            )

    @staticmethod
    def _normalized_url(url: str) -> str:
        """Return normalized URL used for record checks."""

        parsed = urlsplit(url.strip())
        scheme = parsed.scheme.casefold()
        hostname = (
            parsed.hostname.casefold()
            if parsed.hostname is not None
            else ""
        )
        port = parsed.port

        if (
            port is not None
            and not (
                scheme == "http"
                and port == 80
            )
            and not (
                scheme == "https"
                and port == 443
            )
        ):
            netloc = f"{hostname}:{port}"
        else:
            netloc = hostname

        path = parsed.path or "/"

        if path != "/":
            path = path.rstrip("/")

        return urlunsplit(
            (
                scheme,
                netloc,
                path,
                parsed.query,
                "",
            )
        )
