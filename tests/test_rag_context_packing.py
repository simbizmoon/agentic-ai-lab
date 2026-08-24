"""Offline tests for bounded RAG context packing contracts."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.schemas.document_chunk import DocumentChunk
from app.schemas.rag_context_packing import (
    OmittedRagContextItem,
    PackedRagContextItem,
    RagContextOmissionReason,
    RagContextPackingBudget,
    RagContextPackingRequest,
    RagContextPackingResult,
    RagContextPackingUsage,
)
from app.schemas.retrieval_result import RetrievalResult


def _retrieval(position: int, text: str = "Evidence") -> RetrievalResult:
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


def _budget(**changes: object) -> RagContextPackingBudget:
    values = {
        "maximum_items": 2,
        "maximum_utf8_bytes": 1000,
        "maximum_estimated_tokens": 100,
        "token_estimator_id": "deterministic-test-estimator-v1",
    }
    values.update(changes)
    return RagContextPackingBudget(**values)  # type: ignore[arg-type]


def _request() -> RagContextPackingRequest:
    return RagContextPackingRequest(
        candidates=[_retrieval(1), _retrieval(2), _retrieval(3)],
        budget=_budget(),
    )


def _result() -> RagContextPackingResult:
    request = _request()
    return RagContextPackingResult(
        request=request,
        included=[
            PackedRagContextItem(
                retrieval=request.candidates[0],
                original_position=1,
                packed_rank=1,
                incremental_utf8_bytes=20,
                incremental_estimated_tokens=5,
            ),
            PackedRagContextItem(
                retrieval=request.candidates[1],
                original_position=2,
                packed_rank=2,
                incremental_utf8_bytes=22,
                incremental_estimated_tokens=6,
            ),
        ],
        omitted=[
            OmittedRagContextItem(
                retrieval=request.candidates[2],
                original_position=3,
                reasons=[RagContextOmissionReason.ITEM_LIMIT],
            )
        ],
        usage=RagContextPackingUsage(
            candidate_count=3,
            included_count=2,
            omitted_count=1,
            context_utf8_bytes=42,
            estimated_tokens=11,
        ),
        was_truncated=True,
    )


def test_budget_is_strict_frozen_and_named() -> None:
    value = _budget()
    assert value.token_estimator_id == "deterministic-test-estimator-v1"
    with pytest.raises(ValidationError):
        RagContextPackingBudget(
            maximum_items=2,
            maximum_utf8_bytes=100,
            maximum_estimated_tokens=20,
            token_estimator_id="x",
            hidden=True,
        )
    with pytest.raises(ValidationError):
        value.maximum_items = 3  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maximum_items", 0),
        ("maximum_items", 101),
        ("maximum_utf8_bytes", 0),
        ("maximum_utf8_bytes", 10_000_001),
        ("maximum_estimated_tokens", 0),
        ("maximum_estimated_tokens", 1_000_001),
        ("token_estimator_id", "   "),
        ("token_estimator_id", " estimator "),
    ],
)
def test_budget_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _budget(**{field: value})


def test_request_accepts_empty_candidates() -> None:
    value = RagContextPackingRequest(candidates=[], budget=_budget())
    assert value.candidates == []


def test_request_rejects_duplicate_chunk_identity() -> None:
    with pytest.raises(ValidationError, match="chunk IDs must be unique"):
        RagContextPackingRequest(
            candidates=[_retrieval(1), _retrieval(1)], budget=_budget()
        )


def test_request_rejects_noncontiguous_candidate_ranks() -> None:
    second = _retrieval(2).model_copy(update={"rank": 3})
    with pytest.raises(ValidationError, match="ranks must be contiguous"):
        RagContextPackingRequest(candidates=[_retrieval(1), second], budget=_budget())


def test_omission_reasons_are_unique_and_canonical() -> None:
    retrieval = _retrieval(1)
    with pytest.raises(ValidationError, match="unique"):
        OmittedRagContextItem(
            retrieval=retrieval,
            original_position=1,
            reasons=[
                RagContextOmissionReason.ITEM_LIMIT,
                RagContextOmissionReason.ITEM_LIMIT,
            ],
        )
    with pytest.raises(ValidationError, match="canonical"):
        OmittedRagContextItem(
            retrieval=retrieval,
            original_position=1,
            reasons=[
                RagContextOmissionReason.ESTIMATED_TOKEN_LIMIT,
                RagContextOmissionReason.UTF8_BYTE_LIMIT,
            ],
        )


def test_valid_result_preserves_complete_classification() -> None:
    value = _result()
    assert value.usage.candidate_count == 3
    assert value.usage.context_utf8_bytes == 42
    assert value.was_truncated is True
    assert [item.original_position for item in value.included] == [1, 2]
    assert [item.original_position for item in value.omitted] == [3]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_candidate",
        "duplicate_position",
        "mutated_candidate",
        "included_order",
        "omitted_order",
        "packed_rank_gap",
        "usage_count",
        "usage_bytes",
        "usage_tokens",
        "truncation_flag",
    ],
)
def test_result_rejects_inconsistent_classification(mutation: str) -> None:
    values = _result().model_dump(mode="python")
    if mutation == "missing_candidate":
        values["omitted"] = []
    elif mutation == "duplicate_position":
        values["omitted"][0]["original_position"] = 2
    elif mutation == "mutated_candidate":
        values["included"][0]["retrieval"]["chunk"]["document_id"] = "drift"
    elif mutation == "included_order":
        values["included"].reverse()
    elif mutation == "omitted_order":
        request = values["request"]
        request["budget"]["maximum_items"] = 1
        values["included"] = values["included"][:1]
        values["omitted"] = [
            {
                "retrieval": request["candidates"][2],
                "original_position": 3,
                "reasons": [RagContextOmissionReason.ITEM_LIMIT],
            },
            {
                "retrieval": request["candidates"][1],
                "original_position": 2,
                "reasons": [RagContextOmissionReason.ITEM_LIMIT],
            },
        ]
        values["usage"] = {
            "candidate_count": 3,
            "included_count": 1,
            "omitted_count": 2,
            "context_utf8_bytes": 20,
            "estimated_tokens": 5,
        }
    elif mutation == "packed_rank_gap":
        values["included"][1]["packed_rank"] = 3
    elif mutation == "usage_count":
        values["usage"]["candidate_count"] = 2
    elif mutation == "usage_bytes":
        values["usage"]["context_utf8_bytes"] = 41
    elif mutation == "usage_tokens":
        values["usage"]["estimated_tokens"] = 10
    else:
        values["was_truncated"] = False
    with pytest.raises(ValidationError):
        RagContextPackingResult.model_validate(values)


def test_empty_result_is_not_truncated() -> None:
    request = RagContextPackingRequest(candidates=[], budget=_budget())
    value = RagContextPackingResult(
        request=request,
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
    assert value.was_truncated is False


def test_result_rejects_budget_overrun() -> None:
    values = deepcopy(_result().model_dump(mode="python"))
    values["request"]["budget"]["maximum_utf8_bytes"] = 41
    with pytest.raises(ValidationError, match="bytes exceed budget"):
        RagContextPackingResult.model_validate(values)


def test_contract_has_no_provider_or_quality_fields() -> None:
    forbidden = {
        "model",
        "winner",
        "source_authority",
        "paper_quality",
        "patent_quality",
        "legal_conclusion",
    }
    assert forbidden.isdisjoint(RagContextPackingResult.model_fields)
