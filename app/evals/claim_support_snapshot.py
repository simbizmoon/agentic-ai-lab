"""Schemas for deterministic claim support evaluation."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class EvidenceGroundingStatus(StrEnum):
    """Grounding state of evidence used to support a claim."""

    GROUNDED = "grounded"
    PARTIAL = "partial"
    UNGROUNDED = "ungrounded"
    NOT_EVALUATED = "not_evaluated"


class ClaimSupportEvidenceArtifact(BaseModel):
    """One evidence artifact available for claim support."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evidence_id: str
    source_id: str
    grounding_status: EvidenceGroundingStatus
    required: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        """Validate evidence identity and source."""

        if not self.evidence_id.strip():
            raise ValueError(
                "evidence_id must not be blank"
            )

        if not self.source_id.strip():
            raise ValueError(
                "source_id must not be blank"
            )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class ClaimSupportClaimArtifact(BaseModel):
    """One claim and its configured support requirements."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    claim_id: str
    text: str
    supporting_evidence_ids: list[str] = Field(
        default_factory=list
    )
    required_evidence_ids: list[str] = Field(
        default_factory=list
    )
    minimum_support_count: int = Field(default=1, ge=1)
    minimum_source_count: int = Field(default=1, ge=1)
    required: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        """Validate claim support requirements."""

        if not self.claim_id.strip():
            raise ValueError(
                "claim_id must not be blank"
            )

        if not self.text.strip():
            raise ValueError(
                "text must not be blank"
            )

        self._validate_unique_text(
            self.supporting_evidence_ids,
            field_name="supporting_evidence_ids",
        )
        self._validate_unique_text(
            self.required_evidence_ids,
            field_name="required_evidence_ids",
        )

        supporting_ids = {
            evidence_id.strip().casefold()
            for evidence_id in self.supporting_evidence_ids
        }

        for evidence_id in self.required_evidence_ids:
            if (
                evidence_id.strip().casefold()
                not in supporting_ids
            ):
                raise ValueError(
                    "required_evidence_ids must be included "
                    "in supporting_evidence_ids"
                )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate nonblank unique text."""

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
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class ClaimSupportSnapshot(BaseModel):
    """Claims and evidence supplied to claim support evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_id: str
    request_id: str
    workspace_id: str
    evidence: list[ClaimSupportEvidenceArtifact] = Field(
        default_factory=list
    )
    claims: list[ClaimSupportClaimArtifact] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Validate snapshot identity and unique artifacts."""

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
            [
                evidence.evidence_id
                for evidence in self.evidence
            ],
            field_name="evidence IDs",
        )
        self._validate_unique_ids(
            [
                claim.claim_id
                for claim in self.claims
            ],
            field_name="claim IDs",
        )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_ids(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate unique nonblank identifiers."""

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
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )
