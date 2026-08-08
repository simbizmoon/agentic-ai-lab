"""Tests for generative pipeline claim construction."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.budget import ExecutionBudget
from app.research.generative_pipeline_claim_builder import (
    GenerativePipelineClaimBuilder,
)
from app.research.openai_evidence_claim_generator import (
    ClaimGenerationProviderError,
    GeneratedClaimProposalBatchResult,
    GeneratedClaimProposalResult,
    StructuredClaimGenerationError,
)
from app.schemas.generated_claim_proposal import (
    GeneratedClaimProposal,
)
from app.schemas.research_claim import (
    ResearchClaimStatus,
    ResearchClaimType,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)


@dataclass
class FakeGenerator:
    """Return controlled generated claim proposals."""

    calls: list[str]
    total_tokens: int = 0
    elapsed_seconds: float = 0.01

    def generate(
        self,
        evidence: ResearchEvidence,
    ) -> GeneratedClaimProposalResult:
        self.calls.append(evidence.evidence_id)

        usage = None
        if self.total_tokens:
            usage = SimpleNamespace(total_tokens=self.total_tokens)

        return GeneratedClaimProposalResult(
            proposal=GeneratedClaimProposal(
                text=(
                    "The SDK can expose Python functions "
                    "as callable tools."
                ),
                rationale=(
                    "The generated wording preserves the "
                    "evidence meaning without adding scope."
                ),
            ),
            response_id="resp-claim-001",
            request_id="req-provider-001",
            usage=usage,
            elapsed_seconds=self.elapsed_seconds,
        )


def evidence() -> ResearchEvidence:
    return ResearchEvidence(
        evidence_id="evidence-001",
        request_id="request-001",
        task_id="task-001",
        source_id="source-001",
        document_id="document-001",
        excerpt=(
            "The SDK can turn Python functions into tools "
            "by inspecting signatures and docstrings."
        ),
        start_character=10,
        end_character=95,
        evidence_type=ResearchEvidenceType.METHOD,
        stance=ResearchEvidenceStance.SUPPORTS,
        relevance_score=0.95,
        confidence_score=0.91,
        rationale="The excerpt describes function tool construction.",
    )


def evidence_set(
    *,
    items: list[ResearchEvidence] | None = None,
) -> ResearchEvidenceSet:
    """Build the minimum validated input object needed by the builder test."""

    source_evidence = (
        [evidence()]
        if items is None
        else items
    )

    excerpt = (
        source_evidence[0].excerpt
        if source_evidence
        else (
            "The SDK can turn Python functions into tools "
            "by inspecting signatures and docstrings."
        )
    )
    content = "0123456789" + excerpt + " trailing text"

    document_set = ResearchSourceDocumentSet.model_construct(
        request_id="request-001",
        candidate_set=None,
        documents=[
            SimpleNamespace(
                document_id="document-001",
                status=ResearchSourceDocumentStatus.READ,
                candidate=SimpleNamespace(
                    task_id="task-001",
                    source_id="source-001",
                ),
                content=content,
                sections=[],
            )
        ],
    )

    return ResearchEvidenceSet.model_construct(
        request_id="request-001",
        document_set=document_set,
        evidence=source_evidence,
    )


def evidence_set_with_count(count: int) -> ResearchEvidenceSet:
    """Build a validated evidence set with distinct document ranges."""

    excerpts = [
        f"Evidence statement number {position} supports a bounded claim."
        for position in range(1, count + 1)
    ]
    separator = "\n"
    content = separator.join(excerpts)

    candidate = ResearchSourceCandidate(
        source_id="source-001",
        request_id="request-001",
        task_id="task-001",
        query_id="query-001",
        title="Example documentation",
        url="https://example.com/docs",
        source_type=ResearchSourceType.OFFICIAL_DOCUMENTATION,
        snippet="Example documentation snippet.",
        rank=1,
        metadata={},
    )

    document = ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        sections=[],
        word_count=len(content.split()),
        character_count=len(content),
        reader="test-reader",
        metadata={},
    )
    document_set = ResearchSourceDocumentSet(
        request_id="request-001",
        documents=[document],
    )

    base_evidence = evidence()
    items: list[ResearchEvidence] = []
    cursor = 0

    for position, excerpt in enumerate(excerpts, start=1):
        start_character = cursor
        end_character = start_character + len(excerpt)
        items.append(
            base_evidence.model_copy(
                update={
                    "evidence_id": f"evidence-{position:03d}",
                    "excerpt": excerpt,
                    "start_character": start_character,
                    "end_character": end_character,
                    "rationale": "Controlled budget test evidence.",
                }
            )
        )
        cursor = end_character + len(separator)

    return ResearchEvidenceSet(
        request_id="request-001",
        document_set=document_set,
        evidence=items,
    )

def test_builder_creates_generated_draft_claim() -> None:
    generator = FakeGenerator(calls=[])
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
    )

    result = builder.build(evidence_set())

    assert generator.calls == ["evidence-001"]
    assert len(result.claims) == 1

    claim = result.claims[0]

    assert (
        claim.text
        == "The SDK can expose Python functions as callable tools."
    )
    assert (
        claim.text
        != result.evidence_set.evidence[0].excerpt
    )
    assert claim.claim_type is ResearchClaimType.FACTUAL
    assert claim.status is ResearchClaimStatus.DRAFT
    assert claim.confidence_score == 0.91
    assert claim.supporting_evidence_ids == []
    assert claim.contradicting_evidence_ids == []


def test_builder_preserves_evidence_identity_and_citation() -> None:
    builder = GenerativePipelineClaimBuilder(
        generator=FakeGenerator(calls=[]),
    )

    result = builder.build(evidence_set())
    source_evidence = result.evidence_set.evidence[0]
    claim = result.claims[0]
    citation = claim.citations[0]

    assert claim.claim_id == "request-001-claim-001"
    assert claim.request_id == source_evidence.request_id
    assert claim.task_id == source_evidence.task_id

    assert citation.citation_id == "request-001-citation-001"
    assert citation.evidence_id == source_evidence.evidence_id
    assert citation.source_id == source_evidence.source_id
    assert citation.document_id == source_evidence.document_id
    assert citation.excerpt == source_evidence.excerpt
    assert (
        citation.start_character
        == source_evidence.start_character
    )
    assert (
        citation.end_character
        == source_evidence.end_character
    )


def test_builder_records_generator_metadata() -> None:
    builder = GenerativePipelineClaimBuilder(
        generator=FakeGenerator(calls=[]),
    )

    claim = builder.build(evidence_set()).claims[0]

    assert claim.metadata == {
        "builder": "generative-pipeline",
        "generator_response_id": "resp-claim-001",
        "generator_request_id": "req-provider-001",
    }
    assert claim.citations[0].metadata == {
        "builder": "generative-pipeline",
    }


def test_builder_returns_empty_claim_set_for_no_evidence() -> None:
    generator = FakeGenerator(calls=[])
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
    )

    result = builder.build(
        evidence_set(items=[]),
    )

    assert result.claims == []
    assert generator.calls == []

def test_builder_without_budget_processes_all_evidence() -> None:
    generator = FakeGenerator(calls=[])
    builder = GenerativePipelineClaimBuilder(generator=generator)

    result = builder.build(evidence_set_with_count(3))

    assert len(result.claims) == 3
    assert generator.calls == ["evidence-001", "evidence-002", "evidence-003"]
    assert builder.last_usage.attempts == 0


def test_builder_stops_before_attempt_limit() -> None:
    generator = FakeGenerator(calls=[])
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
        budget=ExecutionBudget(
            max_attempts=2,
            max_recorded_tokens=10_000,
            max_elapsed_seconds=60.0,
        ),
    )

    result = builder.build(evidence_set_with_count(3))

    assert len(result.claims) == 2
    assert generator.calls == ["evidence-001", "evidence-002"]
    assert builder.last_usage.attempts == 2


def test_builder_keeps_claim_that_crosses_token_budget() -> None:
    generator = FakeGenerator(calls=[], total_tokens=600)
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
        budget=ExecutionBudget(
            max_attempts=5,
            max_recorded_tokens=1_000,
            max_elapsed_seconds=60.0,
        ),
    )

    result = builder.build(evidence_set_with_count(3))

    assert len(result.claims) == 2
    assert generator.calls == ["evidence-001", "evidence-002"]
    assert builder.last_usage.attempts == 2
    assert builder.last_usage.recorded_tokens == 1_200


def test_builder_keeps_claim_that_crosses_time_budget() -> None:
    generator = FakeGenerator(calls=[], elapsed_seconds=0.6)
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
        budget=ExecutionBudget(
            max_attempts=5,
            max_recorded_tokens=10_000,
            max_elapsed_seconds=1.0,
        ),
    )

    result = builder.build(evidence_set_with_count(3))

    assert len(result.claims) == 2
    assert generator.calls == ["evidence-001", "evidence-002"]
    assert builder.last_usage.attempts == 2
    assert builder.last_usage.elapsed_seconds == 1.2


def test_builder_treats_missing_usage_as_zero_tokens() -> None:
    generator = FakeGenerator(calls=[])
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
        budget=ExecutionBudget(
            max_attempts=2,
            max_recorded_tokens=1,
            max_elapsed_seconds=60.0,
        ),
    )

    result = builder.build(evidence_set_with_count(2))

    assert len(result.claims) == 2
    assert builder.last_usage.attempts == 2
    assert builder.last_usage.recorded_tokens == 0


@dataclass
class BatchFakeGenerator(FakeGenerator):
    batch_error: Exception | None = None

    def __post_init__(self) -> None:
        self.batch_calls: list[list[str]] = []
        self.single_calls = 0

    def generate_batch(self, evidence_items: list[tuple[str, ResearchEvidence]]) -> GeneratedClaimProposalBatchResult:
        self.batch_calls.append([e.evidence_id for _item_id, e in evidence_items])
        if self.batch_error is not None:
            raise self.batch_error
        return GeneratedClaimProposalBatchResult(
            proposals={
                item_id: GeneratedClaimProposal(
                    text=f"Claim for {e.evidence_id}",
                    rationale="Batch-bounded claim.",
                )
                for item_id, e in evidence_items
            },
            response_id="resp-batch-001",
            request_id="req-batch-001",
            usage=(SimpleNamespace(total_tokens=self.total_tokens) if self.total_tokens else None),
            elapsed_seconds=self.elapsed_seconds,
        )

    def generate(self, evidence: ResearchEvidence) -> GeneratedClaimProposalResult:
        self.single_calls += 1
        return super().generate(evidence)


def test_builder_batches_three_evidence_into_one_physical_call() -> None:
    generator = BatchFakeGenerator(calls=[])
    generator.__post_init__()
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
        budget=ExecutionBudget(max_attempts=8, max_recorded_tokens=8_000, max_elapsed_seconds=60.0),
    )
    result = builder.build(evidence_set_with_count(3))
    assert len(result.claims) == 3
    assert len(generator.batch_calls) == 1
    assert generator.single_calls == 0
    assert builder.last_usage.attempts == 3
    assert builder.last_api_usage.attempts == 1
    assert [c.citations[0].evidence_id for c in result.claims] == ["evidence-001", "evidence-002", "evidence-003"]


def test_batch_preserves_max_attempts_as_item_cap() -> None:
    generator = BatchFakeGenerator(calls=[])
    generator.__post_init__()
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
        budget=ExecutionBudget(max_attempts=2, max_recorded_tokens=8_000, max_elapsed_seconds=60.0),
    )
    result = builder.build(evidence_set_with_count(3))
    assert len(result.claims) == 2
    assert generator.batch_calls == [["evidence-001", "evidence-002"]]
    assert builder.last_usage.attempts == 2
    assert builder.last_api_usage.attempts == 1


def test_batch_structured_failure_falls_back_to_singles() -> None:
    generator = BatchFakeGenerator(calls=[], batch_error=StructuredClaimGenerationError("bad batch"))
    generator.__post_init__()
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
        budget=ExecutionBudget(max_attempts=3, max_recorded_tokens=8_000, max_elapsed_seconds=60.0),
    )
    result = builder.build(evidence_set_with_count(3))
    assert len(result.claims) == 3
    assert len(generator.batch_calls) == 1
    assert generator.single_calls == 3
    assert builder.last_api_usage.attempts == 4


def test_batch_provider_error_does_not_fallback() -> None:
    generator = BatchFakeGenerator(calls=[], batch_error=ClaimGenerationProviderError("provider unavailable"))
    generator.__post_init__()
    builder = GenerativePipelineClaimBuilder(generator=generator)
    with pytest.raises(ClaimGenerationProviderError, match="provider unavailable"):
        builder.build(evidence_set_with_count(2))
    assert generator.single_calls == 0


def test_batch_shared_usage_is_recorded_once_physically() -> None:
    generator = BatchFakeGenerator(calls=[], total_tokens=1_200, elapsed_seconds=1.2)
    generator.__post_init__()
    builder = GenerativePipelineClaimBuilder(
        generator=generator,
        budget=ExecutionBudget(max_attempts=5, max_recorded_tokens=1_000, max_elapsed_seconds=1.0),
    )
    result = builder.build(evidence_set_with_count(3))
    assert len(result.claims) == 3
    assert builder.last_usage.attempts == 3
    assert builder.last_usage.recorded_tokens == 1_200
    assert builder.last_usage.elapsed_seconds == 1.2
    assert builder.last_api_usage.attempts == 1
