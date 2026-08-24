"""Offline tests for deterministic whole-chunk RAG context packing."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.rag.context_builder import build_rag_context
from app.research.deterministic_rag_context_packer import (
    ConservativeUtf8TokenEstimator,
    DeterministicRagContextPacker,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.rag_context_packing import (
    RagContextOmissionReason,
    RagContextPackingBudget,
    RagContextPackingRequest,
)
from app.schemas.retrieval_result import RetrievalResult


@dataclass(frozen=True)
class WordEstimator:
    estimator_id: str = "deterministic-word-estimate-test-v1"

    def estimate_tokens(self, text: str) -> int:
        return len(text.split())


@dataclass(frozen=True)
class InvalidEstimator:
    estimator_id: str
    value: object

    def estimate_tokens(self, text: str):
        del text
        return self.value


def _retrieval(position: int, text: str) -> RetrievalResult:
    return RetrievalResult(
        chunk=DocumentChunk(
            document_id=f"document-{position}",
            chunk_id=f"chunk-{position}",
            ordinal=position - 1,
            text=text,
            start_char=10 * position,
            end_char=10 * position + len(text),
            metadata={"source": f"source-{position}.txt"},
        ),
        score=round(1.0 - position / 10, 2),
        rank=position,
    )


def _candidates() -> list[RetrievalResult]:
    return [
        _retrieval(1, "Patent frame evidence."),
        _retrieval(2, "Academic retrieval evidence with several useful words."),
        _retrieval(3, "Official guidance."),
    ]


def _request(
    *,
    maximum_items: int = 3,
    maximum_utf8_bytes: int = 10_000,
    maximum_estimated_tokens: int = 10_000,
    estimator_id: str = "deterministic-word-estimate-test-v1",
) -> RagContextPackingRequest:
    return RagContextPackingRequest(
        candidates=_candidates(),
        budget=RagContextPackingBudget(
            maximum_items=maximum_items,
            maximum_utf8_bytes=maximum_utf8_bytes,
            maximum_estimated_tokens=maximum_estimated_tokens,
            token_estimator_id=estimator_id,
        ),
    )


def test_packer_includes_all_chunks_and_accounts_rendered_context() -> None:
    estimator = WordEstimator()
    result = DeterministicRagContextPacker(token_estimator=estimator).pack(
        request=_request()
    )
    rendered = build_rag_context(
        [
            item.retrieval.model_copy(update={"rank": item.packed_rank})
            for item in result.included
        ]
    ).context_text
    assert [item.original_position for item in result.included] == [1, 2, 3]
    assert result.omitted == []
    assert result.was_truncated is False
    assert result.usage.context_utf8_bytes == len(rendered.encode("utf-8"))
    assert result.usage.estimated_tokens == estimator.estimate_tokens(rendered)
    assert sum(item.incremental_utf8_bytes for item in result.included) == len(
        rendered.encode("utf-8")
    )


def test_item_limit_omits_later_chunks_without_cutting_text() -> None:
    result = DeterministicRagContextPacker(token_estimator=WordEstimator()).pack(
        request=_request(maximum_items=1)
    )
    assert [item.retrieval.chunk.text for item in result.included] == [
        "Patent frame evidence."
    ]
    assert [item.original_position for item in result.omitted] == [2, 3]
    assert all(
        item.reasons == [RagContextOmissionReason.ITEM_LIMIT] for item in result.omitted
    )
    assert result.included[0].retrieval.chunk.text == _candidates()[0].chunk.text


def test_byte_limit_measures_rendered_headers_and_utf8() -> None:
    first = build_rag_context([_candidates()[0]]).context_text
    first_bytes = len(first.encode("utf-8"))
    result = DeterministicRagContextPacker(token_estimator=WordEstimator()).pack(
        request=_request(maximum_utf8_bytes=first_bytes)
    )
    assert [item.original_position for item in result.included] == [1]
    assert RagContextOmissionReason.UTF8_BYTE_LIMIT in result.omitted[0].reasons
    assert result.usage.context_utf8_bytes == first_bytes


def test_token_limit_uses_named_estimator_and_can_differ_from_bytes() -> None:
    estimator = WordEstimator()
    first = build_rag_context([_candidates()[0]]).context_text
    first_tokens = estimator.estimate_tokens(first)
    result = DeterministicRagContextPacker(token_estimator=estimator).pack(
        request=_request(maximum_estimated_tokens=first_tokens)
    )
    assert [item.original_position for item in result.included] == [1]
    assert RagContextOmissionReason.ESTIMATED_TOKEN_LIMIT in result.omitted[0].reasons
    assert result.usage.estimated_tokens == first_tokens


def test_later_small_chunk_can_fit_after_large_chunk_is_omitted() -> None:
    candidates = _candidates()
    first_and_third = build_rag_context([candidates[0], candidates[2]]).context_text
    limit = len(first_and_third.encode("utf-8"))
    request = _request(maximum_utf8_bytes=limit)
    result = DeterministicRagContextPacker(token_estimator=WordEstimator()).pack(
        request=request
    )
    assert [item.original_position for item in result.included] == [1, 3]
    assert [item.original_position for item in result.omitted] == [2]
    assert result.included[1].packed_rank == 2


def test_all_applicable_omission_reasons_use_canonical_order() -> None:
    result = DeterministicRagContextPacker(token_estimator=WordEstimator()).pack(
        request=_request(
            maximum_items=1,
            maximum_utf8_bytes=1,
            maximum_estimated_tokens=1,
        )
    )
    assert result.included == []
    assert result.omitted[1].reasons == [
        RagContextOmissionReason.UTF8_BYTE_LIMIT,
        RagContextOmissionReason.ESTIMATED_TOKEN_LIMIT,
    ]


def test_empty_candidates_return_zero_usage() -> None:
    request = RagContextPackingRequest(
        candidates=[],
        budget=_request().budget,
    )
    result = DeterministicRagContextPacker(token_estimator=WordEstimator()).pack(
        request=request
    )
    assert result.included == []
    assert result.omitted == []
    assert result.usage.context_utf8_bytes == 0
    assert result.usage.estimated_tokens == 0
    assert result.was_truncated is False


def test_estimator_identity_must_match_budget() -> None:
    with pytest.raises(ValueError, match="estimator_id must match"):
        DeterministicRagContextPacker(token_estimator=WordEstimator()).pack(
            request=_request(estimator_id="different-estimator")
        )


@pytest.mark.parametrize("estimator_id", ["", "   ", " padded "])
def test_constructor_rejects_invalid_estimator_identity(estimator_id: str) -> None:
    with pytest.raises(ValueError, match="estimator"):
        DeterministicRagContextPacker(
            token_estimator=InvalidEstimator(estimator_id=estimator_id, value=0)
        )


@pytest.mark.parametrize("value", [-1, 1.5, True, "2", None])
def test_packer_rejects_invalid_estimator_output(value: object) -> None:
    estimator = InvalidEstimator(estimator_id="invalid-output-test", value=value)
    with pytest.raises(ValueError, match="nonnegative integer"):
        DeterministicRagContextPacker(token_estimator=estimator).pack(
            request=_request(estimator_id=estimator.estimator_id)
        )


def test_conservative_estimator_is_explicit_and_deterministic() -> None:
    estimator = ConservativeUtf8TokenEstimator()
    assert estimator.estimator_id == "conservative-utf8-byte-token-estimate-v1"
    assert estimator.estimate_tokens("A한") == len("A한".encode())
    with pytest.raises(TypeError):
        estimator.estimate_tokens(1)  # type: ignore[arg-type]


def test_packer_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError, match="RagContextPackingRequest"):
        DeterministicRagContextPacker(token_estimator=WordEstimator()).pack(
            request="invalid"  # type: ignore[arg-type]
        )
