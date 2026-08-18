"""Composition of deterministic patent reports and bounded synthesis."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from app.config import Settings, load_settings
from app.research.openai_patent_technical_synthesizer import (
    OpenAIPatentTechnicalSynthesizer,
    PatentTechnicalSynthesisGenerationResult,
)
from app.research.patent_technical_relevance_runtime import (
    PatentTechnicalRelevanceRuntimeResult,
)
from app.research.patent_technical_report_builder import (
    DeterministicPatentTechnicalReportBuilder,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_technical_report import PatentTechnicalResearchReport
from app.services.openai_client import create_openai_client


@dataclass(frozen=True)
class PatentTechnicalSynthesisRuntimeResult:
    """One deterministic patent report and its bounded synthesis."""

    report: PatentTechnicalResearchReport
    synthesis: PatentTechnicalSynthesisGenerationResult


class PatentTechnicalSynthesisRuntime:
    """Build a deterministic report, then synthesize bounded prose."""

    def __init__(
        self,
        *,
        report_builder: DeterministicPatentTechnicalReportBuilder,
        synthesizer: OpenAIPatentTechnicalSynthesizer,
    ) -> None:
        self._report_builder = report_builder
        self._synthesizer = synthesizer

    def synthesize(
        self,
        *,
        request: PatentResearchRequest,
        relevance_result: PatentTechnicalRelevanceRuntimeResult,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentTechnicalSynthesisRuntimeResult:
        """Return bounded synthesis while preserving exact runtime binding."""

        if relevance_result.research.execution.collection.request != request:
            raise RuntimeError(
                "patent relevance runtime result was not bound to the exact request"
            )

        if relevance_result.relevance.execution != relevance_result.research.execution:
            raise RuntimeError(
                "patent relevance runtime result did not preserve execution"
            )

        report = self._report_builder.build(
            request=request,
            relevance=relevance_result.relevance,
            request_id=request_id,
            task_id=task_id,
        )

        synthesis = self._synthesizer.synthesize(report)

        return PatentTechnicalSynthesisRuntimeResult(
            report=report,
            synthesis=synthesis,
        )


def build_openai_patent_technical_synthesis_runtime(
    *,
    settings: Settings | None = None,
    openai_client: OpenAI | None = None,
) -> PatentTechnicalSynthesisRuntime:
    """Build deterministic report plus OpenAI bounded synthesis."""

    resolved_settings = settings or load_settings()
    resolved_client = openai_client or create_openai_client(resolved_settings)

    return PatentTechnicalSynthesisRuntime(
        report_builder=DeterministicPatentTechnicalReportBuilder(),
        synthesizer=OpenAIPatentTechnicalSynthesizer(
            client=resolved_client,
            model=resolved_settings.openai_model,
        ),
    )
