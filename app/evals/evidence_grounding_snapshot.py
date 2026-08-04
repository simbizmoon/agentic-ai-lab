"""Schemas for deterministic evidence grounding evaluation."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class GroundingSourceArtifact(BaseModel):
    """One source document used for evidence grounding."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_id: str
    title: str
    text: str
    locations: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        """Validate source identity and text."""

        required_text = {
            "source_id": self.source_id,
            "title": self.title,
            "text": self.text,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        for location_id, location_text in self.locations.items():
            if not location_id.strip():
                raise ValueError(
                    "location IDs must not be blank"
                )

            if not location_text.strip():
                raise ValueError(
                    "location text must not be blank"
                )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata values."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class GroundingEvidenceArtifact(BaseModel):
    """One evidence item to ground against a source."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evidence_id: str
    source_id: str
    text: str
    location_reference: str | None = None
    required: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        """Validate evidence identity and references."""

        required_text = {
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "text": self.text,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.location_reference is not None
            and not self.location_reference.strip()
        ):
            raise ValueError(
                "location_reference must not be blank "
                "when provided"
            )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata values."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class EvidenceGroundingSnapshot(BaseModel):
    """Sources and evidence supplied to grounding evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_id: str
    request_id: str
    workspace_id: str
    sources: list[GroundingSourceArtifact] = Field(
        default_factory=list
    )
    evidence: list[GroundingEvidenceArtifact] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Validate execution identity and artifact uniqueness."""

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

        self._validate_unique_ids(
            [source.source_id for source in self.sources],
            field_name="source IDs",
        )
        self._validate_unique_ids(
            [
                evidence.evidence_id
                for evidence in self.evidence
            ],
            field_name="evidence IDs",
        )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_ids(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate nonblank unique identifiers."""

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

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata values."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )
