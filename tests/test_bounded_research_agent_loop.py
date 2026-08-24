"""Offline tests for the bounded provider-neutral research-agent loop contract."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

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
    BoundedResearchAgentLoopBudget,
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
from app.schemas.document_chunk import DocumentChunk
from app.schemas.grounded_answer_result import GroundedAnswerResult
from app.schemas.rag_context_packing import (
    PackedRagContextItem,
    RagContextPackingBudget,
    RagContextPackingRequest,
    RagContextPackingResult,
    RagContextPackingUsage,
)
from app.schemas.retrieval_result import RetrievalResult
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)
from app.services.text_generation import TokenUsage


def _stage6_retrieval(position: int) -> RetrievalResult:
    text = f"Exact evidence {position}."
    return RetrievalResult(
        chunk=DocumentChunk(
            document_id=f"document-{position}",
            chunk_id=f"chunk-{position}",
            ordinal=position - 1,
            text=text,
            start_char=0,
            end_char=len(text),
            metadata={"source_id": f"source-{position}"},
        ),
        score=round(1.0 - position / 10, 2),
        rank=position,
    )


def _stage6_packing(*, empty: bool) -> RagContextPackingResult:
    retrievals = [] if empty else [_stage6_retrieval(1)]
    request = RagContextPackingRequest(
        candidates=retrievals,
        budget=RagContextPackingBudget(
            maximum_items=1,
            maximum_utf8_bytes=1000,
            maximum_estimated_tokens=100,
            token_estimator_id="offline-stage7-contract-v1",
        ),
    )
    included = [
        PackedRagContextItem(
            retrieval=item,
            original_position=index,
            packed_rank=index,
            incremental_utf8_bytes=len(item.chunk.text.encode()),
            incremental_estimated_tokens=3,
        )
        for index, item in enumerate(retrievals, start=1)
    ]
    return RagContextPackingResult(
        request=request,
        included=included,
        omitted=[],
        usage=RagContextPackingUsage(
            candidate_count=len(retrievals),
            included_count=len(retrievals),
            omitted_count=0,
            context_utf8_bytes=sum(
                len(item.chunk.text.encode()) for item in retrievals
            ),
            estimated_tokens=3 * len(retrievals),
        ),
        was_truncated=False,
    )


def _stage6_request(*, empty: bool) -> GroundedAnswerWorkflowRequest:
    return GroundedAnswerWorkflowRequest(
        question="What is supported?",
        packing=_stage6_packing(empty=empty),
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


class _FullySupportedEvaluator:
    def evaluate(
        self, *, claim_text: str, evidence_excerpt: str
    ) -> SemanticCitationEvaluationResult:
        del claim_text, evidence_excerpt
        return SemanticCitationEvaluationResult(
            judgment=SemanticCitationJudgment(
                support_level=SemanticCitationSupportLevel.FULLY_SUPPORTED,
                entailment_score=1.0,
                rationale="Controlled offline judgment.",
                issues=[],
            ),
            decision=ResearchCitationDecision.VERIFIED,
            response_id="validation-001",
            request_id="request-001",
            usage=TokenUsage(
                input_tokens=2,
                cached_input_tokens=0,
                output_tokens=1,
                reasoning_tokens=0,
                total_tokens=3,
            ),
            elapsed_seconds=0.001,
        )


def _workflow(
    status: GroundedAnswerWorkflowStatus,
) -> BoundedGroundedAnswerWorkflowResult:
    empty = status is GroundedAnswerWorkflowStatus.ABSTAINED
    request = _stage6_request(empty=empty)
    retrievals = [item.retrieval for item in request.packing.included]
    context = build_rag_context(retrievals)
    answer = GroundedAnswerResult(
        question=request.question,
        answer=(
            "The supplied evidence is insufficient."
            if empty
            else "The evidence supports the statement. [S1]"
        ),
        citations=context.citations,
        cited_ids=[] if empty else ["S1"],
        response_id="response-stage7-contract",
        model_name="controlled-local-generator",
        evidence_available=bool(retrievals),
    )
    validation = BoundedAnswerCitationVerifier(
        evaluator=_FullySupportedEvaluator()
    ).verify(
        request=AnswerCitationValidationRequest(
            question=request.question,
            answer=answer.answer,
            context=context,
            evidence_retrievals=retrievals,
            citation_required=bool(retrievals),
            budget=request.citation_validation_budget,
            response_id=answer.response_id,
            model_name=answer.model_name,
        )
    )
    return BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=status,
        generation_usage=GroundedAnswerGenerationUsage(
            attempts=1, recorded_tokens=5, elapsed_seconds=0.01
        ),
        generation_budget_exhausted=False,
        answer=answer,
        citation_validation=validation,
        abstention_detected=empty,
    )


def _budget(**updates: object) -> BoundedResearchAgentLoopBudget:
    values: dict[str, object] = {
        "maximum_rounds": 2,
        "maximum_tool_calls": 2,
        "maximum_provider_calls": 2,
        "maximum_recorded_tokens": 100,
        "maximum_elapsed_seconds": 10.0,
        "maximum_external_requests": 2,
    }
    values.update(updates)
    return BoundedResearchAgentLoopBudget(**values)


def _request(**updates: object) -> BoundedResearchAgentLoopRequest:
    values: dict[str, object] = {
        "goal": "Produce a grounded cross-source answer",
        "constraints": ["Preserve exact provenance"],
        "allowed_tools": ["bounded_grounded_answer"],
        "budget": _budget(),
    }
    values.update(updates)
    return BoundedResearchAgentLoopRequest(**values)


def _observation(
    status: GroundedAnswerWorkflowStatus = GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE,
    *,
    observation_id: str = "observation-001",
    tool_name: str = "bounded_grounded_answer",
) -> ResearchAgentObservation:
    return ResearchAgentObservation(
        observation_id=observation_id,
        tool_name=tool_name,
        status=ResearchAgentObservationStatus.WORKFLOW_RESULT,
        workflow_result=_workflow(status),
    )


def _failure_observation() -> ResearchAgentObservation:
    return ResearchAgentObservation(
        observation_id="observation-failed",
        tool_name="bounded_grounded_answer",
        status=ResearchAgentObservationStatus.TOOL_FAILED,
        failure=ResearchAgentObservationFailure(
            code="provider_unavailable",
            safe_message="The provider is temporarily unavailable",
            retryable=True,
        ),
    )


def _round(
    decision: ResearchAgentLoopDecision = ResearchAgentLoopDecision.GOAL_ACHIEVED,
    *,
    observations: list[ResearchAgentObservation] | None = None,
    round_number: int = 1,
    plan_id: str = "plan-001",
    usage: ResearchAgentRoundUsage | None = None,
) -> ResearchAgentLoopRound:
    selected = observations if observations is not None else [_observation()]
    return ResearchAgentLoopRound(
        round_number=round_number,
        plan_id=plan_id,
        observations=selected,
        decision=decision,
        rationale="The grounded answer satisfies the bounded research goal",
        usage=usage
        or ResearchAgentRoundUsage(
            tool_calls=len(selected),
            provider_calls=1,
            recorded_tokens=20,
            elapsed_seconds=0.25,
            external_requests=1,
        ),
    )


def _result_values(
    decision: ResearchAgentLoopDecision = ResearchAgentLoopDecision.GOAL_ACHIEVED,
    *,
    rounds: list[ResearchAgentLoopRound] | None = None,
    request: BoundedResearchAgentLoopRequest | None = None,
) -> dict[str, object]:
    selected = rounds or [_round(decision)]
    reason = {
        ResearchAgentLoopDecision.GOAL_ACHIEVED: ResearchAgentTerminationReason.GOAL_ACHIEVED,
        ResearchAgentLoopDecision.ABSTAIN: ResearchAgentTerminationReason.ABSTAINED,
        ResearchAgentLoopDecision.HUMAN_REVIEW: ResearchAgentTerminationReason.HUMAN_REVIEW_REQUIRED,
        ResearchAgentLoopDecision.TERMINAL_FAILURE: ResearchAgentTerminationReason.TERMINAL_FAILURE,
        ResearchAgentLoopDecision.BUDGET_EXHAUSTED: ResearchAgentTerminationReason.BUDGET_EXHAUSTED,
    }[decision]
    return {
        "request": request or _request(),
        "rounds": selected,
        "final_decision": decision,
        "termination_reason": reason,
        "usage": ResearchAgentLoopUsage(
            rounds=len(selected),
            tool_calls=sum(item.usage.tool_calls for item in selected),
            provider_calls=sum(item.usage.provider_calls for item in selected),
            recorded_tokens=sum(item.usage.recorded_tokens for item in selected),
            elapsed_seconds=sum(item.usage.elapsed_seconds for item in selected),
            external_requests=sum(item.usage.external_requests for item in selected),
        ),
        "trace_id": "trace-stage7-001",
    }


def test_goal_achieved_preserves_stage6_observation_and_usage() -> None:
    result = BoundedResearchAgentLoopResult(**_result_values())

    assert result.final_decision is ResearchAgentLoopDecision.GOAL_ACHIEVED
    assert result.rounds[0].observations[0].workflow_result is not None
    assert result.rounds[0].observations[0].workflow_result.status is (
        GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE
    )
    assert result.usage.tool_calls == 1
    assert result.trace_id == "trace-stage7-001"


def test_abstention_requires_and_accepts_stage6_abstention() -> None:
    observation = _observation(GroundedAnswerWorkflowStatus.ABSTAINED)
    round_item = _round(ResearchAgentLoopDecision.ABSTAIN, observations=[observation])

    result = BoundedResearchAgentLoopResult(
        **_result_values(ResearchAgentLoopDecision.ABSTAIN, rounds=[round_item])
    )

    assert result.termination_reason is ResearchAgentTerminationReason.ABSTAINED


@pytest.mark.parametrize(
    ("decision", "reason"),
    [
        (
            ResearchAgentLoopDecision.HUMAN_REVIEW,
            ResearchAgentTerminationReason.HUMAN_REVIEW_REQUIRED,
        ),
        (
            ResearchAgentLoopDecision.TERMINAL_FAILURE,
            ResearchAgentTerminationReason.TERMINAL_FAILURE,
        ),
    ],
)
def test_nonanswer_terminal_states_preserve_tool_failure(
    decision: ResearchAgentLoopDecision,
    reason: ResearchAgentTerminationReason,
) -> None:
    round_item = _round(decision, observations=[_failure_observation()])
    values = _result_values(decision, rounds=[round_item])

    result = BoundedResearchAgentLoopResult(**values)

    assert result.termination_reason is reason
    assert result.rounds[0].observations[0].failure is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maximum_rounds", 0),
        ("maximum_tool_calls", 0),
        ("maximum_provider_calls", -1),
        ("maximum_recorded_tokens", -1),
        ("maximum_elapsed_seconds", 0.0),
        ("maximum_elapsed_seconds", float("inf")),
        ("maximum_external_requests", -1),
    ],
)
def test_budget_rejects_invalid_boundaries(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _budget(**{field: value})


@pytest.mark.parametrize(
    "updates",
    [
        {"goal": " goal"},
        {"constraints": [""]},
        {"constraints": ["Exact", "exact"]},
        {"allowed_tools": []},
        {"allowed_tools": ["Tool", "tool"]},
    ],
)
def test_request_rejects_ambiguous_or_non_normalized_values(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _request(**updates)


def test_models_are_strict_frozen_and_forbid_unknown_fields() -> None:
    request = _request()
    with pytest.raises(ValidationError):
        BoundedResearchAgentLoopBudget(
            maximum_rounds="2",
            maximum_tool_calls=2,
            maximum_provider_calls=2,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
            maximum_external_requests=2,
        )
    with pytest.raises(ValidationError):
        BoundedResearchAgentLoopRequest(
            goal="Goal", allowed_tools=["tool"], budget=_budget(), unknown=True
        )
    with pytest.raises(ValidationError):
        request.goal = "Changed"


def test_observation_requires_exactly_one_payload_matching_status() -> None:
    with pytest.raises(ValidationError, match="requires only workflow_result"):
        ResearchAgentObservation(
            observation_id="observation-001",
            tool_name="tool",
            status=ResearchAgentObservationStatus.WORKFLOW_RESULT,
        )
    with pytest.raises(ValidationError, match="requires only failure"):
        ResearchAgentObservation(
            observation_id="observation-001",
            tool_name="tool",
            status=ResearchAgentObservationStatus.TOOL_FAILED,
            workflow_result=_workflow(GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE),
        )


def test_round_requires_unique_observations_and_exact_call_count() -> None:
    duplicate = _observation()
    with pytest.raises(ValidationError, match="unique within a round"):
        _round(
            observations=[duplicate, duplicate],
            usage=ResearchAgentRoundUsage(
                tool_calls=2,
                provider_calls=0,
                recorded_tokens=0,
                elapsed_seconds=0.0,
                external_requests=0,
            ),
        )
    with pytest.raises(ValidationError, match="tool_calls must match"):
        _round(
            usage=ResearchAgentRoundUsage(
                tool_calls=0,
                provider_calls=0,
                recorded_tokens=0,
                elapsed_seconds=0.0,
                external_requests=0,
            )
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("round_number", "round numbers must be sequential"),
        ("plan_id", "requires a new plan ID"),
        ("observation_id", "unique across the loop"),
        ("tool_name", "non-allowed tool"),
    ],
)
def test_result_rejects_broken_loop_identity(mutation: str, message: str) -> None:
    first = _round(ResearchAgentLoopDecision.REPLAN)
    second_observation = _observation(observation_id="observation-002")
    second = _round(
        observations=[second_observation], round_number=2, plan_id="plan-002"
    )
    if mutation == "round_number":
        second = second.model_copy(update={"round_number": 3})
    elif mutation == "plan_id":
        second = second.model_copy(update={"plan_id": "plan-001"})
    elif mutation == "observation_id":
        second_observation = second_observation.model_copy(
            update={"observation_id": "observation-001"}
        )
        second = second.model_copy(update={"observations": [second_observation]})
    else:
        second_observation = second_observation.model_copy(
            update={"tool_name": "shell"}
        )
        second = second.model_copy(update={"observations": [second_observation]})

    with pytest.raises(ValidationError, match=message):
        BoundedResearchAgentLoopResult(**_result_values(rounds=[first, second]))


def test_result_rejects_usage_final_decision_and_reason_mismatches() -> None:
    values = _result_values()
    bad_usage = deepcopy(values)
    bad_usage["usage"] = ResearchAgentLoopUsage(
        rounds=1,
        tool_calls=1,
        provider_calls=1,
        recorded_tokens=21,
        elapsed_seconds=0.25,
        external_requests=1,
    )
    with pytest.raises(ValidationError, match="aggregate loop usage"):
        BoundedResearchAgentLoopResult(**bad_usage)

    bad_decision = deepcopy(values)
    bad_decision["final_decision"] = ResearchAgentLoopDecision.ABSTAIN
    bad_decision["termination_reason"] = ResearchAgentTerminationReason.ABSTAINED
    with pytest.raises(ValidationError, match="final decision must match"):
        BoundedResearchAgentLoopResult(**bad_decision)

    bad_reason = deepcopy(values)
    bad_reason["termination_reason"] = ResearchAgentTerminationReason.TERMINAL_FAILURE
    with pytest.raises(ValidationError, match="termination reason must match"):
        BoundedResearchAgentLoopResult(**bad_reason)


def test_continue_and_replan_cannot_be_final_decisions() -> None:
    for decision in (
        ResearchAgentLoopDecision.CONTINUE,
        ResearchAgentLoopDecision.REPLAN,
    ):
        round_item = _round(decision)
        values = _result_values(rounds=[round_item])
        values["final_decision"] = decision
        values["termination_reason"] = ResearchAgentTerminationReason.TERMINAL_FAILURE
        with pytest.raises(ValidationError, match="terminal final decision"):
            BoundedResearchAgentLoopResult(**values)


def test_over_budget_requires_explicit_budget_exhaustion() -> None:
    request = _request(budget=_budget(maximum_provider_calls=0))
    with pytest.raises(ValidationError, match="over-budget loop"):
        BoundedResearchAgentLoopResult(**_result_values(request=request))


def test_budget_exhaustion_requires_a_reached_ceiling_and_accepts_equality() -> None:
    round_item = _round(
        ResearchAgentLoopDecision.BUDGET_EXHAUSTED,
        observations=[_failure_observation()],
    )
    with pytest.raises(ValidationError, match="requires a reached loop ceiling"):
        BoundedResearchAgentLoopResult(
            **_result_values(
                ResearchAgentLoopDecision.BUDGET_EXHAUSTED, rounds=[round_item]
            )
        )

    request = _request(budget=_budget(maximum_rounds=1))
    result = BoundedResearchAgentLoopResult(
        **_result_values(
            ResearchAgentLoopDecision.BUDGET_EXHAUSTED,
            rounds=[round_item],
            request=request,
        )
    )
    assert result.termination_reason is ResearchAgentTerminationReason.BUDGET_EXHAUSTED


def test_answer_and_abstention_decisions_require_matching_workflow_status() -> None:
    failed_round = _round(
        ResearchAgentLoopDecision.GOAL_ACHIEVED,
        observations=[_failure_observation()],
    )
    with pytest.raises(ValidationError, match="available grounded answer"):
        BoundedResearchAgentLoopResult(**_result_values(rounds=[failed_round]))

    available_round = _round(
        ResearchAgentLoopDecision.ABSTAIN,
        observations=[_observation(GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE)],
    )
    with pytest.raises(ValidationError, match="abstained grounded workflow"):
        BoundedResearchAgentLoopResult(
            **_result_values(
                ResearchAgentLoopDecision.ABSTAIN, rounds=[available_round]
            )
        )


def test_contract_has_no_quality_ranking_or_legal_conclusion_fields() -> None:
    forbidden = {
        "quality_score",
        "authority_score",
        "winner",
        "rank",
        "novelty",
        "validity",
        "legal_conclusion",
    }
    stage7_contract_fields = set().union(
        BoundedResearchAgentLoopBudget.model_fields,
        BoundedResearchAgentLoopRequest.model_fields,
        ResearchAgentObservationFailure.model_fields,
        ResearchAgentObservation.model_fields,
        ResearchAgentRoundUsage.model_fields,
        ResearchAgentLoopRound.model_fields,
        ResearchAgentLoopUsage.model_fields,
        BoundedResearchAgentLoopResult.model_fields,
    )
    assert forbidden.isdisjoint(stage7_contract_fields)
