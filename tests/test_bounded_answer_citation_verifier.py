"""Offline tests for bounded answer citation semantic verification."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.exceptions import StructuredResponseParseError
from app.rag.context_builder import build_rag_context
from app.research.bounded_answer_citation_verifier import (
    BoundedAnswerCitationVerifier,
)
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationBatchEvaluationResult,
    SemanticCitationEvaluationResult,
)
from app.research.research_citation_verifier_executor import ResearchCitationDecision
from app.schemas.answer_citation_validation import (
    AnswerCitationValidationBudget,
    AnswerCitationValidationRequest,
    AnswerCitationValidationStatus,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.retrieval_result import RetrievalResult
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)
from app.services.text_generation import TokenUsage


def _retrieval(position: int, text: str) -> RetrievalResult:
    return RetrievalResult(
        chunk=DocumentChunk(
            document_id=f"document-{position}",
            chunk_id=f"chunk-{position}",
            ordinal=position - 1,
            text=text,
            start_char=0,
            end_char=len(text),
            metadata={},
        ),
        score=0.9,
        rank=position,
    )


def _request(answer: str, *, attempts: int = 10) -> AnswerCitationValidationRequest:
    retrievals = [
        _retrieval(1, "A patent apparatus has a frame."),
        _retrieval(2, "The study explains retrieval augmentation."),
    ]
    return AnswerCitationValidationRequest(
        question="What is supported?",
        answer=answer,
        context=build_rag_context(retrievals),
        evidence_retrievals=retrievals,
        citation_required=True,
        budget=AnswerCitationValidationBudget(
            maximum_statements=10,
            maximum_pairs=10,
            maximum_attempts=attempts,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
        ),
    )


def _judgment(level: SemanticCitationSupportLevel) -> SemanticCitationJudgment:
    return SemanticCitationJudgment(
        support_level=level,
        entailment_score=0.9
        if level is SemanticCitationSupportLevel.FULLY_SUPPORTED
        else 0.2,
        rationale=f"Controlled {level.value} judgment.",
        issues=[]
        if level is SemanticCitationSupportLevel.FULLY_SUPPORTED
        else ["fixture"],
    )


def _usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=2,
        cached_input_tokens=0,
        output_tokens=1,
        reasoning_tokens=0,
        total_tokens=3,
    )


def _decision(level: SemanticCitationSupportLevel) -> ResearchCitationDecision:
    return {
        SemanticCitationSupportLevel.FULLY_SUPPORTED: ResearchCitationDecision.VERIFIED,
        SemanticCitationSupportLevel.PARTIALLY_SUPPORTED: (
            ResearchCitationDecision.NEEDS_REVISION
        ),
        SemanticCitationSupportLevel.UNSUPPORTED: ResearchCitationDecision.REJECTED,
        SemanticCitationSupportLevel.CONTRADICTED: ResearchCitationDecision.REJECTED,
    }[level]


@dataclass
class SingleEvaluator:
    levels: list[SemanticCitationSupportLevel]
    calls: list[tuple[str, str]] = field(default_factory=list)

    def evaluate(self, *, claim_text: str, evidence_excerpt: str):
        self.calls.append((claim_text, evidence_excerpt))
        level = self.levels[len(self.calls) - 1]
        return SemanticCitationEvaluationResult(
            judgment=_judgment(level),
            decision=_decision(level),
            response_id=f"response-{len(self.calls)}",
            request_id=f"request-{len(self.calls)}",
            usage=_usage(),
            elapsed_seconds=0.01,
        )


@dataclass
class BatchEvaluator(SingleEvaluator):
    fail_batch: bool = False

    def evaluate_batch(self, *, citation_items):
        if self.fail_batch:
            raise StructuredResponseParseError("controlled batch failure")
        judgments = {
            item_id: _judgment(self.levels[index])
            for index, (item_id, _, _) in enumerate(citation_items)
        }
        return SemanticCitationBatchEvaluationResult(
            judgments=judgments,
            decisions={
                item_id: _decision(self.levels[index])
                for index, item_id in enumerate(judgments)
            },
            response_id="batch-response",
            request_id="batch-request",
            usage=_usage(),
            elapsed_seconds=0.01,
        )


def test_single_verifier_passes_supported_pairs_and_strips_markers() -> None:
    evaluator = SingleEvaluator([SemanticCitationSupportLevel.FULLY_SUPPORTED] * 2)
    result = BoundedAnswerCitationVerifier(evaluator=evaluator).verify(
        request=_request("Patent frame claim. [S1]\nRetrieval claim. [S2]")
    )
    assert result.status is AnswerCitationValidationStatus.PASSED
    assert result.usage.attempts == 2
    assert evaluator.calls[0][0] == "Patent frame claim."
    assert evaluator.calls[0][1] == "A patent apparatus has a frame."


def test_unsupported_pair_fails_answer_validation() -> None:
    evaluator = SingleEvaluator([SemanticCitationSupportLevel.UNSUPPORTED])
    result = BoundedAnswerCitationVerifier(evaluator=evaluator).verify(
        request=_request("Unsupported claim. [S1]")
    )
    assert result.status is AnswerCitationValidationStatus.FAILED


def test_uncited_statement_is_preserved_and_fails() -> None:
    evaluator = SingleEvaluator([SemanticCitationSupportLevel.FULLY_SUPPORTED])
    result = BoundedAnswerCitationVerifier(evaluator=evaluator).verify(
        request=_request("Supported. [S1]\nUncited factual line.")
    )
    assert result.uncited_statement_ids == ["statement-002"]
    assert result.status is AnswerCitationValidationStatus.FAILED


def test_batch_success_uses_one_attempt_for_all_pairs() -> None:
    evaluator = BatchEvaluator([SemanticCitationSupportLevel.FULLY_SUPPORTED] * 2)
    result = BoundedAnswerCitationVerifier(evaluator=evaluator).verify(
        request=_request("One. [S1]\nTwo. [S2]")
    )
    assert result.usage.attempts == 1
    assert result.usage.evaluated_pair_count == 2
    assert evaluator.calls == []


def test_structured_batch_failure_falls_back_and_charges_attempt() -> None:
    evaluator = BatchEvaluator(
        [SemanticCitationSupportLevel.FULLY_SUPPORTED] * 2,
        fail_batch=True,
    )
    result = BoundedAnswerCitationVerifier(evaluator=evaluator).verify(
        request=_request("One. [S1]\nTwo. [S2]")
    )
    assert result.status is AnswerCitationValidationStatus.PASSED
    assert result.usage.attempts == 3
    assert len(evaluator.calls) == 2


def test_budget_exhaustion_preserves_unevaluated_pair() -> None:
    evaluator = SingleEvaluator([SemanticCitationSupportLevel.FULLY_SUPPORTED] * 2)
    result = BoundedAnswerCitationVerifier(evaluator=evaluator).verify(
        request=_request("One. [S1]\nTwo. [S2]", attempts=1)
    )
    assert result.status is AnswerCitationValidationStatus.INCOMPLETE
    assert result.budget_exhausted is True
    assert result.usage.evaluated_pair_count == 1
    assert result.usage.unevaluated_pair_count == 1


def test_multi_citation_statement_preserves_pair_order_and_evidence() -> None:
    evaluator = SingleEvaluator([SemanticCitationSupportLevel.FULLY_SUPPORTED] * 2)
    result = BoundedAnswerCitationVerifier(evaluator=evaluator).verify(
        request=_request("Combined claim. [S2] [S1]")
    )
    assert [item.citation_id for item in result.pairs] == ["S2", "S1"]
    assert [item.evidence.chunk.chunk_id for item in result.pairs] == [
        "chunk-2",
        "chunk-1",
    ]


def test_marker_only_statement_is_rejected_before_evaluator() -> None:
    evaluator = SingleEvaluator([SemanticCitationSupportLevel.FULLY_SUPPORTED])
    with pytest.raises(ValueError, match="claim text"):
        BoundedAnswerCitationVerifier(evaluator=evaluator).verify(
            request=_request("[S1]")
        )
    assert evaluator.calls == []


def test_no_evidence_abstention_needs_no_semantic_attempt() -> None:
    answer = "The supplied evidence is insufficient."
    request = AnswerCitationValidationRequest(
        question="Unknown?",
        answer=answer,
        context=build_rag_context([]),
        evidence_retrievals=[],
        citation_required=False,
        budget=_request("placeholder").budget,
    )
    evaluator = SingleEvaluator([])
    result = BoundedAnswerCitationVerifier(evaluator=evaluator).verify(request=request)
    assert result.status is AnswerCitationValidationStatus.PASSED
    assert result.usage.attempts == 0
    assert result.pairs == []


def test_wrong_request_type_is_rejected() -> None:
    with pytest.raises(TypeError, match="AnswerCitationValidationRequest"):
        BoundedAnswerCitationVerifier(evaluator=SingleEvaluator([])).verify(
            request="invalid"  # type: ignore[arg-type]
        )
