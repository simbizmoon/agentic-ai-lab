"""Deterministic Markdown and JSON formatting for scholarly exact evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.schemas.scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflowResult,
)
from app.schemas.scholarly_work import ScholarlyIdentifierType


@dataclass(frozen=True)
class ScholarlyEvidenceFormats:
    """Two deterministic in-memory representations of one workflow result."""

    markdown: str
    json_text: str


class DeterministicScholarlyEvidenceFormatter:
    """Render an existing scholarly result without adding judgments."""

    def format(
        self,
        result: BoundedScholarlyEvidenceWorkflowResult,
    ) -> ScholarlyEvidenceFormats:
        if not isinstance(result, BoundedScholarlyEvidenceWorkflowResult):
            raise TypeError("result must be a BoundedScholarlyEvidenceWorkflowResult")
        return ScholarlyEvidenceFormats(
            markdown=self._markdown(result),
            json_text=(
                json.dumps(
                    result.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            ),
        )

    def _markdown(self, result: BoundedScholarlyEvidenceWorkflowResult) -> str:
        artifact = result.adaptation.document_adaptation.artifact
        provider_result = artifact.result
        document_adaptation = result.adaptation.document_adaptation
        evidence = result.adaptation.evidence_set.evidence
        documents_by_work = {
            document.metadata["scholarly_work_id"]: document
            for document in document_adaptation.document_set.documents
        }
        evidence_by_document = {item.document_id: item for item in evidence}

        lines = [
            "# Scholarly Exact Abstract Evidence",
            "",
            f"- Request ID: {result.request.request_id}",
            f"- Task ID: {result.task_id}",
            f"- Provider: {provider_result.provider}",
            f"- Provider status: {provider_result.status.value}",
            f"- Query: {result.request.query}",
            f"- Maximum results: {result.request.maximum_results}",
            (
                "- Provider requests: "
                f"{result.actual_provider_requests}/"
                f"{result.maximum_provider_requests}"
            ),
            f"- Records received: {result.records_received}",
            f"- Works accepted: {result.works_accepted}",
            f"- Records rejected: {result.records_rejected}",
            f"- Abstract documents: {result.abstract_documents_created}",
            (
                "- Works omitted without abstract: "
                f"{result.works_omitted_without_abstract}"
            ),
            (
                "- Whole-abstract evidence items: "
                f"{result.whole_abstract_evidence_created}"
            ),
            f"- Duplicate identity groups: {result.duplicate_identity_groups}",
            "",
            "## Accepted Works",
            "",
        ]

        if not provider_result.works:
            lines.extend(["None.", ""])
        for work in provider_result.works:
            identifiers = {
                item.identifier_type: item.normalized_value for item in work.identifiers
            }
            lines.extend(
                [
                    f"### {work.title}",
                    "",
                    f"- Work ID: {work.work_id}",
                    f"- Work type: {work.work_type.value}",
                    f"- Version: {work.version_type.value}",
                    (
                        "- DOI: "
                        + identifiers.get(ScholarlyIdentifierType.DOI, "ABSENT")
                    ),
                    f"- Access state: {work.access.state.value}",
                    f"- License: {work.access.license or 'ABSENT'}",
                    f"- Integrity status: {work.integrity_status.value}",
                    f"- Provider record ID: {work.provenance.provider_record_id}",
                    f"- Provider request URL: {work.provenance.request_url}",
                    f"- Response SHA-256: {work.provenance.response_sha256}",
                ]
            )
            document = documents_by_work.get(work.work_id)
            if document is None:
                lines.extend(["- Abstract evidence: OMITTED (abstract absent)", ""])
                continue
            item = evidence_by_document[document.document_id]
            lines.extend(
                [
                    f"- Evidence ID: {item.evidence_id}",
                    f"- Source ID: {item.source_id}",
                    f"- Document ID: {item.document_id}",
                    (f"- Character range: {item.start_character}:{item.end_character}"),
                    "",
                    "Exact provider-supplied abstract:",
                    "",
                ]
            )
            self._append_exact_text(lines, item.excerpt)

        lines.extend(["## Rejected Provider Records", ""])
        if not provider_result.record_failures:
            lines.extend(["None.", ""])
        for failure in provider_result.record_failures:
            lines.extend(
                [
                    f"### Provider position {failure.provider_position}",
                    "",
                    f"- Provider record ID: {failure.provider_record_id or 'ABSENT'}",
                    f"- Error type: {failure.error_type}",
                    f"- Message: {failure.message}",
                    "",
                ]
            )

        lines.extend(["## Duplicate Identity Groups", ""])
        if not artifact.duplicate_groups:
            lines.extend(["None.", ""])
        for group in artifact.duplicate_groups:
            lines.extend(
                [
                    f"### {group.group_id}",
                    "",
                    "- Member work IDs: " + ", ".join(group.member_work_ids),
                    "- Shared identity keys: " + ", ".join(group.shared_identity_keys),
                    "",
                ]
            )

        lines.extend(
            [
                "## Scope Notice",
                "",
                (
                    "This artifact preserves provider-supplied metadata and exact "
                    "whole-abstract evidence. It does not assess semantic relevance, "
                    "paper quality, citation impact, systematic-review completeness, "
                    "or permission to obtain or use full text."
                ),
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _append_exact_text(lines: list[str], text: str) -> None:
        longest_run = 0
        current_run = 0
        for character in text:
            if character == "`":
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 0
        fence = "`" * max(3, longest_run + 1)
        lines.extend([fence, text, fence, ""])
