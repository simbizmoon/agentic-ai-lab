"""Stage 9 adapter for exact EPO patent-claim evidence acquisition."""

from __future__ import annotations

import re
from typing import Protocol

from app.research.patent_claim_parser import parse_epo_ops_claims_record
from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
)
from app.research.stage9_development_acquisition_router import (
    Stage9ChannelAcquisitionResult,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsDocumentIdType,
)
from app.schemas.epo_ops_claims import EpoOpsClaimsRecord
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateStatus,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionChannel,
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequest,
)
from app.schemas.stage9_evaluation_manifest import Stage9EvaluationDomain

_PUBLICATION_PATTERN = re.compile(r"(?<![A-Z0-9])(EP[0-9]+[A-Z][0-9]?)(?![A-Z0-9])")
_CLAIM_PATTERN = re.compile(r"\bclaim\s+([1-9][0-9]*)\b", re.IGNORECASE)
_EPO_PUBLICATION_BASE = (
    "https://ops.epo.org/3.2/rest-services/published-data/publication/docdb"
)


class Stage9ExactClaimsRetriever(Protocol):
    """Existing EPO retriever boundary used by the Stage 9 adapter."""

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsClaimsRecord: ...


class Stage9PatentAcquisitionError(RuntimeError):
    """The question or provider result violated exact acquisition boundaries."""


class Stage9PatentAcquisitionAdapter:
    """Acquire one explicitly named EPO claim without Golden evidence injection."""

    def __init__(self, *, claims_retriever: Stage9ExactClaimsRetriever) -> None:
        self._claims_retriever = claims_retriever

    def acquire(
        self,
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
    ) -> Stage9ChannelAcquisitionResult:
        if channel is not Stage9AcquisitionChannel.EPO_PATENT:
            raise ValueError("patent adapter only accepts epo_patent")
        if request.domain is not Stage9EvaluationDomain.PATENT:
            raise ValueError("patent adapter requires the patent domain")

        publication_number, claim_number = self._question_identity(request.question)
        bibliographic = self._bibliographic(publication_number)
        raw_record = self._claims_retriever.retrieve(bibliographic)
        document = parse_epo_ops_claims_record(raw_record)
        if (
            normalize_patent_publication_number(document.publication_number)
            != publication_number
            or document.publication_docdb != bibliographic.publication_docdb
        ):
            raise Stage9PatentAcquisitionError(
                "EPO claims identity did not match the question"
            )

        english_sets = tuple(
            item for item in document.claim_sets if item.language.upper() == "EN"
        )
        if len(english_sets) != 1:
            raise Stage9PatentAcquisitionError(
                "EPO response must contain exactly one English claim set"
            )
        claims = tuple(
            item for item in english_sets[0].claims if item.claim_number == claim_number
        )
        if len(claims) != 1:
            return self._no_evidence(request=request, channel=channel)

        claim = claims[0]
        task_id = f"{request.request_id}-epo-patent"
        source_id = f"epo-{publication_number}"
        document_id = f"epo-{publication_number}-claim-{claim_number}"
        candidate = ResearchSourceCandidate(
            source_id=source_id,
            request_id=request.request_id,
            task_id=task_id,
            query_id=f"{request.request_id}-explicit-publication",
            title=f"{publication_number} claim {claim_number}",
            url=document.source_endpoint,
            source_type=ResearchSourceType.GOVERNMENT,
            snippet=claim.text,
            publisher="European Patent Office",
            rank=1,
            status=ResearchSourceCandidateStatus.READ,
            metadata={
                "publication_number": publication_number,
                "publication_docdb": document.publication_docdb,
                "claim_number": str(claim_number),
                "provider_position": str(claim.provider_position),
                "golden_evidence_supplied": "false",
            },
        )
        research_document = ResearchSourceDocument(
            document_id=document_id,
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=ResearchSourceContentType.TEXT,
            content=claim.text,
            language="en",
            word_count=len(claim.text.split()),
            character_count=len(claim.text),
            reader="stage9-exact-epo-claim-adapter-v1",
            metadata={
                "publication_docdb": document.publication_docdb,
                "claim_number": str(claim_number),
                "provider_position": str(claim.provider_position),
            },
        )
        evidence = ResearchEvidence(
            evidence_id=f"{document_id}-exact-evidence",
            request_id=request.request_id,
            task_id=task_id,
            source_id=source_id,
            document_id=document_id,
            excerpt=claim.text,
            start_character=0,
            end_character=len(claim.text),
            evidence_type=ResearchEvidenceType.OTHER,
            stance=ResearchEvidenceStance.NEUTRAL,
            relevance_score=1.0,
            confidence_score=1.0,
            rationale="Exact claim explicitly identified in the evaluation question.",
            metadata={
                "publication_number": publication_number,
                "claim_number": str(claim_number),
                "provider_position": str(claim.provider_position),
                "claim_construction_performed": "false",
                "legal_conclusion_performed": "false",
            },
        )
        evidence_set = ResearchEvidenceSet(
            request_id=request.request_id,
            document_set=ResearchSourceDocumentSet(
                request_id=request.request_id,
                documents=[research_document],
            ),
            evidence=[evidence],
        )
        return Stage9ChannelAcquisitionResult(
            request_id=request.request_id,
            channel=channel,
            status=Stage9AcquisitionStatus.EVIDENCE_AVAILABLE,
            evidence_set=evidence_set,
            provider_requests=1,
            external_requests=1,
        )

    @staticmethod
    def _question_identity(question: str) -> tuple[str, int]:
        publications = tuple(
            dict.fromkeys(_PUBLICATION_PATTERN.findall(question.upper()))
        )
        claims = tuple(
            dict.fromkeys(int(value) for value in _CLAIM_PATTERN.findall(question))
        )
        if len(publications) != 1 or len(claims) != 1:
            raise Stage9PatentAcquisitionError(
                "question must name exactly one EP publication and one claim number"
            )
        publication = normalize_patent_publication_number(publications[0])
        if not publication.startswith("EP"):
            raise Stage9PatentAcquisitionError(
                "only an exact EP publication is accepted"
            )
        return publication, claims[0]

    @staticmethod
    def _bibliographic(publication_number: str) -> EpoOpsBibliographicRecord:
        match = re.fullmatch(r"EP([0-9]+)([A-Z][0-9]?)", publication_number)
        if match is None:
            raise Stage9PatentAcquisitionError(
                "EP publication must include an exact kind code"
            )
        docdb = f"EP.{match.group(1)}.{match.group(2)}"
        return EpoOpsBibliographicRecord(
            publication_number=publication_number,
            publication_docdb=docdb,
            title=f"Exact EPO publication {publication_number}",
            publication_date=None,
            source_endpoint=f"{_EPO_PUBLICATION_BASE}/{docdb}",
            document_id_type=EpoOpsDocumentIdType.DOCDB,
            application_number=None,
            title_language="en",
        )

    @staticmethod
    def _no_evidence(
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
    ) -> Stage9ChannelAcquisitionResult:
        evidence_set = ResearchEvidenceSet(
            request_id=request.request_id,
            document_set=ResearchSourceDocumentSet(
                request_id=request.request_id,
                documents=[],
            ),
            evidence=[],
        )
        return Stage9ChannelAcquisitionResult(
            request_id=request.request_id,
            channel=channel,
            status=Stage9AcquisitionStatus.NO_EVIDENCE,
            evidence_set=evidence_set,
            provider_requests=1,
            external_requests=1,
        )
