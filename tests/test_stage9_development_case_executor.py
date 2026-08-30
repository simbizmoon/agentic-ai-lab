"""Offline tests for the Stage 9 development case execution adapter."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.evals.stage9_bounded_development_baseline_runner import (
    Stage9DevelopmentCaseExecutionError,
)
from app.evals.stage9_development_case_artifact_writer import (
    Stage9DevelopmentCaseArtifact,
    Stage9DevelopmentCaseArtifactWriter,
)
from app.evals.stage9_development_case_executor import (
    CASE_MAXIMUM_ELAPSED_SECONDS,
    CASE_MAXIMUM_EXTERNAL_REQUESTS,
    CASE_MAXIMUM_PROVIDER_CALLS,
    CASE_MAXIMUM_RECORDED_TOKENS,
    Stage9DevelopmentCaseExecutorAdapter,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopRequest,
    BoundedResearchAgentLoopResult,
    ResearchAgentLoopDecision,
    ResearchAgentLoopRound,
    ResearchAgentLoopUsage,
    ResearchAgentObservation,
    ResearchAgentObservationFailure,
    ResearchAgentObservationStatus,
    ResearchAgentRoundUsage,
    ResearchAgentTerminationReason,
)
from app.schemas.stage9_development_baseline_run import (
    STAGE9_DEVELOPMENT_CASE_IDS,
    Stage9DevelopmentCaseStatus,
    Stage9DevelopmentRunBudget,
    Stage9DevelopmentRunRequest,
)

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


class ControlledLoop:
    def __init__(self) -> None:
        self.requests: list[BoundedResearchAgentLoopRequest] = []

    def run(
        self, *, request: BoundedResearchAgentLoopRequest
    ) -> BoundedResearchAgentLoopResult:
        self.requests.append(request)
        observation = ResearchAgentObservation(
            observation_id="observation-controlled-failure",
            tool_name="bounded_grounded_answer",
            status=ResearchAgentObservationStatus.TOOL_FAILED,
            failure=ResearchAgentObservationFailure(
                code="controlled_failure",
                safe_message="Controlled local test failure.",
                retryable=False,
            ),
        )
        round_usage = ResearchAgentRoundUsage(
            tool_calls=1,
            provider_calls=1,
            recorded_tokens=9,
            elapsed_seconds=0.2,
            external_requests=1,
        )
        round_item = ResearchAgentLoopRound(
            round_number=1,
            plan_id="controlled-plan-001",
            observations=[observation],
            decision=ResearchAgentLoopDecision.TERMINAL_FAILURE,
            rationale="Controlled terminal result.",
            usage=round_usage,
        )
        return BoundedResearchAgentLoopResult(
            request=request,
            rounds=[round_item],
            final_decision=ResearchAgentLoopDecision.TERMINAL_FAILURE,
            termination_reason=ResearchAgentTerminationReason.TERMINAL_FAILURE,
            usage=ResearchAgentLoopUsage(
                rounds=1,
                tool_calls=1,
                provider_calls=1,
                recorded_tokens=9,
                elapsed_seconds=0.2,
                external_requests=1,
            ),
            trace_id="controlled-trace-001",
        )


class ControlledCostEstimator:
    def __init__(self) -> None:
        self.calls = 0

    def estimate(self, *, loop_result, experiment) -> Decimal:
        assert loop_result.usage.recorded_tokens == 9
        assert experiment.plan.manifest.model_name == "gpt-5.6-terra"
        self.calls += 1
        return Decimal("0.07")


def _request() -> Stage9DevelopmentRunRequest:
    return Stage9DevelopmentRunRequest(
        run_id="stage9-development-run-001",
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


def _adapter(tmp_path: Path):
    loop = ControlledLoop()
    estimator = ControlledCostEstimator()
    adapter = Stage9DevelopmentCaseExecutorAdapter(
        experiment=load_approved_baseline(MANIFEST, REVIEW),
        research_loop=loop,
        cost_estimator=estimator,
        artifact_writer=Stage9DevelopmentCaseArtifactWriter(tmp_path),
    )
    return adapter, loop, estimator


def test_executes_locked_question_and_persists_exact_loop_result(
    tmp_path: Path,
) -> None:
    adapter, loop, estimator = _adapter(tmp_path)
    record = adapter.execute(case_id="tech-01", request=_request())
    artifact = Stage9DevelopmentCaseArtifact.model_validate_json(
        Path(record.workflow_artifact_path).read_bytes()
    )

    assert loop.requests[0].goal.startswith("Which NIST AI RMF functions")
    assert "unsupported factual" in " ".join(loop.requests[0].constraints)
    assert record.status is Stage9DevelopmentCaseStatus.FAILED
    assert record.usage.estimated_cost == Decimal("0.07")
    assert artifact.loop_result.trace_id == "controlled-trace-001"
    assert artifact.case_id == "tech-01"
    assert len(artifact.response_model_ids) == 3
    assert estimator.calls == 1


def test_case_budget_is_exact_quarter_of_development_phase(tmp_path: Path) -> None:
    adapter, loop, _ = _adapter(tmp_path)
    adapter.execute(case_id="academic-01", request=_request())
    budget = loop.requests[0].budget

    assert budget.maximum_provider_calls == CASE_MAXIMUM_PROVIDER_CALLS == 4
    assert budget.maximum_external_requests == CASE_MAXIMUM_EXTERNAL_REQUESTS == 6
    assert budget.maximum_recorded_tokens == CASE_MAXIMUM_RECORDED_TOKENS == 30_000
    assert budget.maximum_elapsed_seconds == CASE_MAXIMUM_ELAPSED_SECONDS == 720.0


@pytest.mark.parametrize(
    "case_id",
    ("tech-02", "academic-02", "patent-02", "patent-03", "cross-02", "cross-03"),
)
def test_blind_holdout_is_rejected_before_loop_call(
    tmp_path: Path, case_id: str
) -> None:
    adapter, loop, estimator = _adapter(tmp_path)

    with pytest.raises(Stage9DevelopmentCaseExecutionError, match="development"):
        adapter.execute(case_id=case_id, request=_request())
    assert loop.requests == []
    assert estimator.calls == 0


def test_all_four_development_questions_are_distinct(tmp_path: Path) -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    questions = [
        case.definition.evaluation_input.research_question
        for case in experiment.plan.manifest.cases
        if case.definition.case_id in STAGE9_DEVELOPMENT_CASE_IDS
    ]

    assert len(questions) == 4
    assert len(set(questions)) == 4
