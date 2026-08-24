"""Offline tests for bounded grounded-answer workflow contracts."""

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
    GroundedAnswerWorkflowFailure,
    GroundedAnswerWorkflowFailureStage,
    GroundedAnswerWorkflowRequest,
    GroundedAnswerWorkflowStatus,
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


def _retrieval(position: int) -> RetrievalResult:
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


def _packing(*, empty: bool = False) -> RagContextPackingResult:
    retrievals = [] if empty else [_retrieval(1), _retrieval(2)]
    request = RagContextPackingRequest(
        candidates=retrievals,
        budget=RagContextPackingBudget(
            maximum_items=2,
            maximum_utf8_bytes=1000,
            maximum_estimated_tokens=100,
            token_estimator_id="offline-test-v1",
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


def _citation_budget() -> AnswerCitationValidationBudget:
    return AnswerCitationValidationBudget(
        maximum_statements=10,
        maximum_pairs=10,
        maximum_attempts=10,
        maximum_recorded_tokens=100,
        maximum_elapsed_seconds=10.0,
    )


def _request(*, empty: bool = False) -> GroundedAnswerWorkflowRequest:
    return GroundedAnswerWorkflowRequest(
        question="What is supported?",
        packing=_packing(empty=empty),
        generation_budget=GroundedAnswerGenerationBudget(
            maximum_attempts=1,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
        ),
        citation_validation_budget=_citation_budget(),
    )


def _answer(request: GroundedAnswerWorkflowRequest, *, abstain: bool = False):
    retrievals = [item.retrieval for item in request.packing.included]
    context = build_rag_context(retrievals)
    text = (
        "The supplied evidence is insufficient."
        if abstain
        else "First fact. [S1]\nSecond fact. [S2]"
    )
    return GroundedAnswerResult(
        question=request.question,
        answer=text,
        citations=context.citations,
        cited_ids=[] if abstain else ["S1", "S2"],
        response_id="response-001",
        model_name="controlled-generator",
        evidence_available=bool(retrievals),
    )


class Evaluator:
    def __init__(self, levels: list[SemanticCitationSupportLevel]) -> None:
        self.levels = levels
        self.calls = 0

    def evaluate(self, *, claim_text: str, evidence_excerpt: str):
        del claim_text, evidence_excerpt
        level = self.levels[self.calls]
        self.calls += 1
        accepted = level is SemanticCitationSupportLevel.FULLY_SUPPORTED
        return SemanticCitationEvaluationResult(
            judgment=SemanticCitationJudgment(
                support_level=level,
                entailment_score=1.0 if accepted else 0.0,
                rationale="Controlled offline judgment.",
                issues=[] if accepted else ["fixture"],
            ),
            decision=(
                ResearchCitationDecision.VERIFIED
                if accepted
                else ResearchCitationDecision.REJECTED
            ),
            response_id=f"validation-{self.calls}",
            request_id=f"request-{self.calls}",
            usage=TokenUsage(
                input_tokens=2,
                cached_input_tokens=0,
                output_tokens=1,
                reasoning_tokens=0,
                total_tokens=3,
            ),
            elapsed_seconds=0.001,
        )


def _validation(request, answer, levels):
    retrievals = [item.retrieval for item in request.packing.included]
    return BoundedAnswerCitationVerifier(evaluator=Evaluator(levels)).verify(
        request=AnswerCitationValidationRequest(
            question=request.question,
            answer=answer.answer,
            context=build_rag_context(retrievals),
            evidence_retrievals=retrievals,
            citation_required=bool(retrievals),
            budget=request.citation_validation_budget,
            response_id=answer.response_id,
            model_name=answer.model_name,
        )
    )


def _usage(**changes: object) -> GroundedAnswerGenerationUsage:
    values = {"attempts": 1, "recorded_tokens": 5, "elapsed_seconds": 0.01}
    values.update(changes)
    return GroundedAnswerGenerationUsage(**values)  # type: ignore[arg-type]


def _available() -> BoundedGroundedAnswerWorkflowResult:
    request = _request()
    answer = _answer(request)
    validation = _validation(
        request,
        answer,
        [SemanticCitationSupportLevel.FULLY_SUPPORTED] * 2,
    )
    return BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE,
        generation_usage=_usage(),
        generation_budget_exhausted=False,
        answer=answer,
        citation_validation=validation,
        abstention_detected=False,
    )


def test_available_result_preserves_exact_generation_and_validation() -> None:
    value = _available()
    assert value.status is GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE
    assert value.citation_validation is not None
    assert value.citation_validation.usage.evaluated_pair_count == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maximum_attempts", 0),
        ("maximum_attempts", 101),
        ("maximum_recorded_tokens", 0),
        ("maximum_elapsed_seconds", 0.0),
        ("maximum_elapsed_seconds", float("inf")),
    ],
)
def test_generation_budget_rejects_invalid_values(field: str, value: object) -> None:
    values = {
        "maximum_attempts": 1,
        "maximum_recorded_tokens": 10,
        "maximum_elapsed_seconds": 1.0,
    }
    values[field] = value
    with pytest.raises(ValidationError):
        GroundedAnswerGenerationBudget(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("question", ["", "   ", " padded "])
def test_request_requires_normalized_question(question: str) -> None:
    values = _request().model_dump(mode="python")
    values["question"] = question
    with pytest.raises(ValidationError):
        GroundedAnswerWorkflowRequest.model_validate(values)


def test_request_and_result_are_strict_and_frozen() -> None:
    request = _request()
    with pytest.raises(ValidationError):
        GroundedAnswerWorkflowRequest(**request.model_dump(mode="python"), hidden=True)
    with pytest.raises(ValidationError):
        request.question = "changed"  # type: ignore[misc]


def test_generation_failure_requires_safe_generation_error() -> None:
    request = _request()
    value = BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=GroundedAnswerWorkflowStatus.GENERATION_FAILED,
        generation_usage=_usage(),
        generation_budget_exhausted=False,
        answer=None,
        citation_validation=None,
        abstention_detected=False,
        failure=GroundedAnswerWorkflowFailure(
            stage=GroundedAnswerWorkflowFailureStage.GENERATION,
            code="model_request_failed",
            safe_message="Grounded answer request failed.",
            retryable=True,
        ),
    )
    assert value.failure is not None and value.failure.retryable is True


