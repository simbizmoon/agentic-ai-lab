"""Compose role-routed bounded research workers for live runtime."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from app.budget import ExecutionBudget
from app.research.answer_coverage_evaluation_service import (
    AnswerCoverageEvaluationService,
)
from app.research.claim_relevance_evaluation_service import (
    ClaimRelevanceEvaluationService,
)
from app.research.hybrid_role_policy import (
    HybridResearchRole,
    HybridResearchRolePolicy,
    ResearchExecutionProvider,
)
from app.research.local_worker_runtime import (
    LocalResearchWorkerBundle,
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


@dataclass(frozen=True)
class HybridBoundedResearchWorkerBundle:
    """Resolved bounded worker services with provider provenance."""

    semantic_citation_verifier: SemanticCitationVerificationService
    claim_relevance_evaluator: ClaimRelevanceEvaluationService
    answer_coverage_evaluator: AnswerCoverageEvaluationService
    role_policy: HybridResearchRolePolicy

    def provider_for(
        self,
        role: HybridResearchRole,
    ) -> ResearchExecutionProvider:
        """Return the provider used for one bounded worker role."""

        return self.role_policy.provider_for(role)


def legacy_compatible_role_policy(
    *,
    local_worker_settings: LocalWorkerSettings,
) -> HybridResearchRolePolicy:
    """Map the existing global worker switch into an explicit role policy."""

    bounded_provider = (
        ResearchExecutionProvider.LOCAL
        if local_worker_settings.enabled
        else ResearchExecutionProvider.OPENAI
    )

    return HybridResearchRolePolicy(
        task_decomposition=ResearchExecutionProvider.DETERMINISTIC,
        query_planning=ResearchExecutionProvider.DETERMINISTIC,
        source_quality=ResearchExecutionProvider.DETERMINISTIC,
        document_selection=ResearchExecutionProvider.DETERMINISTIC,
        evidence_relevance=ResearchExecutionProvider.OPENAI,
        claim_generation=ResearchExecutionProvider.OPENAI,
        semantic_citation=bounded_provider,
        claim_relevance=bounded_provider,
        answer_coverage=bounded_provider,
        synthesis=ResearchExecutionProvider.DETERMINISTIC,
        final_quality_review=ResearchExecutionProvider.OPENAI,
    )


def build_hybrid_bounded_research_workers(
    *,
    role_policy: HybridResearchRolePolicy,
    local_worker_settings: LocalWorkerSettings,
    openai_client: OpenAI,
    openai_model: str,
    claim_relevance_budget: ExecutionBudget | None = None,
) -> HybridBoundedResearchWorkerBundle:
    """Build bounded worker services according to explicit role routing."""

    bounded_roles = (
        HybridResearchRole.SEMANTIC_CITATION,
        HybridResearchRole.CLAIM_RELEVANCE,
        HybridResearchRole.ANSWER_COVERAGE,
    )
    providers = {
        role_policy.provider_for(role)
        for role in bounded_roles
    }

    unsupported = providers - {
        ResearchExecutionProvider.OPENAI,
        ResearchExecutionProvider.LOCAL,
    }
    if unsupported:
        values = ", ".join(sorted(item.value for item in unsupported))
        raise ValueError(
            "bounded research workers do not support providers: "
            f"{values}"
        )

    local_workers: LocalResearchWorkerBundle | None = None
    if ResearchExecutionProvider.LOCAL in providers:
        if not local_worker_settings.enabled:
            raise ValueError(
                "role policy requires local bounded workers but "
                "AIRA_RESEARCH_WORKER_PROVIDER is not 'local'"
            )
        local_workers = build_local_research_workers(
            settings=local_worker_settings,
            claim_relevance_budget=claim_relevance_budget,
        )

    semantic_citation_verifier = _semantic_citation_verifier(
        provider=role_policy.provider_for(
            HybridResearchRole.SEMANTIC_CITATION
        ),
        local_workers=local_workers,
        openai_client=openai_client,
        openai_model=openai_model,
    )
    claim_relevance_evaluator = _claim_relevance_evaluator(
        provider=role_policy.provider_for(
            HybridResearchRole.CLAIM_RELEVANCE
        ),
        local_workers=local_workers,
        openai_client=openai_client,
        openai_model=openai_model,
        budget=claim_relevance_budget,
    )
    answer_coverage_evaluator = _answer_coverage_evaluator(
        provider=role_policy.provider_for(
            HybridResearchRole.ANSWER_COVERAGE
        ),
        local_workers=local_workers,
        openai_client=openai_client,
        openai_model=openai_model,
    )

    return HybridBoundedResearchWorkerBundle(
        semantic_citation_verifier=semantic_citation_verifier,
        claim_relevance_evaluator=claim_relevance_evaluator,
        answer_coverage_evaluator=answer_coverage_evaluator,
        role_policy=role_policy,
    )


def _semantic_citation_verifier(
    *,
    provider: ResearchExecutionProvider,
    local_workers: LocalResearchWorkerBundle | None,
    openai_client: OpenAI,
    openai_model: str,
) -> SemanticCitationVerificationService:
    if provider is ResearchExecutionProvider.LOCAL:
        if local_workers is None:
            raise ValueError("local worker bundle is required")
        return local_workers.semantic_citation_verifier

    return SemanticCitationVerificationService(
        evaluator=OpenAISemanticCitationEvaluator(
            client=openai_client,
            model=openai_model,
        )
    )


def _claim_relevance_evaluator(
    *,
    provider: ResearchExecutionProvider,
    local_workers: LocalResearchWorkerBundle | None,
    openai_client: OpenAI,
    openai_model: str,
    budget: ExecutionBudget | None,
) -> ClaimRelevanceEvaluationService:
    if provider is ResearchExecutionProvider.LOCAL:
        if local_workers is None:
            raise ValueError("local worker bundle is required")
        return local_workers.claim_relevance_evaluator

    return ClaimRelevanceEvaluationService(
        evaluator=OpenAIClaimRelevanceEvaluator(
            client=openai_client,
            model=openai_model,
        ),
        budget=budget,
    )


def _answer_coverage_evaluator(
    *,
    provider: ResearchExecutionProvider,
    local_workers: LocalResearchWorkerBundle | None,
    openai_client: OpenAI,
    openai_model: str,
) -> AnswerCoverageEvaluationService:
    if provider is ResearchExecutionProvider.LOCAL:
        if local_workers is None:
            raise ValueError("local worker bundle is required")
        return local_workers.answer_coverage_evaluator

    return AnswerCoverageEvaluationService(
        evaluator=OpenAIAnswerCoverageEvaluator(
            client=openai_client,
            model=openai_model,
        )
    )
