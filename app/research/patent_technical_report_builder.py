"""Deterministic patent technical-relevance report construction."""

from __future__ import annotations

from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceResult,
)
from app.schemas.evidence_relevance_judgment import EvidenceRelevanceLevel
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
    PatentSourceFamily,
)
from app.schemas.patent_technical_report import (
    PatentTechnicalEvidenceReference,
    PatentTechnicalFinding,
    PatentTechnicalResearchReport,
)
from app.schemas.research_evidence import ResearchEvidence
from app.schemas.research_source_document import ResearchSourceDocument

PATENT_TECHNICAL_REPORT_SCOPE_NOTICE = (
    "This report summarizes bounded technical relevance only. "
    "It does not determine novelty, anticipation, obviousness, invalidity, "
    "infringement, freedom to operate, or current legal status."
)


class DeterministicPatentTechnicalReportBuilder:
    """Build a traceable report without generating new technical claims."""

    def __init__(
        self,
        *,
        name: str = "deterministic-patent-technical-report-builder",
    ) -> None:
        if not name.strip():
            raise ValueError("name must not be blank")
        self._name = name.strip()

    @property
    def name(self) -> str:
        return self._name

    def build(
        self,
        *,
        request: PatentResearchRequest,
        relevance: PatentTechnicalRelevanceEvidenceResult,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentTechnicalResearchReport:
        cleaned_request_id = request_id.strip()
        cleaned_task_id = task_id.strip()
        if not cleaned_request_id:
            raise ValueError("request_id must not be blank")
        if not cleaned_task_id:
            raise ValueError("task_id must not be blank")

        if relevance.execution.collection.request != request:
            raise RuntimeError(
                "patent relevance execution was not bound to the exact request"
            )

        document_set = relevance.document_set
        evidence_set = relevance.evidence_set

        if document_set.request_id != cleaned_request_id:
            raise RuntimeError(
                "patent document set request_id did not match report request_id"
            )
        if evidence_set.request_id != cleaned_request_id:
            raise RuntimeError(
                "patent evidence set request_id did not match report request_id"
            )
        if evidence_set.document_set != document_set:
            raise RuntimeError(
                "patent evidence set did not preserve the report document set"
            )

        document_by_id = {
            document.document_id: document for document in document_set.documents
        }
        record_by_publication = {
            record.metadata.publication_number: record
            for record in relevance.execution.collection.verified_records
        }

        findings: list[PatentTechnicalFinding] = []
        unevaluated_evidence_ids: list[str] = []

        for evidence in evidence_set.evidence:
            if evidence.task_id != cleaned_task_id:
                raise RuntimeError(
                    "patent evidence task_id did not match report task_id"
                )

            semantic_level = evidence.metadata.get("semantic_relevance_level")
            semantic_evaluated = evidence.metadata.get("semantic_evaluated")

            if semantic_level == "unevaluated":
                if semantic_evaluated != "false":
                    raise RuntimeError(
                        "unevaluated patent evidence must be marked "
                        "semantic_evaluated=false"
                    )
                unevaluated_evidence_ids.append(evidence.evidence_id)
                continue

            try:
                relevance_level = EvidenceRelevanceLevel(semantic_level or "")
            except ValueError as exc:
                raise RuntimeError(
                    "patent evidence has an unknown semantic relevance level"
                ) from exc

            if relevance_level is EvidenceRelevanceLevel.IRRELEVANT:
                raise RuntimeError(
                    "irrelevant evidence must not reach the patent report builder"
                )

            if semantic_evaluated != "true":
                raise RuntimeError(
                    "relevant patent evidence must have a completed semantic judgment"
                )

            document = document_by_id.get(evidence.document_id)
            if document is None:
                raise RuntimeError("patent evidence referenced an unknown document")

            findings.append(
                self._finding(
                    evidence=evidence,
                    document=document,
                    record_by_publication=record_by_publication,
                    position=len(findings) + 1,
                    request_id=cleaned_request_id,
                    relevance_level=relevance_level,
                )
            )

        execution = relevance.execution
        return PatentTechnicalResearchReport(
            report_id=(f"{cleaned_request_id}-patent-technical-report"),
            request_id=cleaned_request_id,
            task_id=cleaned_task_id,
            question=request.question,
            objective=request.objective,
            prior_art_cutoff_date=request.prior_art_cutoff_date,
            title=(f"Patent Technical Relevance Report: {request.question.strip()}"),
            findings=findings,
            unevaluated_evidence_ids=unevaluated_evidence_ids,
            finding_count=len(findings),
            source_count=len({finding.evidence.source_id for finding in findings}),
            document_count=len(document_set.documents),
            verified_record_count=len(execution.collection.verified_records),
            input_evidence_count=len(evidence_set.evidence),
            executed_query_purpose=execution.query.purpose.value,
            executed_cql=execution.query.cql_query,
            scope_notice=PATENT_TECHNICAL_REPORT_SCOPE_NOTICE,
            builder=self._name,
        )

    @staticmethod
    def _finding(
        *,
        evidence: ResearchEvidence,
        document: ResearchSourceDocument,
        record_by_publication: dict[str, object],
        position: int,
        request_id: str,
        relevance_level: EvidenceRelevanceLevel,
    ) -> PatentTechnicalFinding:
        candidate = document.candidate
        publication_number = candidate.metadata.get("patent_publication_number")
        if not publication_number:
            raise RuntimeError("patent document is missing publication number metadata")

        record = record_by_publication.get(publication_number)
        if record is None:
            raise RuntimeError(
                "patent document publication was not present in verified records"
            )

        metadata = record.metadata
        expected = {
            "patent_source_family": metadata.source_family.value,
            "patent_publication_number": metadata.publication_number,
            "patent_verification_state": (metadata.metadata_verification_state.value),
        }
        for key, value in expected.items():
            if candidate.metadata.get(key) != value:
                raise RuntimeError(
                    f"patent document metadata did not match verified record: {key}"
                )

        if candidate.title != metadata.title:
            raise RuntimeError("patent document title did not match verified record")
        if candidate.url != metadata.source_url:
            raise RuntimeError("patent document URL did not match verified record")
        if evidence.rationale is None:
            raise RuntimeError("relevant patent evidence must contain a rationale")

        return PatentTechnicalFinding(
            finding_id=(f"{request_id}-patent-finding-{position:03d}"),
            publication_number=metadata.publication_number,
            title=metadata.title,
            source_url=metadata.source_url,
            publication_date=metadata.publication_date,
            source_family=PatentSourceFamily(metadata.source_family.value),
            metadata_verification_state=(
                PatentMetadataVerificationState(
                    metadata.metadata_verification_state.value
                )
            ),
            relevance_level=relevance_level,
            relevance_score=evidence.relevance_score,
            relevance_rationale=evidence.rationale,
            evidence=PatentTechnicalEvidenceReference(
                evidence_id=evidence.evidence_id,
                source_id=evidence.source_id,
                document_id=evidence.document_id,
                excerpt=evidence.excerpt,
                start_character=evidence.start_character,
                end_character=evidence.end_character,
            ),
            abstract_language=record.abstract_language,
        )
