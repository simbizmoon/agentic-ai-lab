"""Normalized actual artifacts supplied to deterministic evaluation."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ActualSourceArtifact(BaseModel):
    """One actual source produced by a research execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_id: str
    title: str
    url: str | None = None
    publisher: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        """Validate actual source fields."""

        if not self.source_id.strip():
            raise ValueError("source_id must not be blank")

        if not self.title.strip():
            raise ValueError("title must not be blank")

        if self.url is not None and not self.url.strip():
            raise ValueError(
                "url must not be blank when provided"
            )

        if (
            self.publisher is not None
            and not self.publisher.strip()
        ):
            raise ValueError(
                "publisher must not be blank when provided"
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


class ActualEvidenceArtifact(BaseModel):
    """One actual evidence artifact."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evidence_id: str
    source_id: str
    text: str
    location_reference: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        """Validate actual evidence fields."""

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


class ActualClaimArtifact(BaseModel):
    """One actual research claim."""

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
    citation_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        """Validate actual claim fields."""

        if not self.claim_id.strip():
            raise ValueError("claim_id must not be blank")

        if not self.text.strip():
            raise ValueError("text must not be blank")

        self._validate_unique_text(
            self.supporting_evidence_ids,
            field_name="supporting_evidence_ids",
        )
        self._validate_unique_text(
            self.citation_ids,
            field_name="citation_ids",
        )
        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate unique nonblank strings."""

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


class EvaluationExecutionSnapshot(BaseModel):
    """Normalized research execution supplied to evaluators."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_id: str
    request_id: str
    workspace_id: str
    sources: list[ActualSourceArtifact] = Field(
        default_factory=list
    )
    evidence: list[ActualEvidenceArtifact] = Field(
        default_factory=list
    )
    claims: list[ActualClaimArtifact] = Field(
        default_factory=list
    )
    report_text: str = ""
    tool_call_count: int = Field(default=0, ge=0)
    input_token_count: int = Field(default=0, ge=0)
    output_token_count: int = Field(default=0, ge=0)
    revision_round_count: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Validate execution identity and artifact references."""

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
        self._validate_unique_ids(
            [claim.claim_id for claim in self.claims],
            field_name="claim IDs",
        )

        source_ids = {
            source.source_id.strip().casefold()
            for source in self.sources
        }

        for evidence in self.evidence:
            if (
                evidence.source_id.strip().casefold()
                not in source_ids
            ):
                raise ValueError(
                    "actual evidence must reference "
                    "an actual source"
                )

        evidence_ids = {
            evidence.evidence_id.strip().casefold()
            for evidence in self.evidence
        }

        for claim in self.claims:
            for evidence_id in (
                claim.supporting_evidence_ids
            ):
                if (
                    evidence_id.strip().casefold()
                    not in evidence_ids
                ):
                    raise ValueError(
                        "actual claim must reference "
                        "actual evidence"
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
