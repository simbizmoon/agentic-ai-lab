"""Runtime composition for bounded local research workers."""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.research.answer_coverage_evaluation_service import (
    AnswerCoverageEvaluationService,
)
from app.research.claim_relevance_evaluation_service import (
    ClaimRelevanceEvaluationService,
)
from app.research.local_answer_coverage_evaluator import (
    LocalAnswerCoverageEvaluator,
)
from app.research.local_claim_relevance_evaluator import (
    LocalClaimRelevanceEvaluator,
)
from app.research.local_semantic_citation_evaluator import (
    LocalSemanticCitationEvaluator,
)
from app.research.semantic_citation_verification_service import (
    SemanticCitationVerificationService,
)
from app.services.ollama_client import OllamaClient

LOCAL_WORKER_PROVIDER_ENV = "AIRA_RESEARCH_WORKER_PROVIDER"
LOCAL_WORKER_MODEL_ENV = "AIRA_LOCAL_WORKER_MODEL"
OLLAMA_BASE_URL_ENV = "OLLAMA_BASE_URL"
OLLAMA_TIMEOUT_SECONDS_ENV = "OLLAMA_TIMEOUT_SECONDS"

DEFAULT_LOCAL_WORKER_MODEL = "qwen3.5:4b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120.0

SUPPORTED_WORKER_PROVIDERS = frozenset({"openai", "local"})


@dataclass(frozen=True)
class LocalWorkerSettings:
    """Validated local-worker runtime settings."""

    provider: str
    model: str
    ollama_base_url: str
    ollama_timeout_seconds: float

    @property
    def enabled(self) -> bool:
        """Return whether bounded workers should use Ollama."""
        return self.provider == "local"


@dataclass(frozen=True)
class LocalResearchWorkerBundle:
    """Production services backed by one shared Ollama client."""

    semantic_citation_verifier: SemanticCitationVerificationService
    claim_relevance_evaluator: ClaimRelevanceEvaluationService
    answer_coverage_evaluator: AnswerCoverageEvaluationService


def load_local_worker_settings() -> LocalWorkerSettings:
    """Load bounded research-worker provider settings from environment."""
    provider = os.getenv(
        LOCAL_WORKER_PROVIDER_ENV,
        "openai",
    ).strip().casefold()

    if provider not in SUPPORTED_WORKER_PROVIDERS:
        allowed = ", ".join(sorted(SUPPORTED_WORKER_PROVIDERS))
        raise RuntimeError(
            f"{LOCAL_WORKER_PROVIDER_ENV} must be one of: {allowed}"
        )

    model = os.getenv(
        LOCAL_WORKER_MODEL_ENV,
        DEFAULT_LOCAL_WORKER_MODEL,
    ).strip()
    if not model:
        raise RuntimeError(f"{LOCAL_WORKER_MODEL_ENV} must not be blank")

    base_url = os.getenv(
        OLLAMA_BASE_URL_ENV,
        DEFAULT_OLLAMA_BASE_URL,
    ).strip().rstrip("/")
    if not base_url:
        raise RuntimeError(f"{OLLAMA_BASE_URL_ENV} must not be blank")

    timeout_raw = os.getenv(
        OLLAMA_TIMEOUT_SECONDS_ENV,
        str(DEFAULT_OLLAMA_TIMEOUT_SECONDS),
    ).strip()
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise RuntimeError(
            f"{OLLAMA_TIMEOUT_SECONDS_ENV} must be a number"
        ) from exc

    if not 1.0 <= timeout_seconds <= 600.0:
        raise RuntimeError(
            f"{OLLAMA_TIMEOUT_SECONDS_ENV} must be between 1 and 600"
        )

    return LocalWorkerSettings(
        provider=provider,
        model=model,
        ollama_base_url=base_url,
        ollama_timeout_seconds=timeout_seconds,
    )


def build_local_research_workers(
    *,
    settings: LocalWorkerSettings,
) -> LocalResearchWorkerBundle:
    """Build the three Phase-5-accepted bounded local workers."""
    if not settings.enabled:
        raise ValueError(
            "local research workers require provider='local'"
        )

    client = OllamaClient(
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.ollama_timeout_seconds,
    )

    return LocalResearchWorkerBundle(
        semantic_citation_verifier=(
            SemanticCitationVerificationService(
                evaluator=LocalSemanticCitationEvaluator(
                    client=client,
                    model=settings.model,
                )
            )
        ),
        claim_relevance_evaluator=ClaimRelevanceEvaluationService(
            evaluator=LocalClaimRelevanceEvaluator(
                client=client,
                model=settings.model,
                num_predict=512,
            )
        ),
        answer_coverage_evaluator=AnswerCoverageEvaluationService(
            evaluator=LocalAnswerCoverageEvaluator(
                client=client,
                model=settings.model,
            )
        ),
    )
