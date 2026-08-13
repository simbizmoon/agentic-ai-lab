"""Frozen-input comparison for OpenAI and local bounded research workers."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.budget import ExecutionBudget
from app.config import Settings
from app.research.answer_coverage_evaluation_service import (
    AnswerCoverageEvaluationService,
)
from app.research.claim_relevance_evaluation_service import (
    ClaimRelevanceEvaluationService,
)
from app.research.local_worker_runtime import (
    LocalWorkerSettings,
    build_local_research_workers,
)
from app.research.openai_answer_coverage_evaluator import (
    OpenAIAnswerCoverageEvaluator,
)
from app.research.openai_claim_relevance_evaluator import (
    OpenAIClaimRelevanceEvaluator,
)
from app.research.openai_semantic_citation_evaluator import (
    OpenAISemanticCitationEvaluator,
)
from app.research.semantic_citation_verification_service import (
    SemanticCitationVerificationService,
)
from app.schemas.research_claim import ResearchClaimSet
from app.schemas.research_request import ResearchRequest
from app.services.openai_client import create_openai_client


@dataclass(frozen=True)
class FrozenResearchInput:
    """Validated frozen worker input loaded from one live result artifact."""

    fixture_path: str
    request: ResearchRequest
    claim_set: ResearchClaimSet

    @property
    def evidence_set(self):
        """Return the evidence set embedded in the claim set."""
        return self.claim_set.evidence_set


@dataclass(frozen=True)
class WorkerServices:
    """Three production bounded-worker services."""

    semantic_citation: SemanticCitationVerificationService
    claim_relevance: ClaimRelevanceEvaluationService
    answer_coverage: AnswerCoverageEvaluationService


def load_frozen_input(path: Path) -> FrozenResearchInput:
    """Load request, claim set, and evidence from a persisted live result."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("frozen result JSON must contain an object")

    workspace = data.get("workspace")
    if not isinstance(workspace, dict):
        raise TypeError("workspace must be an object")

    request_data = workspace.get("request")
    claim_set_data = workspace.get("claim_set")

    if not isinstance(request_data, dict):
        raise TypeError("workspace.request must be an object")
    if not isinstance(claim_set_data, dict):
        raise TypeError("workspace.claim_set must be an object")

    request = ResearchRequest.model_validate(
        request_data,
        strict=False,
    )
    claim_set = ResearchClaimSet.model_validate(
        claim_set_data,
        strict=False,
    )

    if request.request_id != claim_set.request_id:
        raise ValueError(
            "frozen request and claim set must share request_id"
        )

    return FrozenResearchInput(
        fixture_path=str(path),
        request=request,
        claim_set=claim_set,
    )


def build_openai_workers(
    *,
    settings: Settings,
    claim_relevance_budget: ExecutionBudget,
) -> WorkerServices:
    """Build OpenAI-backed production worker services."""
    client = create_openai_client(settings)
    return WorkerServices(
        semantic_citation=SemanticCitationVerificationService(
            evaluator=OpenAISemanticCitationEvaluator(
                client=client,
                model=settings.openai_model,
            )
        ),
        claim_relevance=ClaimRelevanceEvaluationService(
            evaluator=OpenAIClaimRelevanceEvaluator(
                client=client,
                model=settings.openai_model,
            ),
            budget=claim_relevance_budget,
        ),
        answer_coverage=AnswerCoverageEvaluationService(
            evaluator=OpenAIAnswerCoverageEvaluator(
                client=client,
                model=settings.openai_model,
            )
        ),
    )


def build_local_workers(
    *,
    settings: LocalWorkerSettings,
    claim_relevance_budget: ExecutionBudget,
) -> WorkerServices:
    """Build local-backed production worker services."""
    bundle = build_local_research_workers(
        settings=settings,
        claim_relevance_budget=claim_relevance_budget,
    )
    return WorkerServices(
        semantic_citation=bundle.semantic_citation_verifier,
        claim_relevance=bundle.claim_relevance_evaluator,
        answer_coverage=bundle.answer_coverage_evaluator,
    )


