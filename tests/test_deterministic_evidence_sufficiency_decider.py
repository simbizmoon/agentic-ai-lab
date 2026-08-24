"""Offline tests for deterministic evidence-sufficiency decisions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.research.deterministic_evidence_sufficiency_decider import (
    DeterministicEvidenceSufficiencyDecider,
)
from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerWorkflowFailure,
    GroundedAnswerWorkflowFailureStage,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopBudget,
    ResearchAgentLoopDecision,
    ResearchAgentLoopUsage,
    ResearchAgentObservation,
    ResearchAgentObservationFailure,
    ResearchAgentObservationStatus,
)
from app.schemas.evidence_sufficiency_decision import (
    EvidenceSufficiencyDecisionCode,
    EvidenceSufficiencyDecisionResult,
)


def _budget(**updates: object) -> BoundedResearchAgentLoopBudget:
    values: dict[str, object] = {
        "maximum_rounds": 3,
        "maximum_tool_calls": 3,
        "maximum_provider_calls": 3,
        "maximum_recorded_tokens": 100,
        "maximum_elapsed_seconds": 10.0,
        "maximum_external_requests": 3,
    }
    values.update(updates)
    return BoundedResearchAgentLoopBudget(**values)


def _usage(**updates: object) -> ResearchAgentLoopUsage:
    values: dict[str, object] = {
        "rounds": 1,
        "tool_calls": 1,
        "provider_calls": 1,
        "recorded_tokens": 10,
        "elapsed_seconds": 0.1,
        "external_requests": 1,
    }
    values.update(updates)
    return ResearchAgentLoopUsage(**values)


def _workflow_observation(
    status: GroundedAnswerWorkflowStatus,
    *,
    retryable: bool | None = None,
    observation_id: str = "observation-001",
) -> ResearchAgentObservation:
    failure = None
    if retryable is not None:
        failure = GroundedAnswerWorkflowFailure(
            stage=(
                GroundedAnswerWorkflowFailureStage.GENERATION
                if status is GroundedAnswerWorkflowStatus.GENERATION_FAILED
                else GroundedAnswerWorkflowFailureStage.VALIDATION
            ),
            code="controlled_failure",
            safe_message="Controlled workflow failure.",
            retryable=retryable,
        )
    workflow_result = BoundedGroundedAnswerWorkflowResult.model_construct(
        status=status, failure=failure
    )
    return ResearchAgentObservation.model_construct(
        observation_id=observation_id,
        tool_name="bounded_grounded_answer",
        status=ResearchAgentObservationStatus.WORKFLOW_RESULT,
        workflow_result=workflow_result,
        failure=None,
    )


def _tool_failure(
    *, retryable: bool, observation_id: str = "observation-tool-failed"
) -> ResearchAgentObservation:
    return ResearchAgentObservation(
        observation_id=observation_id,
        tool_name="bounded_grounded_answer",
        status=ResearchAgentObservationStatus.TOOL_FAILED,
        failure=ResearchAgentObservationFailure(
            code="tool_failed",
            safe_message="The bounded research tool failed.",
            retryable=retryable,
        ),
    )


def _decide(
    observations: list[ResearchAgentObservation],
    *,
    usage: ResearchAgentLoopUsage | None = None,
    budget: BoundedResearchAgentLoopBudget | None = None,
) -> EvidenceSufficiencyDecisionResult:
    return DeterministicEvidenceSufficiencyDecider().decide(
        observations=observations,
        usage_after_round=usage or _usage(),
        budget=budget or _budget(),
    )


@pytest.mark.parametrize(
    ("status", "decision", "code"),
    [
        (
            GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE,
            ResearchAgentLoopDecision.GOAL_ACHIEVED,
            EvidenceSufficiencyDecisionCode.GROUNDED_ANSWER_AVAILABLE,
        ),
        (
            GroundedAnswerWorkflowStatus.ABSTAINED,
            ResearchAgentLoopDecision.ABSTAIN,
            EvidenceSufficiencyDecisionCode.GROUNDED_ABSTENTION,
        ),
        (
            GroundedAnswerWorkflowStatus.INCOMPLETE,
            ResearchAgentLoopDecision.REPLAN,
            EvidenceSufficiencyDecisionCode.WORKFLOW_INCOMPLETE,
        ),
    ],
)
def test_workflow_status_maps_to_deterministic_decision(
    status: GroundedAnswerWorkflowStatus,
    decision: ResearchAgentLoopDecision,
    code: EvidenceSufficiencyDecisionCode,
) -> None:
    result = _decide([_workflow_observation(status)])
    assert result.decision is decision
    assert result.code is code


def test_available_answer_has_priority_over_failure_and_budget() -> None:
    result = _decide(
        [
            _tool_failure(retryable=False),
            _workflow_observation(
                GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE,
                observation_id="observation-answer",
            ),
        ],
        usage=_usage(rounds=3),
    )
    assert result.decision is ResearchAgentLoopDecision.GOAL_ACHIEVED


def test_explicit_abstention_has_priority_over_budget() -> None:
    result = _decide(
        [_workflow_observation(GroundedAnswerWorkflowStatus.ABSTAINED)],
        usage=_usage(tool_calls=3),
    )
    assert result.decision is ResearchAgentLoopDecision.ABSTAIN


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rounds", 3),
        ("tool_calls", 3),
        ("provider_calls", 3),
        ("recorded_tokens", 100),
        ("elapsed_seconds", 10.0),
        ("external_requests", 3),
    ],
)
def test_each_reached_loop_ceiling_terminates_as_budget_exhausted(
    field: str, value: object
) -> None:
    result = _decide(
        [_workflow_observation(GroundedAnswerWorkflowStatus.INCOMPLETE)],
        usage=_usage(**{field: value}),
    )
    assert result.decision is ResearchAgentLoopDecision.BUDGET_EXHAUSTED
    assert result.code is EvidenceSufficiencyDecisionCode.LOOP_BUDGET_REACHED


def test_zero_optional_budget_with_zero_usage_is_not_exhausted() -> None:
    result = _decide(
        [_workflow_observation(GroundedAnswerWorkflowStatus.INCOMPLETE)],
        usage=_usage(provider_calls=0, recorded_tokens=0, external_requests=0),
        budget=_budget(
            maximum_provider_calls=0,
            maximum_recorded_tokens=0,
            maximum_external_requests=0,
        ),
    )
    assert result.decision is ResearchAgentLoopDecision.REPLAN


@pytest.mark.parametrize("retryable", [True, False])
def test_tool_failure_respects_retryability(retryable: bool) -> None:
    result = _decide([_tool_failure(retryable=retryable)])
    assert result.decision is (
        ResearchAgentLoopDecision.REPLAN
        if retryable
        else ResearchAgentLoopDecision.TERMINAL_FAILURE
    )


@pytest.mark.parametrize("retryable", [True, False])
def test_generation_failure_respects_retryability(retryable: bool) -> None:
    result = _decide(
        [
            _workflow_observation(
                GroundedAnswerWorkflowStatus.GENERATION_FAILED,
                retryable=retryable,
            )
        ]
    )
    assert result.decision is (
        ResearchAgentLoopDecision.REPLAN
        if retryable
        else ResearchAgentLoopDecision.TERMINAL_FAILURE
    )


def test_validation_failure_is_terminal() -> None:
    result = _decide(
        [
            _workflow_observation(
                GroundedAnswerWorkflowStatus.VALIDATION_FAILED,
                retryable=False,
            )
        ]
    )
    assert result.decision is ResearchAgentLoopDecision.TERMINAL_FAILURE


def test_conflicting_retryability_requires_human_review() -> None:
    result = _decide(
        [
            _tool_failure(retryable=True, observation_id="retryable"),
            _tool_failure(retryable=False, observation_id="terminal"),
        ]
    )
    assert result.decision is ResearchAgentLoopDecision.HUMAN_REVIEW
    assert result.human_review_recommended is True


def test_unknown_nonterminal_signal_requires_human_review() -> None:
    incomplete_with_nonretryable = [
        _workflow_observation(GroundedAnswerWorkflowStatus.INCOMPLETE),
        _tool_failure(retryable=False),
    ]
    result = _decide(incomplete_with_nonretryable)
    assert result.decision is ResearchAgentLoopDecision.TERMINAL_FAILURE


def test_decider_requires_nonempty_typed_observations() -> None:
    with pytest.raises(ValueError, match="at least one"):
        _decide([])
    with pytest.raises(TypeError, match="ResearchAgentObservation"):
        DeterministicEvidenceSufficiencyDecider().decide(
            observations=[object()],  # type: ignore[list-item]
            usage_after_round=_usage(),
            budget=_budget(),
        )


def test_decision_result_is_strict_frozen_and_consistent() -> None:
    result = _decide([_tool_failure(retryable=True)])
    assert result.replan_recommended is True
    with pytest.raises(ValidationError):
        result.rationale = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="replan recommendation"):
        EvidenceSufficiencyDecisionResult(
            decision=ResearchAgentLoopDecision.REPLAN,
            code=EvidenceSufficiencyDecisionCode.RETRYABLE_FAILURE,
            rationale="Retry is allowed.",
            replan_recommended=False,
            human_review_recommended=False,
        )


def test_contract_contains_no_quality_ranking_or_legal_decisions() -> None:
    forbidden = {
        "quality_score",
        "authority_score",
        "winner",
        "rank",
        "novelty",
        "validity",
        "legal_conclusion",
    }
    assert forbidden.isdisjoint(EvidenceSufficiencyDecisionResult.model_fields)
