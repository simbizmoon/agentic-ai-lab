"""Validation for research source reader implementations."""

from __future__ import annotations

from app.research.research_source_reader import (
    ResearchSourceReader,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
)


class ResearchSourceReaderValidator:
    """Validate source reader identity and output."""

    def validate_reader(
        self,
        reader: ResearchSourceReader,
    ) -> None:
        """Validate static reader identity."""

        if not reader.name.strip():
            raise ValueError(
                "source reader name must not be blank"
            )

    def validate_document(
        self,
        *,
        reader: ResearchSourceReader,
        candidate: ResearchSourceCandidate,
        document: ResearchSourceDocument,
    ) -> None:
        """Validate one reader output against its invocation."""

        self.validate_reader(reader)

        if document.candidate != candidate:
            raise ValueError(
                "document candidate must match "
                "the reader input candidate"
            )

        if (
            document.reader.strip().casefold()
            != reader.name.strip().casefold()
        ):
            raise ValueError(
                "document reader must match "
                "the source reader name"
            )
