"""Tests for generative pipeline claim construction."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.research.generative_pipeline_claim_builder import (
    GenerativePipelineClaimBuilder,
)
from app.research.openai_evidence_claim_generator import (
    GeneratedClaimProposalResult,
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
from app.schemas.research_source_document import (
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)


@dataclass
class FakeGenerator:
    """Return controlled generated claim proposals."""

    calls: list[str]

    def generate(
        self,
        evidence: ResearchEvidence,
    ) -> GeneratedClaimProposalResult:
        self.calls.append(evidence.evidence_id)

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
            usage=None,
            elapsed_seconds=0.01,
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