def test_validation_failure_requires_failed_exact_validation() -> None:
    request = _request()
    answer = _answer(request)
    validation = _validation(
        request, answer, [SemanticCitationSupportLevel.CONTRADICTED] * 2
    )
    value = BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=GroundedAnswerWorkflowStatus.VALIDATION_FAILED,
        generation_usage=_usage(),
        generation_budget_exhausted=False,
        answer=answer,
        citation_validation=validation,
        abstention_detected=False,
        failure=GroundedAnswerWorkflowFailure(
            stage=GroundedAnswerWorkflowFailureStage.VALIDATION,
            code="citation_validation_failed",
            safe_message="Generated answer citations were not supported.",
            retryable=False,
        ),
    )
    assert value.status is GroundedAnswerWorkflowStatus.VALIDATION_FAILED


def test_validation_execution_failure_can_preserve_answer_without_result() -> None:
    request = _request()
    value = BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=GroundedAnswerWorkflowStatus.VALIDATION_FAILED,
        generation_usage=_usage(),
        generation_budget_exhausted=False,
        answer=_answer(request),
        citation_validation=None,
        abstention_detected=False,
        failure=GroundedAnswerWorkflowFailure(
            stage=GroundedAnswerWorkflowFailureStage.VALIDATION,
            code="citation_validation_error",
            safe_message="Generated answer citation validation failed.",
            retryable=False,
        ),
    )
    assert value.citation_validation is None


def test_incomplete_accepts_generation_budget_exhaustion_before_validation() -> None:
    request = _request()
    value = BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=GroundedAnswerWorkflowStatus.INCOMPLETE,
        generation_usage=_usage(recorded_tokens=101),
        generation_budget_exhausted=True,
        answer=_answer(request),
        citation_validation=None,
        abstention_detected=False,
    )
    assert value.status is GroundedAnswerWorkflowStatus.INCOMPLETE


