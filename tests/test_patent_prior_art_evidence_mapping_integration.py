"""Offline integration test from patent claims and evidence into mappings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.budget import ExecutionBudget
from app.rag.embedding_provider import EmbeddingProvider
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.epo_ops_claims_retriever import EpoOpsClaimsRetriever
from app.research.epo_ops_client import EpoOpsHttpResponse
from app.research.openai_evidence_relevance_evaluator import (
    EvidenceRelevanceEvaluationResult,
)
from app.research.paragraph_evidence_extractor import ParagraphEvidenceExtractor
from app.research.patent_claim_chart_runtime import PatentClaimChartRuntime
from app.research.patent_claim_decomposition_runtime import (
    PatentClaimDecompositionRuntime,
)
from app.research.patent_claim_parser import parse_epo_ops_claims_record
from app.research.patent_claims_runtime import PatentClaimsRuntimeResult
from app.research.patent_prior_art_evidence_mapping_runtime import (
    PatentPriorArtEvidenceMappingRuntime,
)
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceRuntime,
)
from app.research.pipeline_analysis_adapters import PipelineEvidenceExtractorAdapter
from app.research.semantic_evidence_reranker import SemanticEvidenceReranker
from app.research.semantic_research_evidence_extractor import (
    SemanticResearchEvidenceExtractor,
)
from app.schemas.document_embedding import TextEmbedding
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
)
from app.schemas.patent_claims import PatentClaim
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
from app.services.text_generation import TokenUsage

FIXTURES = Path(__file__).parent / "fixtures" / "epo_ops"


class FakeClaimsClient:
    def __init__(self, fixture: str) -> None:
        self.body = (FIXTURES / fixture).read_bytes()

    def authenticated_get_response(
        self,
        *,
        endpoint: str,
        accept: str,
        extra_headers: dict[str, str] | None = None,
    ) -> EpoOpsHttpResponse:
        assert endpoint.endswith(
            "/published-data/publication/docdb/EP.1000000.B1/claims"
        )
        assert accept == "application/fulltext+xml"
        assert extra_headers is None
        return EpoOpsHttpResponse(
            body=self.body,
            content_type="application/fulltext+xml;charset=utf-8",
        )


@dataclass(frozen=True)
class FakeDecompositionResult:
    decomposition: PatentClaimDecomposition


class EchoClaimDecomposer:
    """Keep one whole parsed claim as one grounded technical element."""

    def decompose(self, claim: PatentClaim) -> FakeDecompositionResult:
        return FakeDecompositionResult(
            decomposition=PatentClaimDecomposition(
                claim_number=claim.claim_number,
                provider_position=claim.provider_position,
                original_claim_text=claim.text,
                elements=(
                    PatentClaimElement(
                        element_number=1,
                        text=claim.text,
                    ),
                ),
            )
        )


class ControlledEmbeddingProvider(EmbeddingProvider):
    @property
    def model_name(self) -> str:
        return "offline-patent-mapping"

    @property
    def dimensions(self) -> int:
        return 2

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=2,
                vector=self._vector(text),
            )
            for text in texts
        ]

    @staticmethod
    def _vector(text: str) -> list[float]:
        normalized = text.casefold()
        if "english claim one" in normalized or "claim one" in normalized:
            return [1.0, 0.0]
        return [0.0, 1.0]


@dataclass
class ControlledEvidenceRelevanceEvaluator:
    calls: list[str]

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        evidence_excerpt: str,
    ) -> EvidenceRelevanceEvaluationResult:
        self.calls.append(evidence_excerpt)
        relevant = "english claim one" in evidence_excerpt.casefold()
        return EvidenceRelevanceEvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=(
                    EvidenceRelevanceLevel.DIRECTLY_RELEVANT
                    if relevant
                    else EvidenceRelevanceLevel.IRRELEVANT
                ),
                relevance_score=0.95 if relevant else 0.05,
                rationale=(
                    "The passage contains the selected technical phrase."
                    if relevant
                    else "The passage does not contain the selected phrase."
                ),
                issues=[],
            ),
            response_id="resp-offline-evidence",
            request_id="req-offline-evidence",
            usage=TokenUsage(
                input_tokens=10,
                cached_input_tokens=0,
                output_tokens=2,
                reasoning_tokens=0,
                total_tokens=12,
            ),
            elapsed_seconds=0.0,
        )


@dataclass(frozen=True)
class ControlledElementEvaluationResult:
    judgment: EvidenceRelevanceJudgment


@dataclass
class ControlledElementEvidenceEvaluator:
    calls: list[tuple[str, str]]

    def evaluate(
        self,
        *,
        element_text: str,
        evidence_excerpt: str,
    ) -> ControlledElementEvaluationResult:
        self.calls.append((element_text, evidence_excerpt))
        direct = (
            "english claim one" in element_text.casefold()
            and "english claim one" in evidence_excerpt.casefold()
        )
        return ControlledElementEvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=(
                    EvidenceRelevanceLevel.DIRECTLY_RELEVANT
                    if direct
                    else EvidenceRelevanceLevel.IRRELEVANT
                ),
                relevance_score=0.95 if direct else 0.05,
                rationale=(
                    "The element and evidence describe the same fixture phrase."
                    if direct
                    else "The fixture evidence does not describe this element."
                ),
                issues=[] if direct else ["fixture phrase mismatch"],
            )
        )


def target_bibliographic_record() -> EpoOpsBibliographicRecord:
    return EpoOpsBibliographicRecord(
        publication_number="EP1000000B1",
        publication_docdb="EP.1000000.B1",
        title="Fixture target patent",
        publication_date=None,
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
        ),
        document_id_type=EpoOpsDocumentIdType.DOCDB,
    )


def prior_art_execution() -> PatentResearchPlanExecutionResult:
    request = PatentResearchRequest(
        question="Which passage is technically related to English claim one?",
        objective="Select traceable prior-art technical evidence.",
        maximum_search_results=2,
        maximum_sources=2,
        maximum_bytes=4096,
    )
    query = PatentSearchQuery(
        cql_query='ta all "English claim one"',
        purpose=PatentSearchQueryPurpose.PRIMARY,
    )
    abstract = (
        "English claim one describes a pressure sensing arrangement for "
        "detecting occupancy in a seat.\n\n"
        "A separate paragraph discusses an unrelated optical display."
    )
    bibliographic = EpoOpsBibliographicRecord(
        publication_number="EP2000000A1",
        publication_docdb="EP.2000000.A1",
        title="Prior-art fixture patent",
        publication_date=date(2025, 1, 15),
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/search/biblio?q=test"
        ),
        document_id_type=EpoOpsDocumentIdType.DOCDB,
        title_language="en",
    )
    verified = EpoOpsVerifiedPatentRecord(
        metadata=PatentSourceMetadata(
            source_family=PatentSourceFamily.EPO_OPS,
            publication_number="EP2000000A1",
            title="Prior-art fixture patent",
            source_url=(
                "https://ops.epo.org/3.2/rest-services/"
                "published-data/publication/docdb/EP.2000000.A1/abstract"
            ),
            metadata_verification_state=PatentMetadataVerificationState.VERIFIED,
            publication_date=date(2025, 1, 15),
        ),
        abstract_text=abstract,
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
                records=(bibliographic,),
            ),
            verified_records=(verified,),
        ),
        attempted_queries=(query,),
    )


def evidence_runtime(
    evaluator: ControlledEvidenceRelevanceEvaluator,
) -> PatentTechnicalRelevanceEvidenceRuntime:
    return PatentTechnicalRelevanceEvidenceRuntime(
        evidence_extractor=PipelineEvidenceExtractorAdapter(
            SemanticResearchEvidenceExtractor(
                question=("Which passage is technically related to English claim one?"),
                objective="Select traceable prior-art technical evidence.",
                paragraph_extractor=ParagraphEvidenceExtractor(
                    maximum_evidence=3,
                    minimum_characters=20,
                ),
                shortlister=EmbeddingSemanticEvidenceShortlister(
                    embedding_provider=ControlledEmbeddingProvider(),
                    maximum_candidates=3,
                ),
                reranker=SemanticEvidenceReranker(
                    evaluator=evaluator,
                    budget=ExecutionBudget(
                        max_attempts=3,
                        max_recorded_tokens=1000,
                        max_elapsed_seconds=10.0,
                    ),
                ),
                maximum_evidence=1,
            )
        )
    )


def test_offline_fixture_integrates_claims_evidence_and_mapping() -> None:
    raw = EpoOpsClaimsRetriever(
        client=FakeClaimsClient("claims_b1_multilingual.xml")  # type: ignore[arg-type]
    ).retrieve(target_bibliographic_record())
    parsed = parse_epo_ops_claims_record(raw)

    decomposition_result = PatentClaimDecompositionRuntime(
        claim_decomposer=EchoClaimDecomposer(),
    ).decompose(
        PatentClaimsRuntimeResult(
            execution=None,  # type: ignore[arg-type]
            claim_documents=(parsed,),
        )
    )

    evidence_relevance = ControlledEvidenceRelevanceEvaluator(calls=[])
    evidence_result = evidence_runtime(evidence_relevance).extract(
        prior_art_execution(),
        request_id="step4d-offline-integration",
    )

    element_evaluator = ControlledElementEvidenceEvaluator(calls=[])
    mapping_result = PatentPriorArtEvidenceMappingRuntime(
        evaluator=element_evaluator,
    ).map(
        decomposition_result=decomposition_result,
        evidence_result=evidence_result,
    )

    assert len(mapping_result.mapping_documents) == 1
    mapped_document = mapping_result.mapping_documents[0]

    assert mapped_document.publication_number == "EP1000000B1"
    assert mapped_document.publication_docdb == "EP.1000000.B1"
    assert tuple(claim_set.language for claim_set in mapped_document.claim_sets) == (
        "DE",
        "FR",
        "EN",
    )
    assert tuple(len(claim_set.claims) for claim_set in mapped_document.claim_sets) == (
        2,
        2,
        2,
    )

    assert len(evidence_result.evidence_set.evidence) == 1
    selected_evidence = evidence_result.evidence_set.evidence[0]
    assert "English claim one" in selected_evidence.excerpt
    assert (
        evidence_result.document_set.documents[0].content[
            selected_evidence.start_character : selected_evidence.end_character
        ]
        == selected_evidence.excerpt
    )

    english_claim_one = mapped_document.claim_sets[2].claims[0]
    assert english_claim_one.original_claim_text == "English claim one."
    assert english_claim_one.elements[0].element_text == "English claim one."

    mapped_evidence = english_claim_one.elements[0].evaluations[0]
    assert mapped_evidence.publication_number == "EP2000000A1"
    assert mapped_evidence.evidence_id == selected_evidence.evidence_id
    assert mapped_evidence.source_id == selected_evidence.source_id
    assert mapped_evidence.document_id == selected_evidence.document_id
    assert mapped_evidence.excerpt == selected_evidence.excerpt
    assert mapped_evidence.start_character == selected_evidence.start_character
    assert mapped_evidence.end_character == selected_evidence.end_character
    assert (
        mapped_evidence.judgment.relevance_level
        is EvidenceRelevanceLevel.DIRECTLY_RELEVANT
    )

    german_claim_one = mapped_document.claim_sets[0].claims[0]
    assert (
        german_claim_one.elements[0].evaluations[0].judgment.relevance_level
        is EvidenceRelevanceLevel.IRRELEVANT
    )

    assert len(evidence_relevance.calls) >= 1
    assert len(element_evaluator.calls) == 6

    chart_result = PatentClaimChartRuntime().build(mapping_result)

    assert chart_result.mapping_result is mapping_result
    assert len(chart_result.charts) == 1

    chart = chart_result.charts[0]
    assert chart.target_publication_number == "EP1000000B1"
    assert chart.target_publication_docdb == "EP.1000000.B1"
    assert tuple(claim_set.language for claim_set in chart.claim_sets) == (
        "DE",
        "FR",
        "EN",
    )
    assert tuple(len(claim_set.claims) for claim_set in chart.claim_sets) == (2, 2, 2)
    assert tuple(
        row.row_number
        for claim_set in chart.claim_sets
        for chart_claim in claim_set.claims
        for row in chart_claim.rows
    ) == (1, 2, 3, 4, 5, 6)

    chart_english_claim_one = chart.claim_sets[2].claims[0]
    assert chart_english_claim_one.original_claim_text == "English claim one."
    assert chart_english_claim_one.rows[0].element_number == 1
    assert chart_english_claim_one.rows[0].element_text == "English claim one."
    assert chart_english_claim_one.rows[0].row_number == 5

    chart_evidence = chart_english_claim_one.rows[0].evaluations[0]
    assert chart_evidence.publication_number == "EP2000000A1"
    assert chart_evidence.evidence_id == selected_evidence.evidence_id
    assert chart_evidence.source_id == selected_evidence.source_id
    assert chart_evidence.document_id == selected_evidence.document_id
    assert chart_evidence.excerpt == selected_evidence.excerpt
    assert chart_evidence.start_character == selected_evidence.start_character
    assert chart_evidence.end_character == selected_evidence.end_character
    assert (
        chart_evidence.judgment.relevance_level
        is EvidenceRelevanceLevel.DIRECTLY_RELEVANT
    )

    chart_german_claim_one = chart.claim_sets[0].claims[0]
    assert chart_german_claim_one.rows[0].row_number == 1
    assert (
        chart_german_claim_one.rows[0].evaluations[0].judgment.relevance_level
        is EvidenceRelevanceLevel.IRRELEVANT
    )


def test_offline_mapping_result_contains_no_legal_conclusion_fields() -> None:
    raw = EpoOpsClaimsRetriever(
        client=FakeClaimsClient("claims_b1_multilingual.xml")  # type: ignore[arg-type]
    ).retrieve(target_bibliographic_record())
    parsed = parse_epo_ops_claims_record(raw)

    decomposition_result = PatentClaimDecompositionRuntime(
        claim_decomposer=EchoClaimDecomposer(),
    ).decompose(
        PatentClaimsRuntimeResult(
            execution=None,  # type: ignore[arg-type]
            claim_documents=(parsed,),
        )
    )

    evidence_result = evidence_runtime(
        ControlledEvidenceRelevanceEvaluator(calls=[])
    ).extract(
        prior_art_execution(),
        request_id="step4d-offline-nonlegal",
    )

    mapping = PatentPriorArtEvidenceMappingRuntime(
        evaluator=ControlledElementEvidenceEvaluator(calls=[]),
    ).map(
        decomposition_result=decomposition_result,
        evidence_result=evidence_result,
    )

    chart = PatentClaimChartRuntime().build(mapping).charts[0]
    mapping_payload = mapping.mapping_documents[0].model_dump()
    chart_payload = chart.model_dump()

    forbidden_keys = {
        "novelty",
        "anticipation",
        "obviousness",
        "inventive_step",
        "invalidity",
        "infringement",
        "freedom_to_operate",
        "legal_status",
        "claim_scope",
        "essentiality",
        "depends_on",
    }

    def collect_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            keys = {str(key).casefold() for key in value}
            for nested in value.values():
                keys.update(collect_keys(nested))
            return keys

        if isinstance(value, (list, tuple)):
            keys: set[str] = set()
            for nested in value:
                keys.update(collect_keys(nested))
            return keys

        return set()

    assert forbidden_keys.isdisjoint(collect_keys(mapping_payload))
    assert forbidden_keys.isdisjoint(collect_keys(chart_payload))

    # Safety language may name legal concepts specifically to disclaim them.
    assert "does not determine novelty" in chart.scope_notice.casefold()
