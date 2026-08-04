"""Validation for research evidence extractor implementations."""

from __future__ import annotations

from app.research.research_evidence_extractor import (
    ResearchEvidenceExtractor,
)
from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionResult,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
)


class ResearchEvidenceExtractorValidator:
    """Validate evidence extractor identity and output."""

    def validate_extractor(
        self,
        extractor: ResearchEvidenceExtractor,
    ) -> None:
        """Validate static extractor identity."""

        if not extractor.name.strip():
            raise ValueError(
                "evidence extractor name must not be blank"
            )

    def validate_result(
        self,
        *,
        extractor: ResearchEvidenceExtractor,
        document: ResearchSourceDocument,
        result: ResearchEvidenceExtractionResult,
    ) -> None:
        """Validate one extraction result against its invocation."""

        self.validate_extractor(extractor)

        if result.document != document:
            raise ValueError(
                "extraction result document must match "
                "the extractor input document"
            )

        if (
            result.extractor.strip().casefold()
            != extractor.name.strip().casefold()
        ):
            raise ValueError(
                "extraction result extractor must match "
                "the evidence extractor name"
            )
