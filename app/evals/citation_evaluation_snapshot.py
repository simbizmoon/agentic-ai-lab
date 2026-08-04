"""Schemas for deterministic citation correctness evaluation."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ActualCitationArtifact(BaseModel):
    """One citation produced by a research execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    citation_id: str
    claim_id: str
    evidence_id: str
    source_id: str
    locator: str | None = None
    quoted_text: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_citation(self) -> Self:
        """Validate citation identity and optional fields."""

        required_text = {
            "citation_id": self.citation_id,
            "claim_id": self.claim_id,
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if self.locator is not None and not self.locator.strip():
            raise ValueError(
                "locator must not be blank when provided"
            )

        if (
            self.quoted_text is not None
            and not self.quoted_text.strip()
        ):
            raise ValueError(
                "quoted_text must not be blank when provided"
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


class CitationEvaluationSnapshot(BaseModel):
    """Citation artifacts and reference indexes for one execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_id: str
    request_id: str
    workspace_id: str
    source_ids: list[str] = Field(default_factory=list)
    evidence_source_map: dict[str, str] = Field(
        default_factory=dict
    )
    claim_citation_map: dict[str, list[str]] = Field(
        default_factory=dict
    )
    citations: list[ActualCitationArtifact] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Validate IDs, maps, and citation uniqueness."""

        required_text = {
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_unique_text(
            self.source_ids,
            field_name="source_ids",
        )
        self._validate_unique_text(
            [
                citation.citation_id
                for citation in self.citations
            ],
            field_name="citation IDs",
        )

        for evidence_id, source_id in (
            self.evidence_source_map.items()
        ):
            if not evidence_id.strip():
                raise ValueError(
                    "evidence_source_map keys must not be blank"
                )

            if not source_id.strip():
                raise ValueError(
                    "evidence_source_map values must not be blank"
                )

        for claim_id, citation_ids in (
            self.claim_citation_map.items()
        ):
            if not claim_id.strip():
                raise ValueError(
                    "claim_citation_map keys must not be blank"
                )

            self._validate_unique_text(
                citation_ids,
                field_name=(
                    f"citation IDs for claim {claim_id}"
                ),
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
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate nonblank unique strings."""

        if any(not value.strip() for value in values):
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
