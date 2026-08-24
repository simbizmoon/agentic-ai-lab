"""Deterministically pack whole retrieval chunks into bounded RAG context."""

from __future__ import annotations

from typing import Protocol

from app.rag.context_builder import build_rag_context
from app.schemas.rag_context_packing import (
    OmittedRagContextItem,
    PackedRagContextItem,
    RagContextOmissionReason,
    RagContextPackingRequest,
    RagContextPackingResult,
    RagContextPackingUsage,
)
from app.schemas.retrieval_result import RetrievalResult


class RagContextTokenEstimator(Protocol):
    """Named deterministic estimator for preflight rendered-context tokens."""

    @property
    def estimator_id(self) -> str: ...

    def estimate_tokens(self, text: str) -> int: ...


class ConservativeUtf8TokenEstimator:
    """Use UTF-8 bytes as a conservative, explicitly non-provider estimate."""

    @property
    def estimator_id(self) -> str:
        return "conservative-utf8-byte-token-estimate-v1"

    def estimate_tokens(self, text: str) -> int:
        if not isinstance(text, str):
            raise TypeError("token estimator text must be a string")
        return len(text.encode("utf-8"))


class DeterministicRagContextPacker:
    """Greedily pack complete chunks in reranked order under all ceilings."""

    def __init__(self, *, token_estimator: RagContextTokenEstimator) -> None:
        estimator_id = token_estimator.estimator_id
        if not isinstance(estimator_id, str) or not estimator_id.strip():
            raise ValueError("token estimator must expose a nonblank estimator_id")
        if estimator_id != estimator_id.strip():
            raise ValueError("token estimator_id must not have surrounding whitespace")
        self._token_estimator = token_estimator

    @property
    def token_estimator(self) -> RagContextTokenEstimator:
        return self._token_estimator

    def pack(self, *, request: RagContextPackingRequest) -> RagContextPackingResult:
        """Classify every candidate as included or explicitly omitted."""

        if not isinstance(request, RagContextPackingRequest):
            raise TypeError("request must be a RagContextPackingRequest")
        if self._token_estimator.estimator_id != request.budget.token_estimator_id:
            raise ValueError("token estimator_id must match the packing budget")

        included: list[PackedRagContextItem] = []
        omitted: list[OmittedRagContextItem] = []
        packed_retrievals: list[RetrievalResult] = []
        current_bytes = 0
        current_tokens = 0

        for position, candidate in enumerate(request.candidates, start=1):
            packed_rank = len(included) + 1
            prospective_retrieval = candidate.model_copy(update={"rank": packed_rank})
            prospective = [*packed_retrievals, prospective_retrieval]
            rendered = build_rag_context(prospective).context_text
            prospective_bytes = len(rendered.encode("utf-8"))
            prospective_tokens = self._estimate(rendered)

            reasons: list[RagContextOmissionReason] = []
            budget = request.budget
            if packed_rank > budget.maximum_items:
                reasons.append(RagContextOmissionReason.ITEM_LIMIT)
            if prospective_bytes > budget.maximum_utf8_bytes:
                reasons.append(RagContextOmissionReason.UTF8_BYTE_LIMIT)
            if prospective_tokens > budget.maximum_estimated_tokens:
                reasons.append(RagContextOmissionReason.ESTIMATED_TOKEN_LIMIT)

            if reasons:
                omitted.append(
                    OmittedRagContextItem(
                        retrieval=candidate,
                        original_position=position,
                        reasons=reasons,
                    )
                )
                continue

            included.append(
                PackedRagContextItem(
                    retrieval=candidate,
                    original_position=position,
                    packed_rank=packed_rank,
                    incremental_utf8_bytes=prospective_bytes - current_bytes,
                    incremental_estimated_tokens=prospective_tokens - current_tokens,
                )
            )
            packed_retrievals.append(prospective_retrieval)
            current_bytes = prospective_bytes
            current_tokens = prospective_tokens

        return RagContextPackingResult(
            request=request,
            included=included,
            omitted=omitted,
            usage=RagContextPackingUsage(
                candidate_count=len(request.candidates),
                included_count=len(included),
                omitted_count=len(omitted),
                context_utf8_bytes=current_bytes,
                estimated_tokens=current_tokens,
            ),
            was_truncated=bool(omitted),
        )

    def _estimate(self, text: str) -> int:
        value = self._token_estimator.estimate_tokens(text)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("token estimator must return a nonnegative integer")
        return value
