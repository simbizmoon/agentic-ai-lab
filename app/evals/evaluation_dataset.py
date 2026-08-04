"""Schemas for deterministic research evaluation datasets."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class EvaluationDifficulty(StrEnum):
    """Difficulty level of one evaluation case."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class EvaluationCaseStatus(StrEnum):
    """Lifecycle status of an evaluation case."""

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class ExpectedSource(BaseModel):
    """One source expected or accepted for an evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_id: str
    title: str
    canonical_url: str | None = None
    publisher: str | None = None
    required: bool = True
    acceptable_alternatives: list[str] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        """Validate expected source fields."""

        required_text = {
            "source_id": self.source_id,
            "title": self.title,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.canonical_url is not None
            and not self.canonical_url.strip()
        ):
            raise ValueError(
                "canonical_url must not be blank when provided"
            )

        if (
            self.publisher is not None
            and not self.publisher.strip()
        ):
            raise ValueError(
                "publisher must not be blank when provided"
            )

        self._validate_unique_text(
            self.acceptable_alternatives,
            field_name="acceptable_alternatives",
        )
        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate nonblank, case-insensitively unique text."""

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
        """Validate string metadata."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class ExpectedEvidence(BaseModel):
    """One expected evidence item for an evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evidence_id: str
    source_id: str
    expected_text: str
    location_hint: str | None = None
    required: bool = True
    semantic_match_allowed: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        """Validate expected evidence fields."""

        required_text = {
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "expected_text": self.expected_text,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.location_hint is not None
            and not self.location_hint.strip()
        ):
            raise ValueError(
                "location_hint must not be blank when provided"
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


class ExpectedClaim(BaseModel):
    """One expected claim and its supporting evidence."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    claim_id: str
    expected_text: str
    supporting_evidence_ids: list[str] = Field(
        min_length=1
    )
    required: bool = True
    semantic_match_allowed: bool = True
    minimum_support_count: int = Field(default=1, ge=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        """Validate expected claim fields."""

        if not self.claim_id.strip():
            raise ValueError(
                "claim_id must not be blank"
            )

        if not self.expected_text.strip():
            raise ValueError(
                "expected_text must not be blank"
            )

        normalized_evidence_ids = [
            evidence_id.strip().casefold()
            for evidence_id in self.supporting_evidence_ids
        ]

        if any(
            not evidence_id.strip()
            for evidence_id in self.supporting_evidence_ids
        ):
            raise ValueError(
                "supporting_evidence_ids must not "
                "contain blank values"
            )

        if (
            len(set(normalized_evidence_ids))
            != len(normalized_evidence_ids)
        ):
            raise ValueError(
                "supporting_evidence_ids must not "
                "contain duplicates"
            )

        if (
            self.minimum_support_count
            > len(self.supporting_evidence_ids)
        ):
            raise ValueError(
                "minimum_support_count must not exceed "
                "supporting evidence count"
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


class EvaluationCase(BaseModel):
    """One complete research evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    case_id: str
    name: str
    description: str
    research_question: str
    status: EvaluationCaseStatus = (
        EvaluationCaseStatus.ACTIVE
    )
    difficulty: EvaluationDifficulty
    input_context: list[str] = Field(default_factory=list)
    expected_sources: list[ExpectedSource] = Field(
        default_factory=list
    )
    expected_evidence: list[ExpectedEvidence] = Field(
        default_factory=list
    )
    expected_claims: list[ExpectedClaim] = Field(
        default_factory=list
    )
    required_report_elements: list[str] = Field(
        default_factory=list
    )
    forbidden_report_elements: list[str] = Field(
        default_factory=list
    )
    tags: list[str] = Field(default_factory=list)
    minimum_overall_score: float = Field(
        default=0.7,
        ge=0,
        le=1,
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_case(self) -> Self:
        """Validate case identity and artifact relationships."""

        required_text = {
            "case_id": self.case_id,
            "name": self.name,
            "description": self.description,
            "research_question": self.research_question,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_unique_text(
            self.input_context,
            field_name="input_context",
        )
        self._validate_unique_text(
            self.required_report_elements,
            field_name="required_report_elements",
        )
        self._validate_unique_text(
            self.forbidden_report_elements,
            field_name="forbidden_report_elements",
        )
        self._validate_unique_text(
            self.tags,
            field_name="tags",
        )

        self._validate_unique_ids(
            [
                source.source_id
                for source in self.expected_sources
            ],
            field_name="expected source IDs",
        )
        self._validate_unique_ids(
            [
                evidence.evidence_id
                for evidence in self.expected_evidence
            ],
            field_name="expected evidence IDs",
        )
        self._validate_unique_ids(
            [
                claim.claim_id
                for claim in self.expected_claims
            ],
            field_name="expected claim IDs",
        )

        source_ids = {
            source.source_id.strip().casefold()
            for source in self.expected_sources
        }

        for evidence in self.expected_evidence:
            if (
                evidence.source_id.strip().casefold()
                not in source_ids
            ):
                raise ValueError(
                    "expected evidence must reference "
                    "an expected source"
                )

        evidence_ids = {
            evidence.evidence_id.strip().casefold()
            for evidence in self.expected_evidence
        }

        for claim in self.expected_claims:
            for evidence_id in (
                claim.supporting_evidence_ids
            ):
                if (
                    evidence_id.strip().casefold()
                    not in evidence_ids
                ):
                    raise ValueError(
                        "expected claim must reference "
                        "expected evidence"
                    )

        required_elements = {
            value.strip().casefold()
            for value in self.required_report_elements
        }
        forbidden_elements = {
            value.strip().casefold()
            for value in self.forbidden_report_elements
        }

        if required_elements & forbidden_elements:
            raise ValueError(
                "report elements must not be both "
                "required and forbidden"
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
        """Validate nonblank unique text values."""

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

    @property
    def required_source_count(self) -> int:
        """Return the number of required expected sources."""

        return sum(
            source.required
            for source in self.expected_sources
        )

    @property
    def required_evidence_count(self) -> int:
        """Return the number of required evidence items."""

        return sum(
            evidence.required
            for evidence in self.expected_evidence
        )

    @property
    def required_claim_count(self) -> int:
        """Return the number of required claims."""

        return sum(
            claim.required
            for claim in self.expected_claims
        )


class EvaluationDataset(BaseModel):
    """A versioned collection of research evaluation cases."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    dataset_id: str
    name: str
    description: str
    version: str
    cases: list[EvaluationCase] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dataset(self) -> Self:
        """Validate dataset identity and case uniqueness."""

        required_text = {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        case_ids = [
            case.case_id.strip().casefold()
            for case in self.cases
        ]

        if len(set(case_ids)) != len(case_ids):
            raise ValueError(
                "dataset cases must have unique case IDs"
            )

        if any(not tag.strip() for tag in self.tags):
            raise ValueError(
                "tags must not contain blank values"
            )

        normalized_tags = [
            tag.strip().casefold()
            for tag in self.tags
        ]

        if len(set(normalized_tags)) != len(normalized_tags):
            raise ValueError(
                "tags must not contain duplicates"
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

    @property
    def active_cases(self) -> list[EvaluationCase]:
        """Return active evaluation cases."""

        return [
            case
            for case in self.cases
            if case.status is EvaluationCaseStatus.ACTIVE
        ]

    def case_by_id(
        self,
        case_id: str,
    ) -> EvaluationCase | None:
        """Return one case using case-insensitive ID matching."""

        normalized = case_id.strip().casefold()

        return next(
            (
                case
                for case in self.cases
                if case.case_id.strip().casefold()
                == normalized
            ),
            None,
        )
