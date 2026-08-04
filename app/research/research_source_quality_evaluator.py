"""Deterministic source quality evaluation."""

from __future__ import annotations

from datetime import date
from typing import ClassVar

from app.schemas.research_request import (
    ResearchSourceType,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
)


class ResearchSourceQualityEvaluator:
    """Evaluate one source document using deterministic rules."""

    _AUTHORITY_SCORES: ClassVar[
        dict[ResearchSourceType, float]
    ] = {
        ResearchSourceType.OFFICIAL_DOCUMENTATION: 1.0,
        ResearchSourceType.GOVERNMENT: 1.0,
        ResearchSourceType.PRIMARY_RESEARCH: 0.95,
        ResearchSourceType.ACADEMIC: 0.9,
        ResearchSourceType.INDUSTRY: 0.7,
        ResearchSourceType.NEWS: 0.6,
        ResearchSourceType.OTHER: 0.4,
    }

    _PRIMARY_SOURCE_SCORES: ClassVar[
        dict[ResearchSourceType, float]
    ] = {
        ResearchSourceType.PRIMARY_RESEARCH: 1.0,
        ResearchSourceType.OFFICIAL_DOCUMENTATION: 0.95,
        ResearchSourceType.GOVERNMENT: 0.9,
        ResearchSourceType.ACADEMIC: 0.8,
        ResearchSourceType.INDUSTRY: 0.5,
        ResearchSourceType.NEWS: 0.3,
        ResearchSourceType.OTHER: 0.2,
    }

    def __init__(
        self,
        *,
        reference_date: date,
        name: str = "deterministic-source-quality",
    ) -> None:
        if not name.strip():
            raise ValueError(
                "name must not be blank"
            )

        self._reference_date = reference_date
        self._name = name

    @property
    def name(self) -> str:
        """Return the evaluator name."""

        return self._name

    def evaluate(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchSourceQualityEvaluation:
        """Evaluate one successfully read source document."""

        if (
            document.status
            is not ResearchSourceDocumentStatus.READ
        ):
            raise ValueError(
                "cannot evaluate a failed document"
            )

        candidate = document.candidate

        authority_score = self._AUTHORITY_SCORES[
            candidate.source_type
        ]
        primary_source_score = (
            self._PRIMARY_SOURCE_SCORES[
                candidate.source_type
            ]
        )
        recency_score = self._recency_score(
            published_at=candidate.published_at
        )
        completeness_score = self._completeness_score(
            document
        )
        traceability_score = self._traceability_score(
            document
        )

        overall_score = round(
            (
                authority_score * 0.30
                + primary_source_score * 0.20
                + recency_score * 0.15
                + completeness_score * 0.20
                + traceability_score * 0.15
            ),
            4,
        )

        strengths, limitations = self._descriptions(
            document=document,
            authority_score=authority_score,
            primary_source_score=primary_source_score,
            recency_score=recency_score,
            completeness_score=completeness_score,
            traceability_score=traceability_score,
        )

        return ResearchSourceQualityEvaluation(
            document=document,
            evaluator=self.name,
            authority_score=authority_score,
            primary_source_score=primary_source_score,
            recency_score=recency_score,
            completeness_score=completeness_score,
            traceability_score=traceability_score,
            overall_score=overall_score,
            quality_level=(
                ResearchSourceQualityEvaluation
                .level_for_score(overall_score)
            ),
            strengths=strengths,
            limitations=limitations,
            metadata={
                "reference_date": (
                    self._reference_date.isoformat()
                ),
                "method": "weighted-deterministic",
            },
        )

    def _recency_score(
        self,
        *,
        published_at: date | None,
    ) -> float:
        """Score publication recency against the reference date."""

        if published_at is None:
            return 0.3

        age_days = (
            self._reference_date - published_at
        ).days

        if age_days < 0:
            return 0.4

        if age_days <= 365:
            return 1.0

        if age_days <= 365 * 3:
            return 0.8

        if age_days <= 365 * 5:
            return 0.6

        if age_days <= 365 * 10:
            return 0.4

        return 0.2

    @staticmethod
    def _completeness_score(
        document: ResearchSourceDocument,
    ) -> float:
        """Score content size and structural completeness."""

        score = 0.0

        if document.character_count >= 2000:
            score += 0.6
        elif document.character_count >= 500:
            score += 0.45
        elif document.character_count >= 100:
            score += 0.3
        else:
            score += 0.15

        if document.sections:
            score += 0.25

        if document.language is not None:
            score += 0.15

        return min(round(score, 4), 1.0)

    @staticmethod
    def _traceability_score(
        document: ResearchSourceDocument,
    ) -> float:
        """Score metadata useful for source traceability."""

        candidate = document.candidate
        score = 0.25

        if candidate.author is not None:
            score += 0.25

        if candidate.publisher is not None:
            score += 0.25

        if candidate.published_at is not None:
            score += 0.25

        return round(score, 4)

    @staticmethod
    def _descriptions(
        *,
        document: ResearchSourceDocument,
        authority_score: float,
        primary_source_score: float,
        recency_score: float,
        completeness_score: float,
        traceability_score: float,
    ) -> tuple[list[str], list[str]]:
        """Return deterministic strengths and limitations."""

        strengths: list[str] = []
        limitations: list[str] = []

        if authority_score >= 0.9:
            strengths.append(
                "High-authority source type"
            )
        else:
            limitations.append(
                "Source authority is limited"
            )

        if primary_source_score >= 0.9:
            strengths.append(
                "Strong primary-source characteristics"
            )
        else:
            limitations.append(
                "Source may rely on secondary reporting"
            )

        if recency_score >= 0.8:
            strengths.append(
                "Publication is recent"
            )
        else:
            limitations.append(
                "Publication is old or undated"
            )

        if completeness_score >= 0.7:
            strengths.append(
                "Document content is structurally complete"
            )
        else:
            limitations.append(
                "Document content is limited"
            )

        if traceability_score >= 0.75:
            strengths.append(
                "Source metadata is traceable"
            )
        else:
            limitations.append(
                "Source metadata is incomplete"
            )

        if not document.sections:
            limitations.append(
                "Document has no extracted sections"
            )

        return strengths, limitations
