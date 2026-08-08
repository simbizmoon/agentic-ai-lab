from types import SimpleNamespace

import pytest

from app.research.generative_pipeline_claim_builder import (
    GenerativePipelineClaimBuilder,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)


class FakeGenerator:
    def generate(self, evidence: ResearchEvidence):
        return SimpleNamespace(
            proposal=SimpleNamespace(
                text=f"Claim for {evidence.evidence_id}",
                rationale="Generated for incremental test.",
            ),
            response_id=f"response-{evidence.evidence_id}",
            request_id=None,
            usage=None,
            elapsed_seconds=0.0,
        )


def make_evidence(
    evidence_id: str,
) -> ResearchEvidence:
    excerpt = f"Evidence {evidence_id}"

    return ResearchEvidence.model_construct(
        evidence_id=evidence_id,
        request_id="request-1",
        task_id="task-1",
        source_id="source-1",
        document_id="document-1",
        excerpt=excerpt,
        start_character=0,
        end_character=len(excerpt),
        confidence_score=0.8,
        metadata={},
    )


def make_set(
    *items: ResearchEvidence,
) -> ResearchEvidenceSet:
    if len(items) != 1:
        raise ValueError(
            "incremental builder fixture expects exactly one evidence item"
        )

    item = items[0]
    candidate = SimpleNamespace(
        request_id="request-1",
        task_id="task-1",
        source_id="source-1",
    )

    document = ResearchSourceDocument.model_construct(
        document_id="document-1",
        request_id="request-1",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content=item.excerpt,
        metadata={},
    )

    document_set = ResearchSourceDocumentSet.model_construct(
        request_id="request-1",
        documents=[document],
    )

    return ResearchEvidenceSet(
        request_id="request-1",
        document_set=document_set,
        evidence=list(items),
    )


def test_incremental_build_continues_positions() -> None:
    builder = GenerativePipelineClaimBuilder(
        generator=FakeGenerator(),
    )

    result = builder.build_incremental(
        make_set(
            make_evidence("evidence-5"),
        ),
        start_position=5,
    )

    assert result.claims[0].claim_id == (
        "request-1-claim-005"
    )
    assert result.claims[0].citations[0].citation_id == (
        "request-1-citation-005"
    )


def test_incremental_build_rejects_invalid_start_position() -> None:
    builder = GenerativePipelineClaimBuilder(
        generator=FakeGenerator(),
    )

    with pytest.raises(
        ValueError,
        match="start_position must be greater than zero",
    ):
        builder.build_incremental(
            make_set(
                make_evidence("evidence-1"),
            ),
            start_position=0,
        )
