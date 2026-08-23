"""Tests for the bounded downstream patent comparison workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from app.research.patent_claim_decomposition_runtime import (
    PatentClaimDecompositionRuntimeResult,
)
from app.research.patent_claims_runtime import PatentClaimsRuntimeResult
from app.research.patent_multi_patent_comparison_workflow import (
    PatentMultiPatentComparisonWorkflow,
)
from app.research.patent_prior_art_evidence_mapping_runtime import (
    PatentPriorArtEvidenceMappingRuntime,
)
from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceResult,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimElement,
    PatentClaimsDocumentDecomposition,
    PatentClaimSetDecomposition,
)
from app.schemas.patent_multi_patent_comparison import PatentMultiPatentComparison
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)


@dataclass(frozen=True)
class EvaluationResult:
    judgment: EvidenceRelevanceJudgment


@dataclass
class RecordingEvaluator:
    calls: list[tuple[str, str]]

    def evaluate(self, *, element_text: str, evidence_excerpt: str) -> EvaluationResult:
        self.calls.append((element_text, evidence_excerpt))
        return EvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
                relevance_score=0.6,
                rationale="Controlled workflow judgment.",
                issues=["Controlled technical gap."],
            )
        )


def workflow_request(**overrides: object) -> PatentMultiPatentComparisonRequest:
    values: dict[str, object] = {
        "target_publication_number": "EP1000000B1",
        "comparison_publication_numbers": ("EP2000000A1", "EP3000000A1"),
        "claim_language": "EN",
        "claim_number": 1,
        "maximum_claim_elements": 1,
        "maximum_mapping_calls": 2,
    }
    values.update(overrides)
    return PatentMultiPatentComparisonRequest.model_validate(values)


def decomposition(
    *,
    publication_number: str = "EP1000000B1",
    language: str = "EN",
    claim_number: int = 1,
    element_count: int = 1,
) -> PatentClaimDecompositionRuntimeResult:
    elements = tuple(
        PatentClaimElement(element_number=index, text=f"technical element {index}")
        for index in range(1, element_count + 1)
    )
    return PatentClaimDecompositionRuntimeResult(
        claims_result=PatentClaimsRuntimeResult(
            execution=None,  # type: ignore[arg-type]
            claim_documents=(),
        ),
        decomposition_documents=(
            PatentClaimsDocumentDecomposition(
                publication_number=publication_number,
                publication_docdb="EP.1000000.B1",
                source_endpoint="https://ops.epo.org/target/claims",
                claim_sets=(
                    PatentClaimSetDecomposition(
                        language=language,
                        claims=(
                            PatentClaimDecomposition(
                                claim_number=claim_number,
                                provider_position=1,
                                original_claim_text="Target claim text.",
                                elements=elements,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def evidence(
    publications: tuple[str, ...] = ("EP2000000A1", "EP3000000A1"),
) -> PatentTechnicalRelevanceEvidenceResult:
    request_id = "workflow-request-001"
    task_id = "patent-technical-relevance"
    documents: list[ResearchSourceDocument] = []
    evidence_items: list[ResearchEvidence] = []
    for index, publication in enumerate(publications, start=1):
        content = f"Exact abstract evidence for {publication}."
        source_id = f"source-{index:03d}"
        document_id = f"document-{index:03d}"
        candidate = ResearchSourceCandidate(
            source_id=source_id,
            request_id=request_id,
            task_id=task_id,
            query_id="comparison-query",
            title=f"Publication {publication}",
            url=f"https://ops.epo.org/{publication}",
            source_type=ResearchSourceType.OTHER,
            snippet=content,
            rank=index,
            metadata={
                "search_query_text": publication,
                "patent_publication_number": publication,
            },
        )
        documents.append(
            ResearchSourceDocument(
                document_id=document_id,
                candidate=candidate,
                status=ResearchSourceDocumentStatus.READ,
                content_type=ResearchSourceContentType.TEXT,
                content=content,
                language="en",
                sections=[],
                word_count=len(content.split()),
                character_count=len(content),
                reader="controlled-workflow-reader",
                metadata={"patent_publication_number": publication},
            )
        )
        evidence_items.append(
            ResearchEvidence(
                evidence_id=f"evidence-{index:03d}",
                request_id=request_id,
                task_id=task_id,
                source_id=source_id,
                document_id=document_id,
                excerpt=content,
                start_character=0,
                end_character=len(content),
                evidence_type=ResearchEvidenceType.OTHER,
                stance=ResearchEvidenceStance.NEUTRAL,
                relevance_score=1.0,
                confidence_score=1.0,
                rationale="Controlled exact abstract evidence.",
                metadata={"workflow_test": "true"},
            )
        )
    document_set = ResearchSourceDocumentSet(
        request_id=request_id,
        documents=documents,
    )
    evidence_set = ResearchEvidenceSet(
        request_id=request_id,
        document_set=document_set,
        evidence=evidence_items,
    )
    return PatentTechnicalRelevanceEvidenceResult(
        execution=None,  # type: ignore[arg-type]
        document_set=document_set,
        evidence_set=evidence_set,
    )


def test_workflow_maps_compares_and_persists_exact_artifacts(tmp_path: Path) -> None:
    evaluator = RecordingEvaluator(calls=[])
    prepared_decomposition = decomposition()
    prepared_evidence = evidence()

    result = PatentMultiPatentComparisonWorkflow(
        mapping_runtime=PatentPriorArtEvidenceMappingRuntime(evaluator=evaluator),
    ).execute(
        workflow_request(),
        decomposition_result=prepared_decomposition,
        evidence_result=prepared_evidence,
        output_dir=tmp_path,
        execution_id="workflow-001",
    )

    assert result.decomposition_result is prepared_decomposition
    assert result.evidence_result is prepared_evidence
    assert result.mapping_result.decomposition_result is prepared_decomposition
    assert result.mapping_result.evidence_result is prepared_evidence
    assert result.actual_mapping_calls == 2
    assert len(evaluator.calls) == 2
    assert result.artifact_paths.markdown_path.is_file()
    assert result.artifact_paths.json_path.is_file()

    comparison = PatentMultiPatentComparison.model_validate_json(
        result.artifact_paths.json_path.read_text(encoding="utf-8")
    )
    assert comparison is not result.comparison_result.comparisons[0]
    assert comparison == result.comparison_result.comparisons[0]
    assert comparison.prior_art_publications == (
        "EP2000000A1",
        "EP3000000A1",
    )


@pytest.mark.parametrize(
    ("prepared", "message"),
    [
        (decomposition(publication_number="EP9999999B1"), "target publication"),
        (decomposition(language="DE"), "claim language"),
        (decomposition(claim_number=2), "claim number"),
        (decomposition(element_count=2), "maximum_claim_elements"),
    ],
)
def test_decomposition_preflight_fails_before_mapping_or_writing(
    tmp_path: Path,
    prepared: PatentClaimDecompositionRuntimeResult,
    message: str,
) -> None:
    evaluator = RecordingEvaluator(calls=[])

    with pytest.raises(RuntimeError, match=message):
        PatentMultiPatentComparisonWorkflow(
            mapping_runtime=PatentPriorArtEvidenceMappingRuntime(evaluator=evaluator),
        ).execute(
            workflow_request(),
            decomposition_result=prepared,
            evidence_result=evidence(),
            output_dir=tmp_path,
            execution_id="workflow-001",
        )

    assert evaluator.calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("publications", "message"),
    [
        (("EP2000000A1",), "exactly one evidence passage"),
        (
            ("EP3000000A1", "EP2000000A1"),
            "publication order",
        ),
    ],
)
def test_evidence_preflight_fails_before_mapping_or_writing(
    tmp_path: Path,
    publications: tuple[str, ...],
    message: str,
) -> None:
    evaluator = RecordingEvaluator(calls=[])

    with pytest.raises(RuntimeError, match=message):
        PatentMultiPatentComparisonWorkflow(
            mapping_runtime=PatentPriorArtEvidenceMappingRuntime(evaluator=evaluator),
        ).execute(
            workflow_request(),
            decomposition_result=decomposition(),
            evidence_result=evidence(publications),
            output_dir=tmp_path,
            execution_id="workflow-001",
        )

    assert evaluator.calls == []
    assert list(tmp_path.iterdir()) == []


def test_actual_pair_budget_is_checked_before_mapping(tmp_path: Path) -> None:
    evaluator = RecordingEvaluator(calls=[])
    bounded_request = workflow_request(
        maximum_claim_elements=2,
        maximum_mapping_calls=4,
    ).model_copy(update={"maximum_mapping_calls": 1})

    with pytest.raises(RuntimeError, match="exceed maximum_mapping_calls"):
        PatentMultiPatentComparisonWorkflow(
            mapping_runtime=PatentPriorArtEvidenceMappingRuntime(evaluator=evaluator),
        ).execute(
            bounded_request,
            decomposition_result=decomposition(),
            evidence_result=evidence(),
            output_dir=tmp_path,
            execution_id="workflow-001",
        )

    assert evaluator.calls == []
    assert list(tmp_path.iterdir()) == []


def test_workflow_rejects_wrong_request_and_output_types(tmp_path: Path) -> None:
    workflow = PatentMultiPatentComparisonWorkflow(
        mapping_runtime=PatentPriorArtEvidenceMappingRuntime(
            evaluator=RecordingEvaluator(calls=[])
        ),
    )
    with pytest.raises(TypeError, match="request must be"):
        workflow.execute(
            object(),  # type: ignore[arg-type]
            decomposition_result=decomposition(),
            evidence_result=evidence(),
            output_dir=tmp_path,
            execution_id="workflow-001",
        )
    with pytest.raises(TypeError, match="output_dir must be a Path"):
        workflow.execute(
            workflow_request(),
            decomposition_result=decomposition(),
            evidence_result=evidence(),
            output_dir="reports",  # type: ignore[arg-type]
            execution_id="workflow-001",
        )
