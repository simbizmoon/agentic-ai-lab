"""Tests for semantic citation verification service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.exceptions import StructuredResponseParseError
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationBatchEvaluationResult,
    SemanticCitationEvaluationResult,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
    ResearchCitationVerification,
)
from app.research.semantic_citation_verification_service import (
    SemanticCitationVerificationService,
)
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
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)

CONTENT = "Agent memory stores contextual information."


@dataclass
class FakeSemanticEvaluator:
    """Return one deterministic semantic judgment."""

    score: float = 0.9

    def evaluate(
        self,
        *,
        claim_text: str,
        evidence_excerpt: str,
    ) -> SemanticCitationEvaluationResult:
        assert claim_text.strip()
        assert evidence_excerpt.strip()

        return SemanticCitationEvaluationResult(
            judgment=SemanticCitationJudgment(
                support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                entailment_score=self.score,
                rationale="Evidence supports the claim.",
                issues=[],
            ),
            decision=(
                ResearchCitationDecision.VERIFIED
            ),
            response_id="resp-semantic-001",
            request_id="req-semantic-001",
            usage=None,
            elapsed_seconds=0.01,
        )


def build_evidence_set(
    *,
    request_id: str = "research-001",
) -> ResearchEvidenceSet:
    """Build one valid evidence set."""

    candidate = ResearchSourceCandidate(
        source_id="source-001",
        request_id=request_id,
        task_id="task-001",
        query_id="query-001",
        title="Agent memory research",
        url="https://example.com/source",
        source_type=ResearchSourceType.ACADEMIC,
        author="Example Author",
        publisher="Example Publisher",
        published_at=date(2026, 1, 1),
        rank=1,
    )

    document = ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        language="en",
        sections=[],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="test-reader",
    )

    document_set = ResearchSourceDocumentSet(
        request_id=request_id,
        documents=[document],
    )

    evidence = ResearchEvidence(
        evidence_id="evidence-001",
        request_id=request_id,
        task_id="task-001",
        source_id="source-001",
        document_id="document-001",
        excerpt=CONTENT,
        start_character=0,
        end_character=len(CONTENT),
        evidence_type=ResearchEvidenceType.FACT,
        stance=ResearchEvidenceStance.SUPPORTS,
        relevance_score=0.9,
        confidence_score=0.8,
    )

    return ResearchEvidenceSet(
        request_id=request_id,
        document_set=document_set,
        evidence=[evidence],
    )


def build_claim_set(
    evidence_set: ResearchEvidenceSet,
) -> ResearchClaimSet:
    """Build one valid claim linked to the evidence."""

    evidence = evidence_set.evidence[0]

    citation = ResearchCitation(
        citation_id="citation-001",
        evidence_id=evidence.evidence_id,
        source_id=evidence.source_id,
        document_id=evidence.document_id,
        excerpt=evidence.excerpt,
        start_character=evidence.start_character,
        end_character=evidence.end_character,
    )

    claim = ResearchClaim(
        claim_id="claim-001",
        request_id=evidence.request_id,
        task_id=evidence.task_id,
        text=evidence.excerpt,
        claim_type=ResearchClaimType.FACTUAL,
        status=ResearchClaimStatus.SUPPORTED,
        confidence_score=evidence.confidence_score,
        citations=[citation],
        supporting_evidence_ids=[
            evidence.evidence_id
        ],
    )

    return ResearchClaimSet(
        request_id=evidence_set.request_id,
        evidence_set=evidence_set,
        claims=[claim],
    )


def test_service_verifies_all_citations() -> None:
    evidence_set = build_evidence_set()
    claim_set = build_claim_set(evidence_set)

    service = SemanticCitationVerificationService(
        evaluator=FakeSemanticEvaluator(),
        verification_id_factory=(
            lambda: "verification-001"
        ),
    )

    result = service.verify(
        claim_set=claim_set,
        evidence_set=evidence_set,
    )

    assert len(result) == 1

    verification = result[0]

    assert verification.verification_id == (
        "verification-001"
    )
    assert verification.claim_id == "claim-001"
    assert verification.citation_id == "citation-001"
    assert verification.evidence_id == "evidence-001"
    assert verification.source_id == "source-001"
    assert verification.decision is (
        ResearchCitationDecision.VERIFIED
    )
    assert verification.support_level is (
        SemanticCitationSupportLevel.FULLY_SUPPORTED
    )
    assert verification.entailment_score == pytest.approx(
        0.9
    )
    assert verification.traceability_score == pytest.approx(
        1.0
    )
    assert (
        verification.citation_accuracy_score
        == pytest.approx(1.0)
    )
    assert (
        verification.metadata["response_id"]
        == "resp-semantic-001"
    )


def test_service_rejects_request_mismatch() -> None:
    evidence_set = build_evidence_set()
    claim_set = build_claim_set(evidence_set).model_copy(
        update={"request_id": "other-request"}
    )

    service = SemanticCitationVerificationService(
        evaluator=FakeSemanticEvaluator(),
    )

    with pytest.raises(
        ValueError,
        match="request_id",
    ):
        service.verify(
            claim_set=claim_set,
            evidence_set=evidence_set,
        )


def test_service_rejects_blank_verification_id() -> None:
    evidence_set = build_evidence_set()
    claim_set = build_claim_set(evidence_set)

    service = SemanticCitationVerificationService(
        evaluator=FakeSemanticEvaluator(),
        verification_id_factory=lambda: " ",
    )

    with pytest.raises(
        ValueError,
        match="verification_id factory returned blank value",
    ):
        service.verify(
            claim_set=claim_set,
            evidence_set=evidence_set,
        )


def test_verification_rejects_support_decision_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match="decision must match semantic support_level",
    ):
        ResearchCitationVerification(
            verification_id="verification-mismatch",
            claim_id="claim-001",
            citation_id="citation-001",
            evidence_id="evidence-001",
            source_id="source-001",
            decision=ResearchCitationDecision.VERIFIED,
            support_level=(
                SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
            ),
            entailment_score=0.5,
            traceability_score=1.0,
            citation_accuracy_score=1.0,
            rationale="Intentional mismatch.",
            issues=[],
        )

@dataclass
class BatchSemanticEvaluator(FakeSemanticEvaluator):
    """Support batch evaluation while recording physical calls."""

    batch_error: Exception | None = None

    def __post_init__(self) -> None:
        self.batch_calls: list[
            list[tuple[str, str, str]]
        ] = []
        self.single_calls = 0

    def evaluate_batch(
        self,
        *,
        citation_items: list[tuple[str, str, str]],
    ) -> SemanticCitationBatchEvaluationResult:
        self.batch_calls.append(list(citation_items))
        if self.batch_error is not None:
            raise self.batch_error

        judgment_value = SemanticCitationJudgment(
            support_level=(
                SemanticCitationSupportLevel.FULLY_SUPPORTED
            ),
            entailment_score=self.score,
            rationale="Evidence supports the claim.",
            issues=[],
        )
        return SemanticCitationBatchEvaluationResult(
            judgments={
                item_id: judgment_value
                for item_id, _claim, _evidence
                in reversed(citation_items)
            },
            decisions={
                item_id: ResearchCitationDecision.VERIFIED
                for item_id, _claim, _evidence
                in citation_items
            },
            response_id="resp-semantic-batch",
            request_id="req-semantic-batch",
            usage=None,
            elapsed_seconds=0.02,
        )

    def evaluate(
        self,
        *,
        claim_text: str,
        evidence_excerpt: str,
    ) -> SemanticCitationEvaluationResult:
        self.single_calls += 1
        return super().evaluate(
            claim_text=claim_text,
            evidence_excerpt=evidence_excerpt,
        )


def build_three_pair_claim_set(
    evidence_set: ResearchEvidenceSet,
) -> ResearchClaimSet:
    """Build three claims citing the same code-owned evidence."""

    base = build_claim_set(evidence_set).claims[0]
    claims = []
    for index in range(1, 4):
        citation = base.citations[0].model_copy(
            update={
                "citation_id": f"citation-{index:03d}",
            }
        )
        claims.append(
            base.model_copy(
                update={
                    "claim_id": f"claim-{index:03d}",
                    "citations": [citation],
                }
            )
        )

    return ResearchClaimSet(
        request_id=evidence_set.request_id,
        evidence_set=evidence_set,
        claims=claims,
    )


def test_batch_service_verifies_three_pairs_with_one_physical_call(
) -> None:
    evidence_set = build_evidence_set()
    claim_set = build_three_pair_claim_set(evidence_set)
    evaluator = BatchSemanticEvaluator()
    evaluator.__post_init__()
    ids = iter(
        [
            "verification-001",
            "verification-002",
            "verification-003",
        ]
    )
    service = SemanticCitationVerificationService(
        evaluator=evaluator,
        verification_id_factory=lambda: next(ids),
    )

    values = service.verify(
        claim_set=claim_set,
        evidence_set=evidence_set,
    )

    assert len(values) == 3
    assert len(evaluator.batch_calls) == 1
    assert evaluator.single_calls == 0
    assert service.last_usage.attempts == 1
    assert [
        value.claim_id
        for value in values
    ] == [
        "claim-001",
        "claim-002",
        "claim-003",
    ]
    assert [
        value.citation_id
        for value in values
    ] == [
        "citation-001",
        "citation-002",
        "citation-003",
    ]
    assert all(
        value.evidence_id == "evidence-001"
        for value in values
    )
    assert all(
        value.metadata["response_id"]
        == "resp-semantic-batch"
        for value in values
    )


def test_batch_structured_failure_falls_back_to_singles() -> None:
    evidence_set = build_evidence_set()
    claim_set = build_three_pair_claim_set(evidence_set)
    evaluator = BatchSemanticEvaluator(
        batch_error=StructuredResponseParseError(
            "bad batch"
        )
    )
    evaluator.__post_init__()
    ids = iter(
        [
            "verification-001",
            "verification-002",
            "verification-003",
        ]
    )
    service = SemanticCitationVerificationService(
        evaluator=evaluator,
        verification_id_factory=lambda: next(ids),
    )

    values = service.verify(
        claim_set=claim_set,
        evidence_set=evidence_set,
    )

    assert len(values) == 3
    assert len(evaluator.batch_calls) == 1
    assert evaluator.single_calls == 3
    assert service.last_usage.attempts == 4


def test_batch_programming_error_propagates() -> None:
    evidence_set = build_evidence_set()
    claim_set = build_claim_set(evidence_set)
    evaluator = BatchSemanticEvaluator(
        batch_error=RuntimeError("programming failure")
    )
    evaluator.__post_init__()
    service = SemanticCitationVerificationService(
        evaluator=evaluator,
    )

    with pytest.raises(
        RuntimeError,
        match="programming failure",
    ):
        service.verify(
            claim_set=claim_set,
            evidence_set=evidence_set,
        )
