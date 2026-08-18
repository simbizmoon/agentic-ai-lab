"""Runtime composition for patent technical synthesis verification."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from app.config import Settings, load_settings
from app.research.openai_semantic_citation_evaluator import (
    OpenAISemanticCitationEvaluator,
)
from app.research.patent_technical_synthesis_runtime import (
    PatentTechnicalSynthesisRuntimeResult,
)
from app.research.patent_technical_synthesis_verifier import (
    PatentTechnicalSynthesisVerifier,
)
from app.schemas.patent_technical_synthesis_verification import (
    PatentTechnicalSynthesisVerificationResult,
)
from app.services.openai_client import create_openai_client


@dataclass(frozen=True)
class PatentTechnicalSynthesisVerificationRuntimeResult:
    """Bounded synthesis plus support verification."""

    synthesis_result: PatentTechnicalSynthesisRuntimeResult
    verification: PatentTechnicalSynthesisVerificationResult


class PatentTechnicalSynthesisVerificationRuntime:
    """Verify one patent technical synthesis runtime result."""

    def __init__(
        self,
        *,
        verifier: PatentTechnicalSynthesisVerifier,
    ) -> None:
        self._verifier = verifier

    def verify(
        self,
        synthesis_result: PatentTechnicalSynthesisRuntimeResult,
    ) -> PatentTechnicalSynthesisVerificationRuntimeResult:
        report = synthesis_result.report
        synthesis = synthesis_result.synthesis.synthesis
        verification = self._verifier.verify(
            report=report,
            synthesis=synthesis,
        )

        if verification.request_id != report.request_id:
            raise RuntimeError("patent synthesis verification request_id drifted")
        if verification.report_id != report.report_id:
            raise RuntimeError("patent synthesis verification report_id drifted")

        return PatentTechnicalSynthesisVerificationRuntimeResult(
            synthesis_result=synthesis_result,
            verification=verification,
        )


def build_openai_patent_technical_synthesis_verification_runtime(
    *,
    settings: Settings | None = None,
    openai_client: OpenAI | None = None,
) -> PatentTechnicalSynthesisVerificationRuntime:
    """Build OpenAI semantic support verification for patent synthesis."""

    resolved_settings = settings or load_settings()
    resolved_client = openai_client or create_openai_client(resolved_settings)
    evaluator = OpenAISemanticCitationEvaluator(
        client=resolved_client,
        model=resolved_settings.openai_model,
    )
    return PatentTechnicalSynthesisVerificationRuntime(
        verifier=PatentTechnicalSynthesisVerifier(
            evaluator=evaluator,
        )
    )
