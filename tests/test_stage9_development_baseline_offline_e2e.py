"""Offline E2E tests for the complete Stage 9 development baseline path."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.evals.stage9_bounded_development_baseline_runner import (
    BoundedStage9DevelopmentBaselineRunner,
)
from app.evals.stage9_conservative_cost_estimator import (
    ConservativeStage9RecordedTokenCostEstimator,
)
from app.evals.stage9_development_case_artifact_writer import (
    Stage9DevelopmentCaseArtifact,
    Stage9DevelopmentCaseArtifactWriter,
)
from app.evals.stage9_development_case_executor import (
    Stage9DevelopmentCaseExecutorAdapter,
)
from app.rag.context_builder import build_rag_context
from app.research.bounded_answer_citation_verifier import (
    BoundedAnswerCitationVerifier,
)
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationEvaluationResult,
)
from app.research.research_citation_verifier_executor import ResearchCitationDecision
from app.schemas.answer_citation_validation import (
    AnswerCitationValidationBudget,
    AnswerCitationValidationRequest,
)
from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerGenerationBudget,
    GroundedAnswerGenerationUsage,
    GroundedAnswerWorkflowRequest,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopRequest,
    BoundedResearchAgentLoopResult,
    ResearchAgentLoopDecision,
    ResearchAgentLoopRound,
    ResearchAgentLoopUsage,
    ResearchAgentObservation,
    ResearchAgentObservationStatus,
    ResearchAgentRoundUsage,
    ResearchAgentTerminationReason,
)
from app.schemas.grounded_answer_result import GroundedAnswerResult
from app.schemas.rag_context_packing import (
    RagContextPackingBudget,
    RagContextPackingRequest,
    RagContextPackingResult,
    RagContextPackingUsage,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)
from app.schemas.stage9_development_baseline_run import (
    STAGE9_BLIND_HOLDOUT_CASE_IDS,
    STAGE9_DEVELOPMENT_CASE_IDS,
    Stage9DevelopmentCaseStatus,
    Stage9DevelopmentRunBudget,
    Stage9DevelopmentRunRequest,
    Stage9DevelopmentRunStatus,
)
from app.services.text_generation import TokenUsage

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)
MANIFEST_SHA = "60179543f5290136d434d4f4c72598af8f74eb569a1d06b43c7490320d81e191"
REVIEW_SHA = "f36c0b7bee7cc9548f2f3a36946e4b49293883b69349b4499f2c80d27190cae7"


class _UnusedEvaluator:
    def evaluate(
        self, *, claim_text: str, evidence_excerpt: str
    ) -> SemanticCitationEvaluationResult:
        del claim_text, evidence_excerpt
        return SemanticCitationEvaluationResult(
            judgment=SemanticCitationJudgment(
                support_level=SemanticCitationSupportLevel.FULLY_SUPPORTED,
                entailment_score=1.0,
                rationale="Unused controlled local judgment.",
                issues=[],
            ),
            decision=ResearchCitationDecision.VERIFIED,
            response_id="unused-response",
            request_id="unused-request",
            usage=TokenUsage(
                input_tokens=0,
                cached_input_tokens=0,
                output_tokens=0,
                reasoning_tokens=0,
                total_tokens=0,
            ),
            elapsed_seconds=0.0,
        )


def _abstained_workflow(question: str) -> BoundedGroundedAnswerWorkflowResult:
    packing = RagContextPackingResult(
        request=RagContextPackingRequest(
            candidates=[],
            budget=RagContextPackingBudget(
                maximum_items=4,
                maximum_utf8_bytes=8_000,
                maximum_estimated_tokens=2_000,
                token_estimator_id="stage9-offline-empty-evidence-v1",
            ),
        ),
        included=[],
        omitted=[],
        usage=RagContextPackingUsage(
            candidate_count=0,
            included_count=0,
            omitted_count=0,
            context_utf8_bytes=0,
            estimated_tokens=0,
        ),
        was_truncated=False,
    )
    request = GroundedAnswerWorkflowRequest(
        question=question,
        packing=packing,
        generation_budget=GroundedAnswerGenerationBudget(
            maximum_attempts=1,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
        ),
        citation_validation_budget=AnswerCitationValidationBudget(
            maximum_statements=10,
            maximum_pairs=10,
            maximum_attempts=10,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
        ),
    )
    context = build_rag_context([])
    answer = GroundedAnswerResult(
        question=question,
        answer="The supplied evidence is insufficient.",
        citations=context.citations,
        cited_ids=[],
        response_id="controlled-abstention-response",
        model_name="controlled-local-generator",
        evidence_available=False,
    )
    validation = BoundedAnswerCitationVerifier(evaluator=_UnusedEvaluator()).verify(
        request=AnswerCitationValidationRequest(
            question=question,
            answer=answer.answer,
            context=context,
            evidence_retrievals=[],
            citation_required=False,
            budget=request.citation_validation_budget,
            response_id=answer.response_id,
            model_name=answer.model_name,
        )
    )
    return BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=GroundedAnswerWorkflowStatus.ABSTAINED,
        generation_usage=GroundedAnswerGenerationUsage(
            attempts=1,
            recorded_tokens=5,
            elapsed_seconds=0.01,
        ),
        generation_budget_exhausted=False,
        answer=answer,
        citation_validation=validation,
        abstention_detected=True,
    )


class ControlledAbstainingResearchLoop:
    def __init__(self) -> None:
        self.goals: list[str] = []

    def run(
        self, *, request: BoundedResearchAgentLoopRequest
    ) -> BoundedResearchAgentLoopResult:
        self.goals.append(request.goal)
        workflow = _abstained_workflow(request.goal)
        observation = ResearchAgentObservation(
            observation_id=f"observation-{len(self.goals):04d}",
            tool_name="bounded_grounded_answer",
            status=ResearchAgentObservationStatus.WORKFLOW_RESULT,
            workflow_result=workflow,
        )
        usage = ResearchAgentRoundUsage(
            tool_calls=1,
            provider_calls=1,
            recorded_tokens=5,
            elapsed_seconds=0.01,
            external_requests=1,
        )
        round_item = ResearchAgentLoopRound(
            round_number=1,
            plan_id=f"controlled-plan-{len(self.goals):04d}",
            observations=[observation],
            decision=ResearchAgentLoopDecision.ABSTAIN,
            rationale="No evidence was supplied by the controlled offline fixture.",
            usage=usage,
        )
        return BoundedResearchAgentLoopResult(
            request=request,
            rounds=[round_item],
            final_decision=ResearchAgentLoopDecision.ABSTAIN,
            termination_reason=ResearchAgentTerminationReason.ABSTAINED,
            usage=ResearchAgentLoopUsage(
                rounds=1,
                tool_calls=1,
                provider_calls=1,
                recorded_tokens=5,
                elapsed_seconds=0.01,
                external_requests=1,
            ),
            trace_id=f"controlled-trace-{len(self.goals):04d}",
        )


def _run_request() -> Stage9DevelopmentRunRequest:
    return Stage9DevelopmentRunRequest(
        run_id="stage9-offline-e2e-001",
        manifest_sha256=MANIFEST_SHA,
        review_sha256=REVIEW_SHA,
        case_ids=STAGE9_DEVELOPMENT_CASE_IDS,
        repetitions_per_case=1,
        budget=Stage9DevelopmentRunBudget(
            maximum_provider_requests=16,
            maximum_external_requests=24,
            maximum_recorded_tokens=120_000,
            maximum_elapsed_seconds=2_880.0,
            maximum_estimated_cost=Decimal("1.50"),
            currency="USD",
        ),
    )


def test_complete_development_path_persists_four_ordered_auditable_cases(
    tmp_path: Path,
) -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    loop = ControlledAbstainingResearchLoop()
    executor = Stage9DevelopmentCaseExecutorAdapter(
        experiment=experiment,
        research_loop=loop,
        cost_estimator=ConservativeStage9RecordedTokenCostEstimator(),
        artifact_writer=Stage9DevelopmentCaseArtifactWriter(tmp_path),
    )
    result = BoundedStage9DevelopmentBaselineRunner(
        experiment=experiment,
        executor=executor,
    ).run(_run_request())

    assert result.status is Stage9DevelopmentRunStatus.COMPLETED
    assert tuple(record.case_id for record in result.case_records) == (
        STAGE9_DEVELOPMENT_CASE_IDS
    )
    assert all(
        record.status is Stage9DevelopmentCaseStatus.ABSTAINED
        for record in result.case_records
    )
    assert result.usage.provider_requests == 4
    assert result.usage.external_requests == 4
    assert result.usage.recorded_tokens == 20
    assert result.usage.estimated_cost == Decimal("0.000240")
    assert len(loop.goals) == 4 == len(set(loop.goals))
    assert not STAGE9_BLIND_HOLDOUT_CASE_IDS.intersection(
        record.case_id for record in result.case_records
    )

    for position, record in enumerate(result.case_records, start=1):
        artifact = Stage9DevelopmentCaseArtifact.model_validate_json(
            Path(record.workflow_artifact_path).read_bytes()
        )
        assert artifact.case_id == STAGE9_DEVELOPMENT_CASE_IDS[position - 1]
        assert artifact.loop_result.trace_id == f"controlled-trace-{position:04d}"
        assert artifact.manifest_sha256 == MANIFEST_SHA
        assert artifact.review_sha256 == REVIEW_SHA


def test_no_provider_or_network_client_is_required_for_offline_e2e(
    tmp_path: Path,
) -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    loop = ControlledAbstainingResearchLoop()
    executor = Stage9DevelopmentCaseExecutorAdapter(
        experiment=experiment,
        research_loop=loop,
        cost_estimator=ConservativeStage9RecordedTokenCostEstimator(),
        artifact_writer=Stage9DevelopmentCaseArtifactWriter(tmp_path),
    )

    result = BoundedStage9DevelopmentBaselineRunner(
        experiment=experiment,
        executor=executor,
    ).run(_run_request())

    assert result.status is Stage9DevelopmentRunStatus.COMPLETED
    assert result.usage.estimated_cost < result.request.budget.maximum_estimated_cost
