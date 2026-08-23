"""Exact target-claim and comparison-abstract acquisition for patent comparison."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.research.patent_claim_parser import parse_epo_ops_claims_record
from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
)
from app.research.patent_research_document_adapter import PatentResearchDocumentAdapter
from app.research.patent_research_plan_executor import PatentResearchPlanExecutionResult
from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceResult,
)
from app.schemas.epo_ops_abstract import (
    EpoOpsAbstractRecord,
    EpoOpsVerifiedPatentRecord,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsDocumentIdType,
    EpoOpsSearchRequest,
)
from app.schemas.epo_ops_claims import EpoOpsClaimsRecord
from app.schemas.patent_claims import PatentClaim, PatentClaimsDocument
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)
from app.schemas.patent_research_collection_result import PatentResearchCollectionResult
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import PatentSearchQuery, PatentSearchQueryPurpose
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

_EPO_PUBLICATION_PATTERN = re.compile(r"EP([0-9]+)([A-Z][0-9]?)", re.ASCII)
_EPO_PUBLICATION_BASE = (
    "https://ops.epo.org/3.2/rest-services/published-data/publication/docdb"
)


class ExactClaimsRetrieverProtocol(Protocol):
    """Retrieve claims for one exact bibliographic publication."""

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsClaimsRecord: ...


class ExactAbstractRetrieverProtocol(Protocol):
    """Retrieve an abstract for one exact bibliographic publication."""

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsAbstractRecord: ...


@dataclass(frozen=True)
class PatentMultiPatentComparisonAcquisitionResult:
    """Exact selected target claim plus ordered whole-abstract evidence."""

    request: PatentMultiPatentComparisonRequest
    target_claims_document: PatentClaimsDocument
    selected_target_claim: PatentClaim
    comparison_execution: PatentResearchPlanExecutionResult
    evidence_result: PatentTechnicalRelevanceEvidenceResult


class PatentMultiPatentComparisonAcquisition:
    """Acquire explicit EPO inputs without search, inference, or legal analysis."""

    def __init__(
        self,
        *,
        claims_retriever: ExactClaimsRetrieverProtocol,
        abstract_retriever: ExactAbstractRetrieverProtocol,
        document_adapter: PatentResearchDocumentAdapter | None = None,
    ) -> None:
        self._claims_retriever = claims_retriever
        self._abstract_retriever = abstract_retriever
        self._document_adapter = document_adapter or PatentResearchDocumentAdapter()

    def acquire(
        self,
        request: PatentMultiPatentComparisonRequest,
        *,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentMultiPatentComparisonAcquisitionResult:
        if not isinstance(request, PatentMultiPatentComparisonRequest):
            raise TypeError("request must be a PatentMultiPatentComparisonRequest")
        cleaned_request_id = request_id.strip()
        cleaned_task_id = task_id.strip()
        if not cleaned_request_id:
            raise ValueError("request_id must not be blank")
        if not cleaned_task_id:
            raise ValueError("task_id must not be blank")

        target_record = self._bibliographic(request.target_publication_number)
        raw_claims = self._claims_retriever.retrieve(target_record)
        target_document = parse_epo_ops_claims_record(raw_claims)
        self._validate_identity(
            expected=target_record,
            publication_number=target_document.publication_number,
            publication_docdb=target_document.publication_docdb,
            artifact="target claims",
        )
        selected_claim = self._select_claim(request, target_document)

        comparison_records = tuple(
            self._bibliographic(publication_number)
            for publication_number in request.comparison_publication_numbers
        )
        abstracts = tuple(
            self._abstract_retriever.retrieve(record) for record in comparison_records
        )
        for record, abstract in zip(comparison_records, abstracts, strict=True):
            self._validate_identity(
                expected=record,
                publication_number=abstract.publication_number,
                publication_docdb=abstract.publication_docdb,
                artifact="comparison abstract",
            )

        execution = self._comparison_execution(
            request,
            comparison_records,
            abstracts,
        )
        document_set = self._document_adapter.adapt(
            execution,
            request_id=cleaned_request_id,
            task_id=cleaned_task_id,
        )
        evidence = [
            ResearchEvidence(
                evidence_id=f"patent-comparison-evidence-{index:03d}",
                request_id=cleaned_request_id,
                task_id=cleaned_task_id,
                source_id=document.candidate.source_id,
                document_id=document.document_id,
                excerpt=document.content,
                start_character=0,
                end_character=len(document.content),
                evidence_type=ResearchEvidenceType.OTHER,
                stance=ResearchEvidenceStance.NEUTRAL,
                relevance_score=1.0,
                confidence_score=1.0,
                rationale=(
                    "Exact verified EPO abstract selected by explicit publication identity."
                ),
                metadata={"patent_comparison_acquisition": "whole_abstract"},
            )
            for index, document in enumerate(document_set.documents, start=1)
        ]
        evidence_set = ResearchEvidenceSet(
            request_id=cleaned_request_id,
            document_set=document_set,
            evidence=evidence,
        )
        evidence_result = PatentTechnicalRelevanceEvidenceResult(
            execution=execution,
            document_set=document_set,
            evidence_set=evidence_set,
        )
        return PatentMultiPatentComparisonAcquisitionResult(
            request=request,
            target_claims_document=target_document,
            selected_target_claim=selected_claim,
            comparison_execution=execution,
            evidence_result=evidence_result,
        )

    @staticmethod
    def _bibliographic(publication_number: str) -> EpoOpsBibliographicRecord:
        match = _EPO_PUBLICATION_PATTERN.fullmatch(publication_number)
        if match is None:
            raise ValueError(
                "exact EPO acquisition requires an EP publication number with kind code"
            )
        publication_docdb = f"EP.{match.group(1)}.{match.group(2)}"
        return EpoOpsBibliographicRecord(
            publication_number=publication_number,
            publication_docdb=publication_docdb,
            title=f"Exact EPO publication {publication_number}",
            publication_date=None,
            source_endpoint=f"{_EPO_PUBLICATION_BASE}/{publication_docdb}",
            document_id_type=EpoOpsDocumentIdType.DOCDB,
            application_number=None,
            title_language="en",
        )

    @staticmethod
    def _validate_identity(
        *,
        expected: EpoOpsBibliographicRecord,
        publication_number: str,
        publication_docdb: str,
        artifact: str,
    ) -> None:
        if (
            normalize_patent_publication_number(publication_number)
            != expected.publication_number
            or publication_docdb != expected.publication_docdb
        ):
            raise RuntimeError(f"{artifact} identity did not match the request")

    @staticmethod
    def _select_claim(
        request: PatentMultiPatentComparisonRequest,
        document: PatentClaimsDocument,
    ) -> PatentClaim:
        matching_sets = tuple(
            claim_set
            for claim_set in document.claim_sets
            if claim_set.language.upper() == request.claim_language
        )
        if len(matching_sets) != 1:
            raise RuntimeError(
                "target claims did not contain exactly one requested language"
            )
        matches = tuple(
            claim
            for claim in matching_sets[0].claims
            if claim.claim_number == request.claim_number
        )
        if len(matches) != 1:
            raise RuntimeError(
                "target claims did not contain exactly one requested claim"
            )
        return matches[0]

    @staticmethod
    def _comparison_execution(
        request: PatentMultiPatentComparisonRequest,
        records: tuple[EpoOpsBibliographicRecord, ...],
        abstracts: tuple[EpoOpsAbstractRecord, ...],
    ) -> PatentResearchPlanExecutionResult:
        count = len(records)
        source_request = PatentResearchRequest(
            question="Compare explicit patent publications to one target claim.",
            objective="Create exact whole-abstract technical evidence.",
            maximum_search_results=count,
            maximum_sources=count,
            maximum_bytes=request.maximum_bytes,
        )
        cql_query = " or ".join(
            f'pn="{record.publication_number}"' for record in records
        )
        query = PatentSearchQuery(
            cql_query=cql_query,
            purpose=PatentSearchQueryPurpose.PRIMARY,
        )
        verified = tuple(
            EpoOpsVerifiedPatentRecord(
                metadata=PatentSourceMetadata(
                    source_family=PatentSourceFamily.EPO_OPS,
                    publication_number=record.publication_number,
                    title=record.title,
                    source_url=abstract.source_endpoint,
                    metadata_verification_state=(
                        PatentMetadataVerificationState.VERIFIED
                    ),
                    publication_date=record.publication_date,
                ),
                abstract_text=abstract.abstract_text,
                abstract_language=abstract.abstract_language,
            )
            for record, abstract in zip(records, abstracts, strict=True)
        )
        return PatentResearchPlanExecutionResult(
            query=query,
            collection=PatentResearchCollectionResult(
                request=source_request,
                search_result=EpoOpsBibliographicSearchResult(
                    request=EpoOpsSearchRequest(
                        cql_query=cql_query,
                        maximum_results=count,
                    ),
                    records=records,
                ),
                verified_records=verified,
            ),
            attempted_queries=(query,),
        )
