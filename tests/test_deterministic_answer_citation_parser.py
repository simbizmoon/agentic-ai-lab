"""Offline tests for deterministic line-bounded answer citation parsing."""

from __future__ import annotations

import pytest

from app.rag.context_builder import build_rag_context
from app.research.deterministic_answer_citation_parser import (
    AnswerCitationParseError,
    DeterministicAnswerCitationParser,
)
from app.schemas.answer_citation_validation import (
    AnswerCitationValidationBudget,
    AnswerCitationValidationRequest,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.retrieval_result import RetrievalResult


def _retrieval(position: int) -> RetrievalResult:
    text = f"Evidence text {position}."
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


def _request(
    answer: str,
    *,
    evidence_count: int = 2,
    maximum_statements: int = 10,
) -> AnswerCitationValidationRequest:
    retrievals = [_retrieval(index) for index in range(1, evidence_count + 1)]
    return AnswerCitationValidationRequest(
        question="What is supported?",
        answer=answer,
        context=build_rag_context(retrievals),
        evidence_retrievals=retrievals,
        citation_required=bool(retrievals),
        budget=AnswerCitationValidationBudget(
            maximum_statements=maximum_statements,
            maximum_pairs=20,
            maximum_attempts=20,
            maximum_recorded_tokens=1000,
            maximum_elapsed_seconds=10.0,
        ),
    )


def test_parser_preserves_exact_line_offsets_and_marker_order() -> None:
    answer = "  First claim. [S2] [S1]  \n\nSecond claim. [S1]\n"
    statements = DeterministicAnswerCitationParser().parse(request=_request(answer))
    assert [item.statement_id for item in statements] == [
        "statement-001",
        "statement-002",
    ]
    assert statements[0].text == "First claim. [S2] [S1]"
    assert statements[0].cited_ids == ["S2", "S1"]
    assert statements[1].text == "Second claim. [S1]"
    for item in statements:
        assert answer[item.start_character : item.end_character] == item.text


def test_parser_handles_crlf_and_unicode_offsets() -> None:
    answer = "한글 주장. [S1]\r\nEnglish claim. [S2]\r\n"
    statements = DeterministicAnswerCitationParser().parse(request=_request(answer))
    assert statements[0].start_character == 0
    assert statements[1].start_character == answer.index("English")
    assert statements[1].end_character == answer.index(
        "\r\n", statements[1].start_character
    )


def test_parser_does_not_split_sentences_inside_one_line() -> None:
    answer = "First sentence. Second sentence. [S1]"
    statements = DeterministicAnswerCitationParser().parse(request=_request(answer))
    assert len(statements) == 1
    assert statements[0].text == answer


def test_parser_preserves_uncited_nonblank_line() -> None:
    answer = "Supported statement. [S1]\nUncited statement."
    statements = DeterministicAnswerCitationParser().parse(request=_request(answer))
    assert statements[1].cited_ids == []


@pytest.mark.parametrize(
    "answer",
    [
        "Malformed. [S]",
        "Malformed. [SX]",
        "Malformed. [1]",
        "Malformed. [S1",
    ],
)
def test_parser_rejects_malformed_citation_like_marker(answer: str) -> None:
    with pytest.raises(AnswerCitationParseError, match="malformed"):
        DeterministicAnswerCitationParser().parse(request=_request(answer))


def test_parser_rejects_duplicate_marker_in_one_statement() -> None:
    with pytest.raises(AnswerCitationParseError, match="duplicate"):
        DeterministicAnswerCitationParser().parse(request=_request("Claim. [S1] [S1]"))


def test_parser_rejects_unknown_marker_before_semantic_evaluation() -> None:
    with pytest.raises(AnswerCitationParseError, match="unknown"):
        DeterministicAnswerCitationParser().parse(request=_request("Claim. [S9]"))


def test_parser_rejects_statement_budget_overflow() -> None:
    with pytest.raises(AnswerCitationParseError, match="statement count"):
        DeterministicAnswerCitationParser().parse(
            request=_request("One. [S1]\nTwo. [S2]", maximum_statements=1)
        )


def test_no_evidence_abstention_line_is_allowed_without_marker() -> None:
    answer = "The supplied evidence is insufficient."
    statements = DeterministicAnswerCitationParser().parse(
        request=_request(answer, evidence_count=0)
    )
    assert len(statements) == 1
    assert statements[0].cited_ids == []


def test_no_evidence_answer_rejects_any_marker_as_unknown() -> None:
    with pytest.raises(AnswerCitationParseError, match="unknown"):
        DeterministicAnswerCitationParser().parse(
            request=_request("Unsupported marker. [S1]", evidence_count=0)
        )


def test_parser_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError, match="AnswerCitationValidationRequest"):
        DeterministicAnswerCitationParser().parse(request="invalid")  # type: ignore[arg-type]
