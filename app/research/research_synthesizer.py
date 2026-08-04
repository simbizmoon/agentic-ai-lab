"""Deterministic synthesis of research workspace claims."""

from __future__ import annotations

from app.research.research_synthesis_error import (
    ResearchSynthesisError,
)
from app.schemas.research_claim import (
    ResearchCitation,
    ResearchClaim,
)
from app.schemas.research_synthesis import (
    ResearchSynthesisCitation,
    ResearchSynthesisReport,
    ResearchSynthesisSection,
)
from app.schemas.research_workspace import (
    ResearchWorkspace,
)


class DeterministicResearchSynthesizer:
    """Build a reproducible report from workspace claims."""

    def __init__(
        self,
        *,
        name: str = "deterministic-research-synthesizer",
    ) -> None:
        if not name.strip():
            raise ValueError(
                "name must not be blank"
            )

        self._name = name

    @property
    def name(self) -> str:
        """Return the synthesizer name."""

        return self._name

    def synthesize(
        self,
        workspace: ResearchWorkspace,
    ) -> ResearchSynthesisReport:
        """Create a deterministic report from a workspace."""

        if workspace.task_graph is None:
            raise ResearchSynthesisError(
                "workspace must contain a task graph"
            )

        if workspace.claim_set is None:
            raise ResearchSynthesisError(
                "workspace must contain a claim set"
            )

        if not workspace.claim_set.claims:
            raise ResearchSynthesisError(
                "workspace must contain at least one claim"
            )

        if workspace.evidence_set is None:
            raise ResearchSynthesisError(
                "workspace must contain an evidence set"
            )

        citation_registry: dict[
            str,
            ResearchSynthesisCitation,
        ] = {}
        citation_labels: dict[str, str] = {}
        sections: list[
            ResearchSynthesisSection
        ] = []

        for task_id in workspace.task_graph.topological_order():
            task = workspace.task(task_id)

            if task is None:
                raise ResearchSynthesisError(
                    "task graph order references missing task"
                )

            claims = workspace.claims_for_task(
                task_id
            )

            if not claims:
                continue

            section = self._build_section(
                workspace=workspace,
                task_id=task_id,
                task_title=task.title,
                claims=claims,
                order=len(sections) + 1,
                citation_registry=citation_registry,
                citation_labels=citation_labels,
            )
            sections.append(section)

        if not sections:
            raise ResearchSynthesisError(
                "workspace claims do not match any task"
            )

        citations = list(
            citation_registry.values()
        )

        unique_claim_ids = {
            claim_id.strip().casefold()
            for section in sections
            for claim_id in section.claim_ids
        }
        unique_source_ids = {
            citation.source_id.strip().casefold()
            for citation in citations
        }

        return ResearchSynthesisReport(
            report_id=(
                f"{workspace.request.request_id}-report"
            ),
            workspace_id=workspace.workspace_id,
            request_id=workspace.request.request_id,
            title=self._report_title(workspace),
            executive_summary=(
                self._executive_summary(
                    workspace=workspace,
                    claim_count=len(unique_claim_ids),
                    citation_count=len(citations),
                    source_count=len(unique_source_ids),
                )
            ),
            sections=sections,
            citations=citations,
            claim_count=len(unique_claim_ids),
            citation_count=len(citations),
            source_count=len(unique_source_ids),
            synthesizer=self.name,
            metadata={
                "method": "deterministic",
                "output_format": (
                    workspace.request.output_format.value
                ),
            },
        )

    def _build_section(
        self,
        *,
        workspace: ResearchWorkspace,
        task_id: str,
        task_title: str,
        claims: list[ResearchClaim],
        order: int,
        citation_registry: dict[
            str,
            ResearchSynthesisCitation,
        ],
        citation_labels: dict[str, str],
    ) -> ResearchSynthesisSection:
        """Build one task-scoped report section."""

        content_lines: list[str] = []
        section_citation_ids: list[str] = []

        for position, claim in enumerate(
            claims,
            start=1,
        ):
            labels: list[str] = []

            for citation in claim.ordered_citations():
                report_citation = (
                    self._register_citation(
                        workspace=workspace,
                        citation=citation,
                        citation_registry=(
                            citation_registry
                        ),
                        citation_labels=citation_labels,
                    )
                )

                labels.append(
                    report_citation.label
                )

                if (
                    report_citation.citation_id
                    not in section_citation_ids
                ):
                    section_citation_ids.append(
                        report_citation.citation_id
                    )

            citation_text = " ".join(labels)

            content_lines.append(
                (
                    f"{position}. {claim.text.strip()} "
                    f"{citation_text}"
                ).rstrip()
            )

        return ResearchSynthesisSection(
            section_id=f"section-{order:03d}",
            task_id=task_id,
            title=task_title,
            content="\n".join(content_lines),
            order=order,
            claim_ids=[
                claim.claim_id
                for claim in claims
            ],
            citation_ids=section_citation_ids,
            metadata={
                "claim_count": str(len(claims)),
            },
        )

    def _register_citation(
        self,
        *,
        workspace: ResearchWorkspace,
        citation: ResearchCitation,
        citation_registry: dict[
            str,
            ResearchSynthesisCitation,
        ],
        citation_labels: dict[str, str],
    ) -> ResearchSynthesisCitation:
        """Register or return one report-level citation."""

        citation_key = (
            citation.evidence_id.strip().casefold()
        )

        existing = citation_registry.get(
            citation_key
        )

        if existing is not None:
            return existing

        evidence = next(
            (
                item
                for item
                in workspace.evidence_set.evidence
                if item.evidence_id
                .strip()
                .casefold()
                == citation_key
            ),
            None,
        )

        if evidence is None:
            raise ResearchSynthesisError(
                "citation references missing evidence"
            )

        document = next(
            (
                item
                for item
                in workspace.evidence_set
                .document_set
                .documents
                if item.document_id
                .strip()
                .casefold()
                == evidence.document_id
                .strip()
                .casefold()
            ),
            None,
        )

        if document is None:
            raise ResearchSynthesisError(
                "evidence references missing document"
            )

        label = citation_labels.get(
            citation_key
        )

        if label is None:
            label = (
                f"[{len(citation_labels) + 1}]"
            )
            citation_labels[citation_key] = label

        report_citation = ResearchSynthesisCitation(
            citation_id=citation.citation_id,
            evidence_id=evidence.evidence_id,
            source_id=evidence.source_id,
            document_id=evidence.document_id,
            label=label,
            title=document.candidate.title,
            url=document.candidate.url,
            excerpt=evidence.excerpt,
            metadata={
                "task_id": evidence.task_id,
            },
        )

        citation_registry[citation_key] = (
            report_citation
        )

        return report_citation

    @staticmethod
    def _report_title(
        workspace: ResearchWorkspace,
    ) -> str:
        """Return the deterministic report title."""

        return (
            "Research Report: "
            f"{workspace.request.question.strip()}"
        )

    @staticmethod
    def _executive_summary(
        *,
        workspace: ResearchWorkspace,
        claim_count: int,
        citation_count: int,
        source_count: int,
    ) -> str:
        """Return a deterministic executive summary."""

        return (
            f"{workspace.request.objective.strip()} "
            f"This report contains {claim_count} claims, "
            f"{citation_count} citations, and evidence "
            f"from {source_count} sources."
        )
