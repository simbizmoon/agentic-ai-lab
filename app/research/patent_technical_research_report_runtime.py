"""Top-level patent technical research, synthesis, and verification runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from app.config import Settings, load_settings
from app.research.patent_technical_relevance_runtime import (
    PatentTechnicalRelevanceRuntime,
    PatentTechnicalRelevanceRuntimeResult,
    build_openai_epo_patent_technical_relevance_runtime,
)
from app.research.patent_technical_synthesis_runtime import (
    PatentTechnicalSynthesisRuntime,
    PatentTechnicalSynthesisRuntimeResult,
    build_openai_patent_technical_synthesis_runtime,
)
from app.research.patent_technical_synthesis_verification_runtime import (
    PatentTechnicalSynthesisVerificationRuntime,
    PatentTechnicalSynthesisVerificationRuntimeResult,
    build_openai_patent_technical_synthesis_verification_runtime,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.services.openai_client import create_openai_client


class PatentTechnicalRelevanceRuntimeProtocol(Protocol):
    """Minimal contract for patent technical-relevance execution."""

    def execute(
        self,
        request: PatentResearchRequest,
        *,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentTechnicalRelevanceRuntimeResult: ...


class PatentTechnicalSynthesisRuntimeProtocol(Protocol):
    """Minimal contract for bounded patent synthesis."""

    def synthesize(
        self,
        *,
        request: PatentResearchRequest,
        relevance_result: PatentTechnicalRelevanceRuntimeResult,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentTechnicalSynthesisRuntimeResult: ...


class PatentTechnicalVerificationRuntimeProtocol(Protocol):
    """Minimal contract for synthesis support verification."""

    def verify(
        self,
        synthesis_result: PatentTechnicalSynthesisRuntimeResult,
    ) -> PatentTechnicalSynthesisVerificationRuntimeResult: ...


@dataclass(frozen=True)
class PatentTechnicalResearchReportRuntimeResult:
    """One end-to-end bounded patent technical research result."""

    relevance: PatentTechnicalRelevanceRuntimeResult
    synthesis: PatentTechnicalSynthesisRuntimeResult
    verification: PatentTechnicalSynthesisVerificationRuntimeResult

    @property
    def accepted(self) -> bool:
        """Return whether all synthesized prose is fully evidence-supported."""

        return self.verification.verification.accepted


class PatentTechnicalResearchReportRuntime:
    """Run collection, relevance, synthesis, and support verification."""

    def __init__(
        self,
        *,
        relevance_runtime: PatentTechnicalRelevanceRuntimeProtocol,
        synthesis_runtime: PatentTechnicalSynthesisRuntimeProtocol,
        verification_runtime: PatentTechnicalVerificationRuntimeProtocol,
    ) -> None:
        self._relevance_runtime = relevance_runtime
        self._synthesis_runtime = synthesis_runtime
        self._verification_runtime = verification_runtime

    def execute(
        self,
        request: PatentResearchRequest,
        *,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentTechnicalResearchReportRuntimeResult:
        """Execute the complete bounded patent technical research slice."""

        cleaned_request_id = request_id.strip()
        cleaned_task_id = task_id.strip()

        if not cleaned_request_id:
            raise ValueError("request_id must not be blank")
        if not cleaned_task_id:
            raise ValueError("task_id must not be blank")

        relevance = self._relevance_runtime.execute(
            request,
            request_id=cleaned_request_id,
            task_id=cleaned_task_id,
        )

        synthesis = self._synthesis_runtime.synthesize(
            request=request,
            relevance_result=relevance,
            request_id=cleaned_request_id,
            task_id=cleaned_task_id,
        )

        if synthesis.report.request_id != cleaned_request_id:
            raise RuntimeError("patent synthesis report request_id drifted")
        if synthesis.report.task_id != cleaned_task_id:
            raise RuntimeError("patent synthesis report task_id drifted")

        verification = self._verification_runtime.verify(synthesis)

        if verification.synthesis_result != synthesis:
            raise RuntimeError(
                "patent synthesis verification did not preserve synthesis result"
            )
        if verification.verification.request_id != cleaned_request_id:
            raise RuntimeError("patent synthesis verification request_id drifted")
        if verification.verification.report_id != synthesis.report.report_id:
            raise RuntimeError("patent synthesis verification report_id drifted")

        return PatentTechnicalResearchReportRuntimeResult(
            relevance=relevance,
            synthesis=synthesis,
            verification=verification,
        )


def build_openai_epo_patent_technical_research_report_runtime(
    *,
    settings: Settings | None = None,
    openai_client: OpenAI | None = None,
    relevance_runtime: PatentTechnicalRelevanceRuntime | None = None,
    synthesis_runtime: PatentTechnicalSynthesisRuntime | None = None,
    verification_runtime: (PatentTechnicalSynthesisVerificationRuntime | None) = None,
) -> PatentTechnicalResearchReportRuntime:
    """Build the end-to-end patent technical research runtime."""

    resolved_settings = settings or load_settings()
    resolved_client = openai_client or create_openai_client(resolved_settings)

    resolved_relevance = (
        relevance_runtime
        if relevance_runtime is not None
        else build_openai_epo_patent_technical_relevance_runtime(
            settings=resolved_settings,
            openai_client=resolved_client,
        )
    )
    resolved_synthesis = (
        synthesis_runtime
        if synthesis_runtime is not None
        else build_openai_patent_technical_synthesis_runtime(
            settings=resolved_settings,
            openai_client=resolved_client,
        )
    )
    resolved_verification = (
        verification_runtime
        if verification_runtime is not None
        else build_openai_patent_technical_synthesis_verification_runtime(
            settings=resolved_settings,
            openai_client=resolved_client,
        )
    )

    return PatentTechnicalResearchReportRuntime(
        relevance_runtime=resolved_relevance,
        synthesis_runtime=resolved_synthesis,
        verification_runtime=resolved_verification,
    )
