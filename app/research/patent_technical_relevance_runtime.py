"""End-to-end patent collection plus technical-relevance evidence composition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from app.config import Settings, load_settings
from app.research.patent_research_runtime import (
    PatentResearchRuntimeResult,
    build_openai_epo_patent_research_runtime,
)
from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceResult,
    PatentTechnicalRelevanceEvidenceRuntime,
    build_openai_patent_technical_relevance_evidence_runtime,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.services.openai_client import create_openai_client


class PatentCollectionRuntimeProtocol(Protocol):
    """Minimal natural-language patent collection contract."""

    def execute(
        self,
        request: PatentResearchRequest,
    ) -> PatentResearchRuntimeResult:
        """Return one request-bound bounded patent collection."""


class PatentEvidenceRuntimeProtocol(Protocol):
    """Minimal verified-patent technical-evidence contract."""

    def extract(
        self,
        execution,
        *,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentTechnicalRelevanceEvidenceResult:
        """Return technical-relevance evidence for one patent execution."""


PatentEvidenceRuntimeFactory = Callable[
    [PatentResearchRequest],
    PatentEvidenceRuntimeProtocol,
]


@dataclass(frozen=True)
class PatentTechnicalRelevanceRuntimeResult:
    """One patent collection and its technical-relevance evidence."""

    research: PatentResearchRuntimeResult
    relevance: PatentTechnicalRelevanceEvidenceResult


class PatentTechnicalRelevanceRuntime:
    """Run bounded patent collection followed by technical evidence analysis."""

    def __init__(
        self,
        *,
        patent_runtime: PatentCollectionRuntimeProtocol,
        evidence_runtime_factory: PatentEvidenceRuntimeFactory,
    ) -> None:
        self._patent_runtime = patent_runtime
        self._evidence_runtime_factory = evidence_runtime_factory

    def execute(
        self,
        request: PatentResearchRequest,
        *,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentTechnicalRelevanceRuntimeResult:
        """Collect verified patents, then extract request-bound evidence."""

        research = self._patent_runtime.execute(request)

        if research.execution.collection.request != request:
            raise RuntimeError(
                "patent research result was not bound to the exact request"
            )

        evidence_runtime = self._evidence_runtime_factory(request)
        relevance = evidence_runtime.extract(
            research.execution,
            request_id=request_id,
            task_id=task_id,
        )

        if relevance.execution != research.execution:
            raise RuntimeError(
                "technical relevance result did not preserve patent execution"
            )

        return PatentTechnicalRelevanceRuntimeResult(
            research=research,
            relevance=relevance,
        )


def build_openai_epo_patent_technical_relevance_runtime(
    *,
    settings: Settings | None = None,
    openai_client: OpenAI | None = None,
    patent_runtime: PatentCollectionRuntimeProtocol | None = None,
) -> PatentTechnicalRelevanceRuntime:
    """Build shared-client patent collection plus relevance composition."""

    resolved_settings = settings or load_settings()
    resolved_client = openai_client or create_openai_client(resolved_settings)

    resolved_patent_runtime = (
        patent_runtime
        if patent_runtime is not None
        else build_openai_epo_patent_research_runtime(
            settings=resolved_settings,
            openai_client=resolved_client,
        )
    )

    def build_evidence_runtime(
        request: PatentResearchRequest,
    ) -> PatentTechnicalRelevanceEvidenceRuntime:
        return build_openai_patent_technical_relevance_evidence_runtime(
            request,
            settings=resolved_settings,
            openai_client=resolved_client,
        )

    return PatentTechnicalRelevanceRuntime(
        patent_runtime=resolved_patent_runtime,
        evidence_runtime_factory=build_evidence_runtime,
    )
