"""Final integrity guardrail for AIRA research results."""

from __future__ import annotations

from app.schemas.research_pipeline import (
    SingleResearchPipelineResult,
)


class ResearchResultGuardrail:
    """Reject incomplete or untraceable research results."""

    def validate(
        self,
        result: SingleResearchPipelineResult,
        *,
        execution_id: str,
    ) -> None:
        """Validate identity, claims, citations, and traceability."""

        normalized_execution_id = execution_id.strip()

        if not normalized_execution_id:
            raise ValueError("execution_id must not be blank")

        request_id = result.workspace.request.request_id

        if request_id != normalized_execution_id:
            raise ValueError(
                "result request_id must match execution_id"
            )

        if result.report.request_id != normalized_execution_id:
            raise ValueError(
                "report request_id must match execution_id"
            )

        if not result.workspace.claim_set.claims:
            raise ValueError(
                "research result must contain at least one claim"
            )

        if not result.report.citations:
            raise ValueError(
                "research result must contain at least one citation"
            )

        evidence_by_id = {
            item.evidence_id: item
            for item in result.workspace.evidence_set.evidence
        }
        cited_evidence_ids = {
            citation.evidence_id
            for citation in result.report.citations
        }

        if not cited_evidence_ids.issubset(evidence_by_id):
            raise ValueError(
                "report citations must reference existing evidence"
            )

        document_by_id = {
            item.document_id: item
            for item
            in result.workspace.evidence_set.document_set.documents
        }

        for citation in result.report.citations:
            evidence = evidence_by_id[citation.evidence_id]

            if citation.source_id != evidence.source_id:
                raise ValueError(
                    "report citation source_id must match "
                    "evidence source_id"
                )

            if citation.document_id != evidence.document_id:
                raise ValueError(
                    "report citation document_id must match "
                    "evidence document_id"
                )

            if citation.excerpt != evidence.excerpt:
                raise ValueError(
                    "report citation excerpt must match "
                    "evidence excerpt"
                )

            document = document_by_id.get(citation.document_id)

            if document is None:
                raise ValueError(
                    "report citations must reference "
                    "existing documents"
                )

            if citation.source_id != document.candidate.source_id:
                raise ValueError(
                    "report citation source_id must match "
                    "document source_id"
                )

            if citation.url != document.candidate.url:
                raise ValueError(
                    "report citation url must match document url"
                )

            if citation.title != document.candidate.title:
                raise ValueError(
                    "report citation title must match document title"
                )

        source_ids = {
            candidate.source_id
            for candidate
            in result.workspace.candidate_set.candidates
        }
        cited_source_ids = {
            citation.source_id
            for citation in result.report.citations
        }

        if not cited_source_ids.issubset(source_ids):
            raise ValueError(
                "report citations must reference existing sources"
            )

        if result.report.claim_count != len(
            result.workspace.claim_set.claims
        ):
            raise ValueError(
                "report claim count must match workspace claims"
            )

        if result.report.citation_count != len(
            result.report.citations
        ):
            raise ValueError(
                "report citation count must match report citations"
            )
