"""Companion runtime for claim acquisition after verified patent execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.research.patent_claim_parser import parse_epo_ops_claims_record
from app.research.patent_publication_identity import normalize_patent_publication_number
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.schemas.epo_ops_bibliographic import EpoOpsBibliographicRecord
from app.schemas.epo_ops_claims import EpoOpsClaimsRecord
from app.schemas.patent_claims import PatentClaimsDocument


class PatentClaimsRetrieverProtocol(Protocol):
    """Retrieve raw claims for one exact bibliographic publication."""

    def retrieve(
        self,
        record: EpoOpsBibliographicRecord,
    ) -> EpoOpsClaimsRecord: ...


class PatentClaimsParserProtocol(Protocol):
    """Parse one raw provider claims record."""

    def __call__(
        self,
        record: EpoOpsClaimsRecord,
    ) -> PatentClaimsDocument: ...


@dataclass(frozen=True)
class PatentClaimsRuntimeResult:
    """Existing patent execution plus separately acquired parsed claims."""

    execution: PatentResearchPlanExecutionResult
    claim_documents: tuple[PatentClaimsDocument, ...]


class PatentClaimsRuntime:
    """Acquire claims only for already verified patent publications."""

    def __init__(
        self,
        *,
        claims_retriever: PatentClaimsRetrieverProtocol,
        claims_parser: PatentClaimsParserProtocol = parse_epo_ops_claims_record,
    ) -> None:
        self._claims_retriever = claims_retriever
        self._claims_parser = claims_parser

    def enrich(
        self,
        execution: PatentResearchPlanExecutionResult,
    ) -> PatentClaimsRuntimeResult:
        """Retrieve and parse claims without changing search or fallback semantics."""

        verified = execution.collection.verified_records
        if not verified:
            return PatentClaimsRuntimeResult(
                execution=execution,
                claim_documents=(),
            )

        selected = execution.collection.search_result.records[: len(verified)]
        if len(selected) != len(verified):
            raise RuntimeError(
                "verified patent records were not backed by selected bibliographic records"
            )

        claim_documents: list[PatentClaimsDocument] = []
        for bibliographic, verified_record in zip(selected, verified, strict=True):
            expected_identity = normalize_patent_publication_number(
                verified_record.metadata.publication_number
            )
            actual_identity = normalize_patent_publication_number(
                bibliographic.publication_number
            )
            if actual_identity != expected_identity:
                raise RuntimeError(
                    "verified patent record identity drifted from selected bibliographic record"
                )

            raw_claims = self._claims_retriever.retrieve(bibliographic)
            parsed = self._claims_parser(raw_claims)

            parsed_identity = normalize_patent_publication_number(
                parsed.publication_number
            )
            if parsed_identity != expected_identity:
                raise RuntimeError(
                    "parsed patent claims identity drifted from verified patent record"
                )

            if parsed.publication_docdb != bibliographic.publication_docdb:
                raise RuntimeError(
                    "parsed patent claims DOCDB identity drifted from selected bibliographic record"
                )

            claim_documents.append(parsed)

        return PatentClaimsRuntimeResult(
            execution=execution,
            claim_documents=tuple(claim_documents),
        )
