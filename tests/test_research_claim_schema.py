"""Tests for research claims and citations."""

import pytest
from pydantic import ValidationError

from app.schemas.research_claim import (
    ResearchCitation,
    ResearchClaim,
    ResearchClaimSet,
    ResearchClaimStatus,
    ResearchClaimType,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_request import (
    ResearchSourceType,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)

CONTENT = "Agent memory stores contextual information."


def candidate(
    *,
    source_id: str,
    task_id: str,
) -> ResearchSourceCandidate:
    """Return one source candidate."""

    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="research-001",
        task_id=task_id,
        query_id=f"query-{task_id}",
        title=f"Source for {task_id}",
        url=f"https://example.com/{source_id}",
        source_type=ResearchSourceType.ACADEMIC,
        rank=1,
    )


def document(
    *,
    document_id: str,
    source_id: str,
    task_id: str,
) -> ResearchSourceDocument:
    """Return one source document."""

    return ResearchSourceDocument(
        document_id=document_id,
        candidate=candidate(
            source_id=source_id,
            task_id=task_id,
        ),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        sections=[],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="test-reader",
    )


def evidence(
    *,
    evidence_id: str = "evidence-001",
    task_id: str = "task-001",
    source_id: str = "source-001",
    document_id: str = "document-001",
    stance: ResearchEvidenceStance = (
        ResearchEvidenceStance.SUPPORTS
    ),
) -> ResearchEvidence:
    """Return one evidence item."""

    return ResearchEvidence(
        evidence_id=evidence_id,
        request_id="research-001",
        task_id=task_id,
        source_id=source_id,
        document_id=document_id,
        excerpt=CONTENT,
        start_character=0,
        end_character=len(CONTENT),
        evidence_type=ResearchEvidenceType.FACT,
        stance=stance,
        relevance_score=0.9,
        confidence_score=0.8,
    )


def evidence_set() -> ResearchEvidenceSet:
    """Return an evidence set with support and contradiction."""

    documents = ResearchSourceDocumentSet(
        request_id="research-001",
        documents=[
            document(
                document_id="document-001",
                source_id="source-001",
                task_id="task-001",
            ),
            document(
                document_id="document-002",
                source_id="source-002",
                task_id="task-001",
            ),
        ],
    )

    return ResearchEvidenceSet(
        request_id="research-001",
        document_set=documents,
        evidence=[
            evidence(),
            evidence(
                evidence_id="evidence-002",
                source_id="source-002",
                document_id="document-002",
                stance=(
                    ResearchEvidenceStance.CONTRADICTS
                ),
            ),
        ],
    )


def citation(
    *,
    citation_id: str = "citation-001",
    evidence_id: str = "evidence-001",
    source_id: str = "source-001",
    document_id: str = "document-001",
    **overrides: object,
) -> ResearchCitation:
    """Return one valid citation."""

    values: dict[str, object] = {
        "citation_id": citation_id,
        "evidence_id": evidence_id,
        "source_id": source_id,
        "document_id": document_id,
        "excerpt": CONTENT,
        "start_character": 0,
        "end_character": len(CONTENT),
        "label": "[1]",
        "metadata": {
            "style": "numeric",
        },
    }
    values.update(overrides)

    return ResearchCitation.model_validate(values)


def claim(
    **overrides: object,
) -> ResearchClaim:
    """Return one supported research claim."""

    values: dict[str, object] = {
        "claim_id": "claim-001",
        "request_id": "research-001",
        "task_id": "task-001",
        "text": (
            "Agent memory stores contextual information."
        ),
        "claim_type": ResearchClaimType.FACTUAL,
        "status": ResearchClaimStatus.SUPPORTED,
        "confidence_score": 0.85,
        "citations": [citation()],
        "supporting_evidence_ids": [
            "evidence-001"
        ],
        "contradicting_evidence_ids": [],
        "rationale": (
            "The cited evidence directly supports "
            "the claim."
        ),
        "metadata": {
            "generator": "test",
        },
    }
    values.update(overrides)

    return ResearchClaim.model_validate(values)


def test_citation_accepts_valid_values() -> None:
    value = citation()

    assert value.citation_id == "citation-001"
    assert value.evidence_id == "evidence-001"


def test_citation_rejects_invalid_range() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "end_character must be greater than "
            "start_character"
        ),
    ):
        citation(
            start_character=5,
            end_character=5,
        )


def test_claim_accepts_supported_claim() -> None:
    value = claim()

    assert value.status is ResearchClaimStatus.SUPPORTED
    assert len(value.citations) == 1


def test_claim_requires_citation() -> None:
    with pytest.raises(ValidationError):
        claim(citations=[])


def test_claim_rejects_duplicate_citation_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "citation IDs must be unique within a claim"
        ),
    ):
        claim(
            citations=[
                citation(citation_id="citation-001"),
                citation(
                    citation_id=" CITATION-001 ",
                    evidence_id="evidence-002",
                    source_id="source-002",
                    document_id="document-002",
                ),
            ],
            supporting_evidence_ids=[
                "evidence-001",
                "evidence-002",
            ],
        )