def evaluate_frozen_input(
    *,
    provider: str,
    frozen: FrozenResearchInput,
    workers: WorkerServices,
) -> dict[str, Any]:
    """Run only the three bounded worker stages on frozen inputs."""
    provider_name = provider.strip().casefold()
    if provider_name not in {"openai", "local"}:
        raise ValueError("provider must be 'openai' or 'local'")

    started = time.perf_counter()

    citation_started = time.perf_counter()
    citation = workers.semantic_citation.verify(
        claim_set=frozen.claim_set,
        evidence_set=frozen.evidence_set,
    )
    citation_wall = max(0.0, time.perf_counter() - citation_started)

    relevance_started = time.perf_counter()
    relevance = workers.claim_relevance.evaluate(
        request=frozen.request,
        claim_set=frozen.claim_set,
    )
    relevance_wall = max(0.0, time.perf_counter() - relevance_started)

    coverage_started = time.perf_counter()
    coverage = workers.answer_coverage.evaluate(
        request=frozen.request,
        claim_set=frozen.claim_set,
    )
    coverage_wall = max(0.0, time.perf_counter() - coverage_started)

    total_wall = max(0.0, time.perf_counter() - started)

    citation_usage = workers.semantic_citation.last_usage
    relevance_usage = workers.claim_relevance.last_usage
    relevance_api_usage = workers.claim_relevance.last_api_usage
    coverage_usage = workers.answer_coverage.last_usage

    return {
        "provider": provider_name,
        "fixture_path": frozen.fixture_path,
        "request_id": frozen.request.request_id,
        "claim_count": len(frozen.claim_set.claims),
        "citation_pair_count": sum(
            len(claim.citations)
            for claim in frozen.claim_set.claims
        ),
        "evidence_count": len(frozen.evidence_set.evidence),
        "citation_verifications": [
            item.model_dump(mode="json")
            for item in citation
        ],
        "claim_relevance_evaluations": [
            item.model_dump(mode="json")
            for item in relevance
        ],
        "answer_coverage_evaluation": coverage.model_dump(mode="json"),
        "wall_seconds": {
            "citation": citation_wall,
            "claim_relevance": relevance_wall,
            "answer_coverage": coverage_wall,
            "total": total_wall,
        },
        "usage": {
            "citation": {
                "attempts": citation_usage.attempts,
                "recorded_tokens": citation_usage.recorded_tokens,
                "elapsed_seconds": citation_usage.elapsed_seconds,
            },
            "claim_relevance_logical": {
                "attempts": relevance_usage.attempts,
                "recorded_tokens": relevance_usage.recorded_tokens,
                "elapsed_seconds": relevance_usage.elapsed_seconds,
            },
            "claim_relevance_api": {
                "attempts": relevance_api_usage.attempts,
                "recorded_tokens": relevance_api_usage.recorded_tokens,
                "elapsed_seconds": relevance_api_usage.elapsed_seconds,
            },
            "answer_coverage": {
                "attempts": coverage_usage.attempts,
                "recorded_tokens": coverage_usage.recorded_tokens,
                "elapsed_seconds": coverage_usage.elapsed_seconds,
            },
        },
    }


def judgment_signature(run: dict[str, Any]) -> dict[str, Any]:
    """Return stable labels used for exact OpenAI/local agreement scoring."""
    citations = run["citation_verifications"]
    relevance = run["claim_relevance_evaluations"]
    coverage = run["answer_coverage_evaluation"]

    return {
        "citation": [
            {
                "claim_id": item["claim_id"],
                "citation_id": item["citation_id"],
                "decision": item["decision"],
                "support_level": item["support_level"],
            }
            for item in citations
        ],
        "claim_relevance": [
            {
                "claim_id": item["claim_id"],
                "relevance_level": item["relevance_level"],
            }
            for item in relevance
        ],
        "answer_coverage": {
            "claim_ids": coverage["claim_ids"],
            "coverage_level": coverage["coverage_level"],
            "coverage_score": coverage["coverage_score"],
        },
    }


def compare_frozen_pair(
    *,
    openai_run: dict[str, Any],
    local_run: dict[str, Any],
) -> dict[str, Any]:
    """Compare labels and execution measurements for one frozen input."""
    openai_sig = judgment_signature(openai_run)
    local_sig = judgment_signature(local_run)

    citation_pairs = list(
        zip(
            openai_sig["citation"],
            local_sig["citation"],
            strict=True,
        )
    )
    relevance_pairs = list(
        zip(
            openai_sig["claim_relevance"],
            local_sig["claim_relevance"],
            strict=True,
        )
    )

    citation_exact = sum(
        left["decision"] == right["decision"]
        and left["support_level"] == right["support_level"]
        for left, right in citation_pairs
    )
    relevance_exact = sum(
        left["relevance_level"] == right["relevance_level"]
        for left, right in relevance_pairs
    )

    return {
        "fixture_path": openai_run["fixture_path"],
        "openai": openai_run,
        "local": local_run,
        "agreement": {
            "citation_exact_count": citation_exact,
            "citation_total": len(citation_pairs),
            "citation_exact_rate": (
                citation_exact / len(citation_pairs)
                if citation_pairs
                else 1.0
            ),
            "claim_relevance_exact_count": relevance_exact,
            "claim_relevance_total": len(relevance_pairs),
            "claim_relevance_exact_rate": (
                relevance_exact / len(relevance_pairs)
                if relevance_pairs
                else 1.0
            ),
            "answer_coverage_level_equal": (
                openai_sig["answer_coverage"]["coverage_level"]
                == local_sig["answer_coverage"]["coverage_level"]
            ),
            "answer_coverage_score_delta_local_minus_openai": (
                float(local_sig["answer_coverage"]["coverage_score"])
                - float(openai_sig["answer_coverage"]["coverage_score"])
            ),
        },
        "wall_delta_local_minus_openai": {
            key: (
                float(local_run["wall_seconds"][key])
                - float(openai_run["wall_seconds"][key])
            )
            for key in (
                "citation",
                "claim_relevance",
                "answer_coverage",
                "total",
            )
        },
    }
