"""Offline tests for answer-citation validation contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.rag.context_builder import build_rag_context
from app.schemas.answer_citation_validation import (
    AnswerCitationPairValidation,
    AnswerCitationValidationBudget,
    AnswerCitationValidationRequest,
    AnswerCitationValidationResult,
    AnswerCitationValidationStatus,
    AnswerCitationValidationUsage,
    AnswerStatement,
    CitationPairEvaluationState,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.retrieval_result import RetrievalResult
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)

ANSWER = "The patent has a frame. [S1]\nThe study explains retrieval. [S2]"


def _retrieval(position: int, text: str) -> RetrievalResult:
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


def _request(*, answer: str = ANSWER) -> AnswerCitationValidationRequest:
    retrievals = [
        _retrieval(1, "A patent apparatus has a frame."),
        _retrieval(2, "The study explains retrieval augmentation."),
    ]
    return AnswerCitationValidationRequest(
        question="What do the sources say?",
        answer=answer,
        context=build_rag_context(retrievals),
        evidence_retrievals=retrievals,
        citation_required=True,
        budget=AnswerCitationValidationBudget(
            maximum_statements=10,
            maximum_pairs=10,
            maximum_attempts=10,
            maximum_recorded_tokens=1000,
            maximum_elapsed_seconds=10.0,
        ),
        response_id="response-1",
        model_name="controlled-test-model",
    )


def _statements(*, second_cited: bool = True) -> list[AnswerStatement]:
    first_end = ANSWER.index("\n")
    second_start = first_end + 1
    return [
        AnswerStatement(
            statement_id="statement-001",
            text=ANSWER[:first_end],
            start_character=0,
            end_character=first_end,
            cited_ids=["S1"],
        ),
        AnswerStatement(
            statement_id="statement-002",
            text=ANSWER[second_start:],
            start_character=second_start,
            end_character=len(ANSWER),
            cited_ids=["S2"] if second_cited else [],
        ),
    ]


def _judgment(level: SemanticCitationSupportLevel):
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


def _pair(statement: str, citation: str, evidence: RetrievalResult, level):
    return AnswerCitationPairValidation(
        statement_id=statement,
        citation_id=citation,
        evidence=evidence,
        evaluation_state=CitationPairEvaluationState.EVALUATED,
        judgment=_judgment(level),
        response_id=f"response-{statement}",
        request_id=f"request-{statement}",
    )


def _result(
    *,
    second_level=SemanticCitationSupportLevel.FULLY_SUPPORTED,
) -> AnswerCitationValidationResult:
    request = _request()
    statements = _statements()
    pairs = [
        _pair(
            "statement-001",
            "S1",
            request.evidence_retrievals[0],
            SemanticCitationSupportLevel.FULLY_SUPPORTED,
        ),
        _pair("statement-002", "S2", request.evidence_retrievals[1], second_level),
    ]
    status = (
        AnswerCitationValidationStatus.FAILED
        if second_level
        in {
            SemanticCitationSupportLevel.UNSUPPORTED,
            SemanticCitationSupportLevel.CONTRADICTED,
        }
        else AnswerCitationValidationStatus.PASSED
    )
    return AnswerCitationValidationResult(
        request=request,
        statements=statements,
        pairs=pairs,
        uncited_statement_ids=[],
        usage=AnswerCitationValidationUsage(
            attempts=2,
            recorded_tokens=20,
            elapsed_seconds=0.2,
            statement_count=2,
            pair_count=2,
            evaluated_pair_count=2,
            unevaluated_pair_count=0,
        ),
        budget_exhausted=False,
        status=status,
    )


def test_valid_fully_supported_result_passes() -> None:
    value = _result()
    assert value.status is AnswerCitationValidationStatus.PASSED
    assert value.usage.pair_count == 2


@pytest.mark.parametrize(
    "level",
    [
        SemanticCitationSupportLevel.UNSUPPORTED,
        SemanticCitationSupportLevel.CONTRADICTED,
    ],
)
def test_unsupported_or_contradicted_pair_fails(level) -> None:
    assert _result(second_level=level).status is AnswerCitationValidationStatus.FAILED


def test_partial_support_is_not_automatically_rejected() -> None:
    value = _result(second_level=SemanticCitationSupportLevel.PARTIALLY_SUPPORTED)
    assert value.status is AnswerCitationValidationStatus.PASSED


def test_request_rejects_context_evidence_drift() -> None:
    values = _request().model_dump(mode="python")
    values["evidence_retrievals"][0]["chunk"]["document_id"] = "drift"
    with pytest.raises(ValidationError, match="exact context citation"):
        AnswerCitationValidationRequest.model_validate(values)


def test_result_rejects_statement_text_or_range_drift() -> None:
    values = _result().model_dump(mode="python")
    values["statements"][0]["text"] = "Changed"
    with pytest.raises(ValidationError, match="exact answer range"):
        AnswerCitationValidationResult.model_validate(values)


def test_result_rejects_unknown_marker() -> None:
    values = _result().model_dump(mode="python")
    values["statements"][0]["cited_ids"] = ["S9"]
    values["pairs"][0]["citation_id"] = "S9"
    with pytest.raises(ValidationError, match="unknown citation"):
        AnswerCitationValidationResult.model_validate(values)


def test_result_rejects_missing_duplicate_or_reordered_pairs() -> None:
    base = _result().model_dump(mode="python")
    for pairs in (
        base["pairs"][:1],
        [*base["pairs"], base["pairs"][0]],
        list(reversed(base["pairs"])),
    ):
        values = _result().model_dump(mode="python")
        values["pairs"] = pairs
        with pytest.raises(ValidationError, match="exactly cover"):
            AnswerCitationValidationResult.model_validate(values)


def test_uncited_statement_requires_failed_status() -> None:
    request = _request()
    statements = _statements(second_cited=False)
    values = _result().model_dump(mode="python")
    values["statements"] = [item.model_dump(mode="python") for item in statements]
    values["pairs"] = values["pairs"][:1]
    values["uncited_statement_ids"] = ["statement-002"]
    values["usage"].update(pair_count=1, evaluated_pair_count=1)
    values["status"] = AnswerCitationValidationStatus.FAILED
    value = AnswerCitationValidationResult.model_validate(values)
    assert value.request == request
    assert value.status is AnswerCitationValidationStatus.FAILED


def test_unevaluated_pair_requires_exhaustion_and_incomplete_status() -> None:
    values = _result().model_dump(mode="python")
    values["pairs"][1].update(
        evaluation_state=CitationPairEvaluationState.UNEVALUATED,
        judgment=None,
        response_id=None,
        request_id=None,
    )
    values["usage"].update(evaluated_pair_count=1, unevaluated_pair_count=1)
    values["budget_exhausted"] = True
    values["status"] = AnswerCitationValidationStatus.INCOMPLETE
    value = AnswerCitationValidationResult.model_validate(values)
    assert value.status is AnswerCitationValidationStatus.INCOMPLETE


def test_no_evidence_answer_can_pass_without_citations() -> None:
    answer = "The supplied evidence is insufficient."
    request = AnswerCitationValidationRequest(
        question="Unknown?",
        answer=answer,
        context=build_rag_context([]),
        evidence_retrievals=[],
        citation_required=False,
        budget=_request().budget,
    )
    statement = AnswerStatement(
        statement_id="statement-001",
        text=answer,
        start_character=0,
        end_character=len(answer),
        cited_ids=[],
    )
    value = AnswerCitationValidationResult(
        request=request,
        statements=[statement],
        pairs=[],
        uncited_statement_ids=[],
        usage=AnswerCitationValidationUsage(
            attempts=0,
            recorded_tokens=0,
            elapsed_seconds=0.0,
            statement_count=1,
            pair_count=0,
            evaluated_pair_count=0,
            unevaluated_pair_count=0,
        ),
        budget_exhausted=False,
        status=AnswerCitationValidationStatus.PASSED,
    )
    assert value.status is AnswerCitationValidationStatus.PASSED


def test_contract_has_no_quality_authority_or_legal_fields() -> None:
    forbidden = {
        "winner",
        "source_authority",
        "paper_quality",
        "patent_quality",
        "legal_conclusion",
    }
    assert forbidden.isdisjoint(AnswerCitationValidationResult.model_fields)
