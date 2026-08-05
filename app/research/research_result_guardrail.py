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

        evidence_ids = {
            item.evidence_id
            for item in result.workspace.evidence_set.evidence
        }
        cited_evidence_ids = {
            citation.evidence_id
            for citation in result.report.citations
        }

        if not cited_evidence_ids.issubset(evidence_ids):
            raise ValueError(
                "report citations must reference existing evidence"
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
