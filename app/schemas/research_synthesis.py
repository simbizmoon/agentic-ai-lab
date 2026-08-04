"""Schemas for synthesized research reports."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ResearchSynthesisCitation(BaseModel):
    """One report-level citation linked to a source."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    citation_id: str
    evidence_id: str
    source_id: str
    document_id: str
    label: str
    title: str
    url: str
    excerpt: str
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_citation(self) -> Self:
        """Validate report citation fields."""

        required_text = {
            "citation_id": self.citation_id,
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "document_id": self.document_id,
            "label": self.label,
            "title": self.title,
            "url": self.url,
            "excerpt": self.excerpt,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self


class ResearchSynthesisSection(BaseModel):
    """One ordered section of a synthesized report."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    section_id: str
    task_id: str
    title: str
    content: str
    order: int = Field(ge=1)
    claim_ids: list[str] = Field(
        min_length=1
    )
    citation_ids: list[str] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_section(self) -> Self:
        """Validate section identity and references."""

        required_text = {
            "section_id": self.section_id,
            "task_id": self.task_id,
            "title": self.title,
            "content": self.content,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        self._validate_unique_ids(
            self.claim_ids,
            field_name="claim_ids",
        )
        self._validate_unique_ids(
            self.citation_ids,
            field_name="citation_ids",
        )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self

    @staticmethod
    def _validate_unique_ids(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate a list of nonblank unique IDs."""

        if any(
            not value.strip()
            for value in values
        ):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )


class ResearchSynthesisReport(BaseModel):
    """Final synthesized report for one research workspace."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    report_id: str
    workspace_id: str
    request_id: str
    title: str
    executive_summary: str
    sections: list[
        ResearchSynthesisSection
    ] = Field(min_length=1)
    citations: list[
        ResearchSynthesisCitation
    ] = Field(min_length=1)
    claim_count: int = Field(ge=1)
    citation_count: int = Field(ge=1)
    source_count: int = Field(ge=1)
    synthesizer: str
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        """Validate report identity, counts, and references."""

        required_text = {
            "report_id": self.report_id,
            "workspace_id": self.workspace_id,
            "request_id": self.request_id,
            "title": self.title,
            "executive_summary": self.executive_summary,
            "synthesizer": self.synthesizer,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        section_ids = [
            section.section_id.strip().casefold()
            for section in self.sections
        ]

        if len(set(section_ids)) != len(section_ids):
            raise ValueError(
                "section IDs must be unique"
            )

        section_orders = [
            section.order
            for section in self.sections
        ]

        if len(set(section_orders)) != len(
            section_orders
        ):
            raise ValueError(
                "section orders must be unique"
            )

        citation_ids = [
            citation.citation_id.strip().casefold()
            for citation in self.citations
        ]

        if len(set(citation_ids)) != len(citation_ids):
            raise ValueError(
                "report citation IDs must be unique"
            )

        labels = [
            citation.label.strip().casefold()
            for citation in self.citations
        ]

        if len(set(labels)) != len(labels):
            raise ValueError(
                "report citation labels must be unique"
            )

        evidence_ids = [
            citation.evidence_id.strip().casefold()
            for citation in self.citations
        ]

        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError(
                "report evidence citations must be unique"
            )

        known_citations = set(citation_ids)

        for section in self.sections:
            section_citations = {
                value.strip().casefold()
                for value in section.citation_ids
            }

            if not section_citations.issubset(
                known_citations
            ):
                raise ValueError(
                    "section citations must reference "
                    "report citations"
                )

        actual_claim_count = len(
            {
                claim_id.strip().casefold()
                for section in self.sections
                for claim_id in section.claim_ids
            }
        )

        if self.claim_count != actual_claim_count:
            raise ValueError(
                "claim_count must match section claims"
            )

        if self.citation_count != len(self.citations):
            raise ValueError(
                "citation_count must match citations"
            )

        actual_source_count = len(
            {
                citation.source_id.strip().casefold()
                for citation in self.citations
            }
        )

        if self.source_count != actual_source_count:
            raise ValueError(
                "source_count must match citation sources"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self

    def ordered_sections(
        self,
    ) -> list[ResearchSynthesisSection]:
        """Return sections in deterministic order."""

        return sorted(
            self.sections,
            key=lambda section: section.order,
        )

    def citation_by_id(
        self,
        citation_id: str,
    ) -> ResearchSynthesisCitation | None:
        """Return one citation by normalized ID."""

        if not citation_id.strip():
            raise ValueError(
                "citation_id must not be blank"
            )

        normalized = (
            citation_id.strip().casefold()
        )

        return next(
            (
                citation
                for citation in self.citations
                if citation.citation_id
                .strip()
                .casefold()
                == normalized
            ),
            None,
        )
