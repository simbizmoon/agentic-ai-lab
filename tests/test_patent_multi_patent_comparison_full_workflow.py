"""Offline E2E tests for full explicit-input patent comparison composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from app.research.patent_multi_patent_comparison_acquisition import (
    PatentMultiPatentComparisonAcquisition,
)
from app.research.patent_multi_patent_comparison_full_workflow import (
    PatentMultiPatentComparisonFullWorkflow,
    PatentMultiPatentSelectedClaimDecomposition,
)
from app.research.patent_multi_patent_comparison_workflow import (
    PatentMultiPatentComparisonWorkflow,
)
from app.research.patent_prior_art_evidence_mapping_runtime import (
    PatentPriorArtEvidenceMappingRuntime,
)
from app.schemas.epo_ops_abstract import EpoOpsAbstractRecord
from app.schemas.epo_ops_bibliographic import EpoOpsBibliographicRecord
from app.schemas.epo_ops_claims import (
    EpoOpsClaimSet,
    EpoOpsClaimsRecord,
    EpoOpsClaimText,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimElement,
)
from app.schemas.patent_claims import PatentClaim
from app.schemas.patent_multi_patent_comparison import PatentMultiPatentComparison
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


@dataclass
class FakeClaimsRetriever:
    calls: list[str]

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsClaimsRecord:
        self.calls.append(record.publication_number)
        return EpoOpsClaimsRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            source_endpoint="https://ops.epo.org/target/claims",
            claim_sets=(
                EpoOpsClaimSet(
                    language="EN",
                    claims=(
                        EpoOpsClaimText(
                            position=1,
                            text="1. A system comprising a sensor and controller.",
                        ),
                    ),
                ),
            ),
        )


@dataclass
class FakeAbstractRetriever:
    calls: list[str]

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsAbstractRecord:
        self.calls.append(record.publication_number)
        return EpoOpsAbstractRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            abstract_text=f"A sensor and controller from {record.publication_number}.",
            abstract_language="en",
            source_endpoint=f"https://ops.epo.org/{record.publication_docdb}/abstract",
        )


@dataclass(frozen=True)
class DecompositionResult:
    decomposition: PatentClaimDecomposition


@dataclass
class FakeClaimDecomposer:
    calls: list[PatentClaim]
    element_count: int = 1
    invent_wording: bool = False

    def decompose(self, claim: PatentClaim) -> DecompositionResult:
        self.calls.append(claim)
        if self.invent_wording:
            elements = (PatentClaimElement(element_number=1, text="invented actuator"),)
        elif self.element_count == 2:
            elements = (
                PatentClaimElement(
                    element_number=1,
                    text="A system comprising a sensor",
                ),
                PatentClaimElement(element_number=2, text="controller"),
            )
        else:
            elements = (PatentClaimElement(element_number=1, text=claim.text),)
        return DecompositionResult(
            decomposition=PatentClaimDecomposition(
                claim_number=claim.claim_number,
                provider_position=claim.provider_position,
                original_claim_text=claim.text,
                elements=elements,
            )
        )


@dataclass(frozen=True)
class EvaluationResult:
    judgment: EvidenceRelevanceJudgment


@dataclass
class FakeMappingEvaluator:
    calls: list[tuple[str, str]]

    def evaluate(self, *, element_text: str, evidence_excerpt: str) -> EvaluationResult:
        self.calls.append((element_text, evidence_excerpt))
        return EvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
                relevance_score=0.7,
                rationale="Offline E2E technical judgment.",
                issues=["Offline E2E technical gap."],
            )
        )


def request(**overrides: object) -> PatentMultiPatentComparisonRequest:
    values: dict[str, object] = {
        "target_publication_number": "EP1000000B1",
        "comparison_publication_numbers": ("EP2000000A1", "EP3000000A1"),
        "claim_language": "EN",
        "claim_number": 1,
        "maximum_claim_elements": 1,
        "maximum_mapping_calls": 2,
        "maximum_bytes": 4096,
    }
    values.update(overrides)
    return PatentMultiPatentComparisonRequest.model_validate(values)


def full_workflow(
    *,
    claims: FakeClaimsRetriever,
    abstracts: FakeAbstractRetriever,
    decomposer: FakeClaimDecomposer,
    evaluator: FakeMappingEvaluator,
) -> PatentMultiPatentComparisonFullWorkflow:
    return PatentMultiPatentComparisonFullWorkflow(
        acquisition=PatentMultiPatentComparisonAcquisition(
            claims_retriever=claims,
            abstract_retriever=abstracts,
        ),
        selected_decomposition=PatentMultiPatentSelectedClaimDecomposition(
            claim_decomposer=decomposer,
        ),
        downstream_workflow=PatentMultiPatentComparisonWorkflow(
            mapping_runtime=PatentPriorArtEvidenceMappingRuntime(evaluator=evaluator),
        ),
    )


def test_full_offline_workflow_persists_exact_comparison(tmp_path: Path) -> None:
    claims = FakeClaimsRetriever(calls=[])
    abstracts = FakeAbstractRetriever(calls=[])
    decomposer = FakeClaimDecomposer(calls=[])
    evaluator = FakeMappingEvaluator(calls=[])
    source_request = request()

    result = full_workflow(
        claims=claims,
        abstracts=abstracts,
        decomposer=decomposer,
        evaluator=evaluator,
    ).execute(
        source_request,
        request_id="full-workflow-001",
        output_dir=tmp_path,
        execution_id="comparison-001",
    )

    assert result.request is source_request
    assert result.acquisition.request is source_request
    assert result.workflow_result.request is source_request
    assert claims.calls == ["EP1000000B1"]
    assert abstracts.calls == ["EP2000000A1", "EP3000000A1"]
    assert len(decomposer.calls) == 1
    assert decomposer.calls[0] is result.acquisition.selected_target_claim
    assert len(evaluator.calls) == 2
    assert result.workflow_result.actual_mapping_calls == 2

    paths = result.workflow_result.artifact_paths
    comparison = PatentMultiPatentComparison.model_validate_json(
        paths.json_path.read_text(encoding="utf-8")
    )
    assert paths.markdown_path.is_file()
    assert comparison.target_publication_number == "EP1000000B1"
    assert comparison.prior_art_publications == (
        "EP2000000A1",
        "EP3000000A1",
    )
    evaluations = comparison.claim_sets[0].claims[0].rows[0].publications
    assert tuple(cell.publication_number for cell in evaluations) == (
        "EP2000000A1",
        "EP3000000A1",
    )
    assert tuple(cell.evaluations[0].evidence_id for cell in evaluations) == (
        "patent-comparison-evidence-001",
        "patent-comparison-evidence-002",
    )


def test_selected_decomposition_preserves_claim_identity_and_one_document() -> None:
    claims = FakeClaimsRetriever(calls=[])
    acquisition = PatentMultiPatentComparisonAcquisition(
        claims_retriever=claims,
        abstract_retriever=FakeAbstractRetriever(calls=[]),
    ).acquire(request(), request_id="full-workflow-001")
    decomposer = FakeClaimDecomposer(calls=[])

    result = PatentMultiPatentSelectedClaimDecomposition(
        claim_decomposer=decomposer,
    ).decompose(acquisition)

    assert len(decomposer.calls) == 1
    assert len(result.decomposition_documents) == 1
    document = result.decomposition_documents[0]
    assert document.publication_number == "EP1000000B1"
    assert tuple(item.language for item in document.claim_sets) == ("EN",)
    decomposition = document.claim_sets[0].claims[0]
    assert decomposition.claim_number == 1
    assert decomposition.provider_position == 1
    assert decomposition.original_claim_text == acquisition.selected_target_claim.text


def test_element_bound_failure_prevents_mapping_and_artifacts(tmp_path: Path) -> None:
    evaluator = FakeMappingEvaluator(calls=[])

    with pytest.raises(RuntimeError, match="exceeds maximum_claim_elements"):
        full_workflow(
            claims=FakeClaimsRetriever(calls=[]),
            abstracts=FakeAbstractRetriever(calls=[]),
            decomposer=FakeClaimDecomposer(calls=[], element_count=2),
            evaluator=evaluator,
        ).execute(
            request(),
            request_id="full-workflow-001",
            output_dir=tmp_path,
            execution_id="comparison-001",
        )

    assert evaluator.calls == []
    assert list(tmp_path.iterdir()) == []


def test_grounding_failure_prevents_mapping_and_artifacts(tmp_path: Path) -> None:
    evaluator = FakeMappingEvaluator(calls=[])

    with pytest.raises(RuntimeError, match="wording or order not grounded"):
        full_workflow(
            claims=FakeClaimsRetriever(calls=[]),
            abstracts=FakeAbstractRetriever(calls=[]),
            decomposer=FakeClaimDecomposer(calls=[], invent_wording=True),
            evaluator=evaluator,
        ).execute(
            request(),
            request_id="full-workflow-001",
            output_dir=tmp_path,
            execution_id="comparison-001",
        )

    assert evaluator.calls == []
    assert list(tmp_path.iterdir()) == []


def test_full_workflow_rejects_wrong_request_type(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="request must be"):
        full_workflow(
            claims=FakeClaimsRetriever(calls=[]),
            abstracts=FakeAbstractRetriever(calls=[]),
            decomposer=FakeClaimDecomposer(calls=[]),
            evaluator=FakeMappingEvaluator(calls=[]),
        ).execute(
            object(),  # type: ignore[arg-type]
            request_id="full-workflow-001",
            output_dir=tmp_path,
            execution_id="comparison-001",
        )