def test_abstention_with_empty_evidence_is_complete_and_validated() -> None:
    request = _request(empty=True)
    answer = _answer(request, abstain=True)
    validation = _validation(request, answer, [])
    value = BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=GroundedAnswerWorkflowStatus.ABSTAINED,
        generation_usage=_usage(),
        generation_budget_exhausted=False,
        answer=answer,
        citation_validation=validation,
        abstention_detected=True,
    )
    assert value.citation_validation is not None
    assert value.citation_validation.usage.attempts == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "question",
        "answer_text",
        "validation_budget",
        "evidence",
        "response_id",
        "model_name",
        "answer_citation",
    ],
)
def test_result_rejects_cross_stage_identity_drift(mutation: str) -> None:
    values = deepcopy(_available().model_dump(mode="python"))
    if mutation == "question":
        values["answer"]["question"] = "Different?"
    elif mutation == "answer_text":
        values["citation_validation"]["request"]["answer"] = "Drift [S1]"
    elif mutation == "validation_budget":
        values["citation_validation"]["request"]["budget"]["maximum_attempts"] = 9
    elif mutation == "evidence":
        values["citation_validation"]["request"]["evidence_retrievals"][0]["chunk"][
            "text"
        ] = "Drift"
    elif mutation == "response_id":
        values["citation_validation"]["request"]["response_id"] = "drift"
    elif mutation == "model_name":
        values["citation_validation"]["request"]["model_name"] = "drift"
    else:
        values["answer"]["citations"][0]["document_id"] = "drift"
    with pytest.raises(ValidationError):
        BoundedGroundedAnswerWorkflowResult.model_validate(values)


@pytest.mark.parametrize(
    "mutation",
    [
        "available_without_validation",
        "available_abstained",
        "available_with_failure",
        "generation_failure_with_answer",
        "generation_failure_wrong_stage",
        "validation_failure_passed",
        "incomplete_without_exhaustion",
        "abstained_flag_false",
    ],
)
def test_result_rejects_status_output_mismatch(mutation: str) -> None:
    values = deepcopy(_available().model_dump(mode="python"))
    if mutation == "available_without_validation":
        values["citation_validation"] = None
    elif mutation == "available_abstained":
        values["abstention_detected"] = True
    elif mutation == "available_with_failure":
        values["failure"] = {
            "stage": "validation",
            "code": "x",
            "safe_message": "Failure.",
            "retryable": False,
        }
    elif mutation == "generation_failure_with_answer":
        values["status"] = "generation_failed"
        values["failure"] = {
            "stage": "generation",
            "code": "x",
            "safe_message": "Failure.",
            "retryable": True,
        }
    elif mutation == "generation_failure_wrong_stage":
        values["status"] = "generation_failed"
        values["answer"] = None
        values["citation_validation"] = None
        values["failure"] = {
            "stage": "validation",
            "code": "x",
            "safe_message": "Failure.",
            "retryable": False,
        }
    elif mutation == "validation_failure_passed":
        values["status"] = "validation_failed"
        values["failure"] = {
            "stage": "validation",
            "code": "x",
            "safe_message": "Failure.",
            "retryable": False,
        }
    elif mutation == "incomplete_without_exhaustion":
        values["status"] = "incomplete"
        values["citation_validation"] = None
    else:
        values["status"] = "abstained"
    with pytest.raises(ValidationError):
        BoundedGroundedAnswerWorkflowResult.model_validate(values)


def test_over_budget_usage_requires_exhausted_marker() -> None:
    values = deepcopy(_available().model_dump(mode="python"))
    values["generation_usage"]["recorded_tokens"] = 101
    with pytest.raises(ValidationError, match="mark exhausted"):
        BoundedGroundedAnswerWorkflowResult.model_validate(values)


def test_contract_has_no_quality_or_legal_fields() -> None:
    forbidden = {
        "winner",
        "best_source",
        "source_authority",
        "paper_quality",
        "patent_quality",
        "legal_conclusion",
    }
    assert forbidden.isdisjoint(BoundedGroundedAnswerWorkflowResult.model_fields)
