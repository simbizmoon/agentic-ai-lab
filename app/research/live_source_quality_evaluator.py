"""Deterministic source-quality evaluation for live web documents."""

from __future__ import annotations

from urllib.parse import urlsplit

from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_document import (
    ResearchSourceDocument,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
)


class LiveWebSourceQualityEvaluator:
    """Score live sources using source type and host signals."""

    def evaluate(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchSourceQualityEvaluation:
        """Return a conservative deterministic quality score."""

        candidate = document.candidate
        host = (
            urlsplit(candidate.url).hostname or ""
        ).casefold()
        source_type = candidate.source_type

        authority = self._authority_score(
            host=host,
            source_type=source_type,
        )
        primary = self._primary_score(
            host=host,
            source_type=source_type,
        )
        recency = 0.8 if candidate.published_at else 0.5
        completeness = min(
            1.0,
            max(0.35, document.character_count / 4_000),
        )
        traceability = 1.0

        overall = round(
            0.30 * authority
            + 0.25 * primary
            + 0.10 * recency
            + 0.15 * completeness
            + 0.20 * traceability,
            4,
        )
        level = (
            ResearchSourceQualityEvaluation
            .level_for_score(overall)
        )
        strengths: list[str] = [
            "Source URL and extracted text are traceable.",
        ]
        limitations: list[str] = []

        if authority >= 0.9:
            strengths.append(
                "Host or declared source type indicates "
                "an authoritative source."
            )
        elif authority < 0.6:
            limitations.append(
                "Authority could not be established from "
                "the available metadata."
            )

        if primary >= 0.9:
            strengths.append(
                "Source appears to be primary or official."
            )
        elif primary < 0.6:
            limitations.append(
                "Source appears secondary or its primary "
                "status is unknown."
            )

        if candidate.published_at is None:
            limitations.append(
                "Publication date was not available."
            )

        return ResearchSourceQualityEvaluation(
            document=document,
            evaluator="live-web-source-quality",
            authority_score=authority,
            primary_source_score=primary,
            recency_score=recency,
            completeness_score=round(completeness, 4),
            traceability_score=traceability,
            overall_score=overall,
            quality_level=level,
            strengths=strengths,
            limitations=limitations,
            metadata={
                "method": "deterministic-host-and-type",
                "host": host,
            },
        )

    @staticmethod
    def _authority_score(
        *,
        host: str,
        source_type: ResearchSourceType,
    ) -> float:
        if source_type in {
            ResearchSourceType.GOVERNMENT,
            ResearchSourceType.OFFICIAL_DOCUMENTATION,
            ResearchSourceType.PRIMARY_RESEARCH,
        }:
            return 0.95

        if source_type is ResearchSourceType.ACADEMIC:
            return 0.9

        if (
            host.endswith(
                (
                    ".gov",
                    ".go.kr",
                    ".edu",
                    ".ac.kr",
                )
            )
            or ".gov." in host
            or ".edu." in host
            or host in {"arxiv.org", "doi.org"}
        ):
            return 0.9

        if host.startswith(
            ("docs.", "developer.", "developers.")
        ):
            return 0.85

        if source_type is ResearchSourceType.NEWS:
            return 0.65

        if source_type is ResearchSourceType.INDUSTRY:
            return 0.7

        return 0.5

    @staticmethod
    def _primary_score(
        *,
        host: str,
        source_type: ResearchSourceType,
    ) -> float:
        if source_type in {
            ResearchSourceType.OFFICIAL_DOCUMENTATION,
            ResearchSourceType.PRIMARY_RESEARCH,
            ResearchSourceType.GOVERNMENT,
        }:
            return 0.95

        if source_type is ResearchSourceType.ACADEMIC:
            return 0.8

        if host.startswith(
            ("docs.", "developer.", "developers.")
        ):
            return 0.9

        if (
            host.endswith((".gov", ".go.kr"))
            or ".gov." in host
        ):
            return 0.9

        return 0.45
