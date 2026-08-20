"""Tests for patent claim-element to prior-art evidence mapping runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.research.patent_claim_decomposition_runtime import (
    PatentClaimDecompositionRuntimeResult,
)
from app.research.patent_claims_runtime import PatentClaimsRuntimeResult
from app.research.patent_prior_art_evidence_mapping_runtime import (
    PatentPriorArtEvidenceMappingRuntime,
)
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceResult,
)
from app.schemas.epo_ops_abstract import EpoOpsVerifiedPatentRecord
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsDocumentIdType,
    EpoOpsSearchRequest,
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
from app.schemas.patent_research_collection_result import (
    PatentResearchCollectionResult,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    PatentSearchQuery,
    PatentSearchQueryPurpose,
)
from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
    PatentSourceFamily,
    PatentSourceMetadata,
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
class ControlledEvaluationResult:
    judgment: EvidenceRelevanceJudgment


@dataclass
class ControlledEvaluator:
    calls: list[tuple[str, str]]

    def evaluate(
        self,
        *,
        element_text: str,
        evidence_excerpt: str,
    ) -> ControlledEvaluationResult:
        self.calls.append((element_text, evidence_excerpt))
        direct = "pressure sensor" in element_text.casefold() and (
            "pressure sensor" in evidence_excerpt.casefold()
        )
        return ControlledEvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=(
                    EvidenceRelevanceLevel.DIRECTLY_RELEVANT
                    if direct
                    else EvidenceRelevanceLevel.IRRELEVANT
                ),
                relevance_score=0.95 if direct else 0.05,
                rationale=(
                    "The technical feature is directly described."
                    if direct
                    else "The excerpt does not describe this technical feature."
                ),
                issues=[] if direct else ["technical feature absent"],
            )
        )


def research_request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="How can pressure sensors detect seat occupancy?",
        objective="Identify relevant sensing mechanisms.",
        maximum_search_results=2,
        maximum_sources=2,
        maximum_bytes=4096,
    )


def execution() -> PatentResearchPlanExecutionResult:
    request = research_request()
    query = PatentSearchQuery(
        cql_query='ta all "pressure sensor"',
        purpose=PatentSearchQueryPurpose.PRIMARY,
    )
    record = EpoOpsBibliographicRecord(
        publication_number="EP123456A1",
        publication_docdb="EP.123456.A1",
        title="Seat occupancy sensing system",
        publication_date=date(2025, 1, 15),
        source_endpoint="https://ops.epo.org/3.2/rest-services/search",
        document_id_type=EpoOpsDocumentIdType.DOCDB,
        application_number=None,
        title_language="en",
    )
    verified = EpoOpsVerifiedPatentRecord(
        metadata=PatentSourceMetadata(
            source_family=PatentSourceFamily.EPO_OPS,
            publication_number="EP123456A1",
            title="Seat occupancy sensing system",
            source_url="https://ops.epo.org/3.2/rest-services/EP123456A1",
            metadata_verification_state=PatentMetadataVerificationState.VERIFIED,
            publication_date=date(2025, 1, 15),
        ),
        abstract_text=(
            "A pressure sensor determines whether a seat is occupied. "
            "A display presents a status."
        ),
        abstract_language="en",
    )
    return PatentResearchPlanExecutionResult(
        query=query,
        collection=PatentResearchCollectionResult(
            request=request,
            search_result=EpoOpsBibliographicSearchResult(
                request=EpoOpsSearchRequest(
                    cql_query=query.cql_query,
                    maximum_results=2,
                ),
                records=(record,),
            ),
            verified_records=(verified,),
        ),
        attempted_queries=(query,),
    )


def decomposition_result() -> PatentClaimDecompositionRuntimeResult:
    claim_text = (
        "A system comprising a pressure sensor configured to detect seat "
        "occupancy and a controller configured to generate an alert."
    )
    decomposition_document = PatentClaimsDocumentDecomposition(
        publication_number="EP999999B1",
        publication_docdb="EP.999999.B1",
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/publication/docdb/EP.999999.B1/claims"
        ),
        claim_sets=(
            PatentClaimSetDecomposition(
                language="EN",
                claims=(
                    PatentClaimDecomposition(
                        claim_number=1,
                        provider_position=1,
                        original_claim_text=claim_text,
                        elements=(
                            PatentClaimElement(
                                element_number=1,
                                text=(
                                    "a pressure sensor configured to detect "
                                    "seat occupancy"
                                ),
                            ),
                            PatentClaimElement(
                                element_number=2,
                                text=("a controller configured to generate an alert"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    return PatentClaimDecompositionRuntimeResult(
        claims_result=PatentClaimsRuntimeResult(
            execution=execution(),
            claim_documents=(),
        ),
        decomposition_documents=(decomposition_document,),
    )


def evidence_result(
    *,
    include_evidence: bool = True,
) -> PatentTechnicalRelevanceEvidenceResult:
    source_text = (
        "A pressure sensor determines whether a seat is occupied. "
        "A display presents a status."
    )
    candidate = ResearchSourceCandidate(
        source_id="patent-source-001",
        request_id="mapping-request-001",
        task_id="patent-technical-relevance",
        query_id="patent-query-primary",
        title="Seat occupancy sensing system",
        url="https://ops.epo.org/3.2/rest-services/EP123456A1",
        source_type=ResearchSourceType.OTHER,
        snippet=source_text,
        published_at=date(2025, 1, 15),
        rank=1,
        metadata={
            "search_query_text": 'ta all "pressure sensor"',
            "patent_source_family": "epo_ops",
            "patent_publication_number": "EP123456A1",
            "patent_verification_state": "verified",
            "patent_query_purpose": "primary",
        },
    )
    document = ResearchSourceDocument(
        document_id="patent-document-001",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=source_text,
        language="en",
        sections=[],
        word_count=len(source_text.split()),
        character_count=len(source_text),
        reader="verified-epo-patent-adapter",
        metadata={
            "patent_source_family": "epo_ops",
            "patent_publication_number": "EP123456A1",
            "patent_verification_state": "verified",
            "patent_query_purpose": "primary",
            "patent_abstract_language": "en",
        },
    )
    document_set = ResearchSourceDocumentSet(
        request_id="mapping-request-001",
        documents=[document],
    )

    evidence = []
    if include_evidence:
        excerpt = "A pressure sensor determines whether a seat is occupied."
        evidence.append(
            ResearchEvidence(
                evidence_id="evidence-001",
                request_id="mapping-request-001",
                task_id="patent-technical-relevance",
                source_id="patent-source-001",
                document_id="patent-document-001",
                excerpt=excerpt,
                start_character=0,
                end_character=len(excerpt),
                evidence_type=ResearchEvidenceType.FACT,
                stance=ResearchEvidenceStance.NEUTRAL,
                relevance_score=0.95,
                confidence_score=0.9,
                rationale="Relevant sensing passage.",
                metadata={
                    "semantic_relevance_level": "directly_relevant",
                },
            )
        )

    evidence_set = ResearchEvidenceSet(
        request_id="mapping-request-001",
        document_set=document_set,
        evidence=evidence,
    )

    return PatentTechnicalRelevanceEvidenceResult(
        execution=execution(),
        document_set=document_set,
        evidence_set=evidence_set,
    )


def test_runtime_maps_every_element_against_ordered_evidence() -> None:
    evaluator = ControlledEvaluator(calls=[])

    result = PatentPriorArtEvidenceMappingRuntime(
        evaluator=evaluator,
    ).map(
        decomposition_result=decomposition_result(),
        evidence_result=evidence_result(),
    )

    assert len(result.mapping_documents) == 1
    document = result.mapping_documents[0]
    assert document.publication_number == "EP999999B1"
    assert document.publication_docdb == "EP.999999.B1"

    claim = document.claim_sets[0].claims[0]
    assert claim.claim_number == 1
    assert [element.element_number for element in claim.elements] == [1, 2]
    assert len(evaluator.calls) == 2

    first = claim.elements[0].evaluations[0]
    assert first.publication_number == "EP123456A1"
    assert first.evidence_id == "evidence-001"
    assert first.source_id == "patent-source-001"
    assert first.document_id == "patent-document-001"
    assert first.judgment.relevance_level is EvidenceRelevanceLevel.DIRECTLY_RELEVANT

    second = claim.elements[1].evaluations[0]
    assert second.judgment.relevance_level is EvidenceRelevanceLevel.IRRELEVANT


def test_runtime_preserves_exact_evidence_excerpt_and_offsets() -> None:
    evaluator = ControlledEvaluator(calls=[])

    result = PatentPriorArtEvidenceMappingRuntime(
        evaluator=evaluator,
    ).map(
        decomposition_result=decomposition_result(),
        evidence_result=evidence_result(),
    )

    evaluation = (
        result.mapping_documents[0].claim_sets[0].claims[0].elements[0].evaluations[0]
    )

    source_document = result.evidence_result.document_set.documents[0]
    assert (
        source_document.content[evaluation.start_character : evaluation.end_character]
        == evaluation.excerpt
    )


def test_zero_evidence_produces_empty_evaluations_without_calls() -> None:
    evaluator = ControlledEvaluator(calls=[])

    result = PatentPriorArtEvidenceMappingRuntime(
        evaluator=evaluator,
    ).map(
        decomposition_result=decomposition_result(),
        evidence_result=evidence_result(include_evidence=False),
    )

    elements = result.mapping_documents[0].claim_sets[0].claims[0].elements
    assert [element.evaluations for element in elements] == [(), ()]
    assert evaluator.calls == []


def test_zero_decomposition_documents_produce_zero_mappings() -> None:
    evaluator = ControlledEvaluator(calls=[])
    empty = decomposition_result()
    empty = PatentClaimDecompositionRuntimeResult(
        claims_result=empty.claims_result,
        decomposition_documents=(),
    )

    result = PatentPriorArtEvidenceMappingRuntime(
        evaluator=evaluator,
    ).map(
        decomposition_result=empty,
        evidence_result=evidence_result(),
    )

    assert result.mapping_documents == ()
    assert evaluator.calls == []


def test_runtime_fails_when_publication_identity_is_missing() -> None:
    evaluator = ControlledEvaluator(calls=[])
    base = evidence_result()
    document = base.document_set.documents[0]
    candidate = document.candidate.model_copy(
        update={
            "metadata": {
                key: value
                for key, value in document.candidate.metadata.items()
                if key != "patent_publication_number"
            }
        }
    )
    changed_document = document.model_copy(update={"candidate": candidate})
    changed_set = ResearchSourceDocumentSet(
        request_id=base.document_set.request_id,
        documents=[changed_document],
    )
    changed_evidence = base.evidence_set.model_copy(
        update={"document_set": changed_set}
    )
    changed = PatentTechnicalRelevanceEvidenceResult(
        execution=base.execution,
        document_set=changed_set,
        evidence_set=changed_evidence,
    )

    with pytest.raises(RuntimeError, match="lacked publication identity"):
        PatentPriorArtEvidenceMappingRuntime(
            evaluator=evaluator,
        ).map(
            decomposition_result=decomposition_result(),
            evidence_result=changed,
        )


def test_runtime_preserves_irrelevant_evaluations_for_audit_trail() -> None:
    evaluator = ControlledEvaluator(calls=[])

    result = PatentPriorArtEvidenceMappingRuntime(
        evaluator=evaluator,
    ).map(
        decomposition_result=decomposition_result(),
        evidence_result=evidence_result(),
    )

    evaluations = result.mapping_documents[0].claim_sets[0].claims[0].elements
    assert (
        evaluations[1].evaluations[0].judgment.relevance_level
        is EvidenceRelevanceLevel.IRRELEVANT
    )


def test_runtime_does_not_create_legal_conclusion_fields() -> None:
    evaluator = ControlledEvaluator(calls=[])

    result = PatentPriorArtEvidenceMappingRuntime(
        evaluator=evaluator,
    ).map(
        decomposition_result=decomposition_result(),
        evidence_result=evidence_result(),
    )

    serialized = repr(result.mapping_documents[0].model_dump()).casefold()
    for forbidden in (
        "novelty",
        "anticipation",
        "obviousness",
        "invalidity",
        "infringement",
        "freedom_to_operate",
        "essentiality",
    ):
        assert forbidden not in serialized
