"""Offline tests for bounded grounded-answer orchestration."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.rag.grounded_answer_service import GroundedAnswerServiceError
from app.research.bounded_answer_citation_verifier import BoundedAnswerCitationVerifier
from app.research.bounded_grounded_answer_orchestrator import (
    BoundedGroundedAnswerOrchestrator,
    GroundedAnswerGenerationAttempt,
)
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationEvaluationResult,
)
from app.research.research_citation_verifier_executor import ResearchCitationDecision
from app.schemas.answer_citation_validation import AnswerCitationValidationBudget
from app.schemas.bounded_grounded_answer_workflow import (
    GroundedAnswerGenerationBudget,
    GroundedAnswerWorkflowRequest,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.grounded_answer_result import GroundedAnswerResult
from app.schemas.rag_context import RagContext
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


def _request(*, empty: bool = False, tokens: int = 100):
    return GroundedAnswerWorkflowRequest(
        question="What is supported?",
        packing=_packing(empty=empty),
        generation_budget=GroundedAnswerGenerationBudget(
            maximum_attempts=1,
            maximum_recorded_tokens=tokens,
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


def _tokens(total: int) -> TokenUsage:
    return TokenUsage(
        input_tokens=total - 1,
        cached_input_tokens=0,
        output_tokens=1,
        reasoning_tokens=0,
        total_tokens=total,
    )


@dataclass
class Generator:
    text: str
    tokens: int = 5
    error: Exception | None = None

    def generate(self, *, question: str, context: RagContext):
        if self.error is not None:
            raise self.error
        cited_ids = [
            item.citation_id
            for item in context.citations
            if f"[{item.citation_id}]" in self.text
        ]
        return GroundedAnswerGenerationAttempt(
            answer=GroundedAnswerResult(
                question=question,
                answer=self.text,
                citations=context.citations,
                cited_ids=cited_ids,
                response_id="response-001",
                model_name="controlled-generator",
                evidence_available=bool(context.citations),
            ),
            usage=_tokens(self.tokens),
            elapsed_seconds=0.01,
        )


@dataclass
class Evaluator:
    levels: list[SemanticCitationSupportLevel]
    calls: int = 0

    def evaluate(self, *, claim_text: str, evidence_excerpt: str):
        del claim_text, evidence_excerpt
        level = self.levels[self.calls]
        self.calls += 1
        supported = level is SemanticCitationSupportLevel.FULLY_SUPPORTED
        return SemanticCitationEvaluationResult(
            judgment=SemanticCitationJudgment(
                support_level=level,
                entailment_score=1.0 if supported else 0.0,
                rationale="Controlled offline judgment.",
                issues=[] if supported else ["fixture"],
            ),
            decision=(
                ResearchCitationDecision.VERIFIED
                if supported
                else ResearchCitationDecision.REJECTED
            ),
            response_id=f"validation-{self.calls}",
            request_id=f"request-{self.calls}",
            usage=_tokens(3),
            elapsed_seconds=0.001,
        )


def _run(request, generator, evaluator):
    return BoundedGroundedAnswerOrchestrator(
        generator=generator,
        citation_verifier=BoundedAnswerCitationVerifier(evaluator=evaluator),
    ).run(request=request)


def test_supported_answer_is_available() -> None:
    result = _run(
        _request(),
        Generator("First. [S1]\nSecond. [S2]"),
        Evaluator([SemanticCitationSupportLevel.FULLY_SUPPORTED] * 2),
    )
    assert result.status is GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE
    assert result.generation_usage.attempts == 1
    assert result.citation_validation is not None
    assert result.citation_validation.usage.evaluated_pair_count == 2


def test_contradicted_answer_is_validation_failed() -> None:
    result = _run(
        _request(),
        Generator("Contradicted. [S1]"),
        Evaluator([SemanticCitationSupportLevel.CONTRADICTED]),
    )
    assert result.status is GroundedAnswerWorkflowStatus.VALIDATION_FAILED
    assert result.failure is not None
    assert result.failure.code == "citation_validation_failed"


def test_unknown_marker_is_safe_validation_error() -> None:
    result = _run(_request(), Generator("Unknown. [S9]"), Evaluator([]))
    assert result.status is GroundedAnswerWorkflowStatus.VALIDATION_FAILED
    assert result.citation_validation is None
    assert result.failure is not None
    assert result.failure.code == "citation_validation_error"


def test_empty_evidence_abstention_uses_no_semantic_call() -> None:
    evaluator = Evaluator([])
    result = _run(
        _request(empty=True),
        Generator("There is not enough information in the supplied evidence."),
        evaluator,
    )
    assert result.status is GroundedAnswerWorkflowStatus.ABSTAINED
    assert result.abstention_detected is True
    assert evaluator.calls == 0


def test_generation_token_overrun_is_incomplete() -> None:
    result = _run(
        _request(tokens=4),
        Generator("First. [S1]", tokens=5),
        Evaluator([]),
    )
    assert result.status is GroundedAnswerWorkflowStatus.INCOMPLETE
    assert result.generation_budget_exhausted is True
    assert result.citation_validation is None


def test_known_generation_failure_preserves_safe_code() -> None:
    result = _run(
        _request(),
        Generator(
            "unused",
            error=GroundedAnswerServiceError(
                code="model_request_failed",
                safe_message="Grounded answer request failed.",
            ),
        ),
        Evaluator([]),
    )
    assert result.status is GroundedAnswerWorkflowStatus.GENERATION_FAILED
    assert result.failure is not None and result.failure.retryable is True


def test_unexpected_generation_failure_does_not_leak_details() -> None:
    result = _run(
        _request(),
        Generator("unused", error=RuntimeError("secret detail")),
        Evaluator([]),
    )
    assert result.failure is not None
    assert result.failure.code == "generation_error"
    assert "secret" not in result.failure.safe_message


def test_citation_budget_exhaustion_is_incomplete() -> None:
    request = _request().model_copy(
        update={
            "citation_validation_budget": AnswerCitationValidationBudget(
                maximum_statements=10,
                maximum_pairs=10,
                maximum_attempts=1,
                maximum_recorded_tokens=100,
                maximum_elapsed_seconds=10.0,
            )
        }
    )
    result = _run(
        request,
        Generator("First. [S1]\nSecond. [S2]"),
        Evaluator([SemanticCitationSupportLevel.FULLY_SUPPORTED] * 2),
    )
    assert result.status is GroundedAnswerWorkflowStatus.INCOMPLETE
    assert result.citation_validation is not None
    assert result.citation_validation.usage.unevaluated_pair_count == 1


def test_wrong_request_type_is_rejected() -> None:
    with pytest.raises(TypeError, match="GroundedAnswerWorkflowRequest"):
        _run("invalid", Generator("unused"), Evaluator([]))  # type: ignore[arg-type]