def test_claim_rejects_duplicate_evidence_citations() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "citation evidence IDs must be unique "
            "within a claim"
        ),
    ):
        claim(
            citations=[
                citation(citation_id="citation-001"),
                citation(citation_id="citation-002"),
            ]
        )


def test_claim_rejects_overlapping_stances() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "supporting and contradicting evidence "
            "must not overlap"
        ),
    ):
        claim(
            supporting_evidence_ids=["evidence-001"],
            contradicting_evidence_ids=[" EVIDENCE-001 "],
        )


def test_claim_requires_cited_supporting_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "supporting evidence IDs must reference "
            "claim citations"
        ),
    ):
        claim(
            supporting_evidence_ids=["missing-evidence"]
        )


def test_supported_claim_requires_support() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "supported claim must contain "
            "supporting evidence"
        ),
    ):
        claim(supporting_evidence_ids=[])


def test_contested_claim_requires_contradiction() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "contested claim must contain "
            "contradicting evidence"
        ),
    ):
        claim(
            status=ResearchClaimStatus.CONTESTED,
            supporting_evidence_ids=["evidence-001"],
            contradicting_evidence_ids=[],
        )


def test_claim_set_accepts_supported_claim() -> None:
    value = ResearchClaimSet(
        request_id="research-001",
        evidence_set=evidence_set(),
        claims=[claim()],
    )

    assert len(value.supported_claims()) == 1


def test_claim_set_rejects_missing_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "all citations must reference "
            "existing evidence"
        ),
    ):
        ResearchClaimSet(
            request_id="research-001",
            evidence_set=evidence_set(),
            claims=[
                claim(
                    citations=[
                        citation(
                            evidence_id="missing-evidence"
                        )
                    ],
                    supporting_evidence_ids=[
                        "missing-evidence"
                    ],
                )
            ],
        )


def test_claim_set_rejects_task_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "citation evidence task_id must match "
            "the claim task_id"
        ),
    ):
        ResearchClaimSet(
            request_id="research-001",
            evidence_set=evidence_set(),
            claims=[
                claim(task_id="different-task")
            ],
        )


def test_claim_set_rejects_source_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "citation source_id must match "
            "the evidence source_id"
        ),
    ):
        ResearchClaimSet(
            request_id="research-001",
            evidence_set=evidence_set(),
            claims=[
                claim(
                    citations=[
                        citation(
                            source_id="different-source"
                        )
                    ]
                )
            ],
        )


def test_claim_set_rejects_excerpt_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "citation excerpt must match "
            "the evidence excerpt"
        ),
    ):
        ResearchClaimSet(
            request_id="research-001",
            evidence_set=evidence_set(),
            claims=[
                claim(
                    citations=[
                        citation(excerpt="Wrong excerpt")
                    ]
                )
            ],
        )


def test_claim_set_rejects_range_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "citation character range must match "
            "the evidence range"
        ),
    ):
        ResearchClaimSet(
            request_id="research-001",
            evidence_set=evidence_set(),
            claims=[
                claim(
                    citations=[
                        citation(
                            end_character=10
                        )
                    ]
                )
            ],
        )


def test_claim_set_rejects_contradiction_as_support() -> None:
    contradictory_citation = citation(
        citation_id="citation-002",
        evidence_id="evidence-002",
        source_id="source-002",
        document_id="document-002",
    )

    with pytest.raises(
        ValidationError,
        match=(
            "supporting evidence must not have "
            "a contradicting stance"
        ),
    ):
        ResearchClaimSet(
            request_id="research-001",
            evidence_set=evidence_set(),
            claims=[
                claim(
                    citations=[contradictory_citation],
                    supporting_evidence_ids=[
                        "evidence-002"
                    ],
                )
            ],
        )


def test_claim_set_accepts_contested_claim() -> None:
    value = ResearchClaimSet(
        request_id="research-001",
        evidence_set=evidence_set(),
        claims=[
            claim(
                status=ResearchClaimStatus.CONTESTED,
                citations=[
                    citation(),
                    citation(
                        citation_id="citation-002",
                        evidence_id="evidence-002",
                        source_id="source-002",
                        document_id="document-002",
                    ),
                ],
                supporting_evidence_ids=[
                    "evidence-001"
                ],
                contradicting_evidence_ids=[
                    "evidence-002"
                ],
            )
        ],
    )

    assert len(value.contested_claims()) == 1


def test_claim_set_filters_by_task() -> None:
    value = ResearchClaimSet(
        request_id="research-001",
        evidence_set=evidence_set(),
        claims=[claim()],
    )

    assert [
        item.claim_id
        for item in value.claims_for_task(
            " TASK-001 "
        )
    ] == [
        "claim-001"
    ]


def test_claim_set_rejects_blank_task_lookup() -> None:
    value = ResearchClaimSet(
        request_id="research-001",
        evidence_set=evidence_set(),
        claims=[],
    )

    with pytest.raises(
        ValueError,
        match="task_id must not be blank",
    ):
        value.claims_for_task(" ")
