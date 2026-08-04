"""Expected outcome schemas for research evaluation cases."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.evals.evaluation_dataset import (
    ExpectedClaim,
    ExpectedEvidence,
    ExpectedSource,
)


class EvaluationDimension(StrEnum):
    """Supported research evaluation dimensions."""

    RELEVANCE = "relevance"
    COMPLETENESS = "completeness"
    CORRECTNESS = "correctness"
    SOURCE_QUALITY = "source_quality"
    EVIDENCE_GROUNDING = "evidence_grounding"
    CLAIM_SUPPORT = "claim_support"
    CITATION_CORRECTNESS = "citation_correctness"
    LOGICAL_CONSISTENCY = "logical_consistency"
    CLARITY = "clarity"
    LIMITATIONS_DISCLOSURE = "limitations_disclosure"


class ExpectedFailureConditionType(StrEnum):
    """Type of condition that makes an evaluation fail."""

    MISSING_REQUIRED_SOURCE = "missing_required_source"
    MISSING_REQUIRED_EVIDENCE = "missing_required_evidence"
    MISSING_REQUIRED_CLAIM = "missing_required_claim"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    INVALID_CITATION = "invalid_citation"
    FORBIDDEN_CONTENT = "forbidden_content"
    SCORE_BELOW_THRESHOLD = "score_below_threshold"
    WORKFLOW_FAILURE = "workflow_failure"
    CUSTOM = "custom"


class EvaluationScoreThreshold(BaseModel):
    """Minimum acceptable score for one evaluation dimension."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    dimension: EvaluationDimension
    minimum_score: float = Field(ge=0, le=1)
    required: bool = True
    rationale: str | None = None

    @model_validator(mode="after")
    def validate_threshold(self) -> Self:
        """Validate optional rationale."""

        if (
            self.rationale is not None
            and not self.rationale.strip()
        ):
            raise ValueError(
                "rationale must not be blank when provided"
            )

        return self


class AcceptableOutcomeVariation(BaseModel):
    """One explicitly accepted variation of an expected result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    variation_id: str
    target_type: str
    target_id: str
    description: str
    accepted_texts: list[str] = Field(default_factory=list)
    semantic_match_allowed: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_variation(self) -> Self:
        """Validate variation identity and accepted text."""

        required_text = {
            "variation_id": self.variation_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "description": self.description,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_unique_text(
            self.accepted_texts,
            field_name="accepted_texts",
        )
        self._validate_metadata(self.metadata)

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


class ExpectedFailureCondition(BaseModel):
    """One explicit condition that fails an evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    condition_id: str
    condition_type: ExpectedFailureConditionType
    description: str
    target_id: str | None = None
    blocking: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_condition(self) -> Self:
        """Validate failure condition fields."""

        if not self.condition_id.strip():
            raise ValueError(
                "condition_id must not be blank"
            )

        if not self.description.strip():
            raise ValueError(
                "description must not be blank"
            )

        if (
            self.target_id is not None
            and not self.target_id.strip()
        ):
            raise ValueError(
                "target_id must not be blank when provided"
            )

        if (
            self.condition_type
            in {
                ExpectedFailureConditionType
                .MISSING_REQUIRED_SOURCE,
                ExpectedFailureConditionType
                .MISSING_REQUIRED_EVIDENCE,
                ExpectedFailureConditionType
                .MISSING_REQUIRED_CLAIM,
            }
            and self.target_id is None
        ):
            raise ValueError(
                "artifact-related failure condition "
                "must include target_id"
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


class EvaluationExpectedOutcome(BaseModel):
    """Complete expected outcome for one evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    outcome_id: str
    name: str
    description: str
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
    acceptable_variations: list[
        AcceptableOutcomeVariation
    ] = Field(default_factory=list)
    score_thresholds: list[
        EvaluationScoreThreshold
    ] = Field(default_factory=list)
    failure_conditions: list[
        ExpectedFailureCondition
    ] = Field(default_factory=list)
    minimum_overall_score: float = Field(
        default=0.7,
        ge=0,
        le=1,
    )
    allow_partial_result: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Validate artifact links and expectation consistency."""

        required_text = {
            "outcome_id": self.outcome_id,
            "name": self.name,
            "description": self.description,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
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
        self._validate_unique_ids(
            [
                variation.variation_id
                for variation in self.acceptable_variations
            ],
            field_name="acceptable variation IDs",
        )
        self._validate_unique_ids(
            [
                condition.condition_id
                for condition in self.failure_conditions
            ],
            field_name="failure condition IDs",
        )

        self._validate_unique_text(
            self.required_report_elements,
            field_name="required_report_elements",
        )
        self._validate_unique_text(
            self.forbidden_report_elements,
            field_name="forbidden_report_elements",
        )

        source_ids = {
            source.source_id.strip().casefold()
            for source in self.expected_sources
        }
        evidence_ids = {
            evidence.evidence_id.strip().casefold()
            for evidence in self.expected_evidence
        }
        claim_ids = {
            claim.claim_id.strip().casefold()
            for claim in self.expected_claims
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

        self._validate_variation_targets(
            source_ids=source_ids,
            evidence_ids=evidence_ids,
            claim_ids=claim_ids,
        )
        self._validate_failure_targets(
            source_ids=source_ids,
            evidence_ids=evidence_ids,
            claim_ids=claim_ids,
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

        dimensions = [
            threshold.dimension
            for threshold in self.score_thresholds
        ]

        if len(set(dimensions)) != len(dimensions):
            raise ValueError(
                "score thresholds must have unique dimensions"
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

    def _validate_variation_targets(
        self,
        *,
        source_ids: set[str],
        evidence_ids: set[str],
        claim_ids: set[str],
    ) -> None:
        """Validate accepted variation target references."""

        supported_targets = {
            "source": source_ids,
            "evidence": evidence_ids,
            "claim": claim_ids,
        }

        for variation in self.acceptable_variations:
            target_type = (
                variation.target_type.strip().casefold()
            )

            if target_type not in supported_targets:
                continue

            if (
                variation.target_id.strip().casefold()
                not in supported_targets[target_type]
            ):
                raise ValueError(
                    "acceptable variation must reference "
                    "an expected artifact"
                )

    def _validate_failure_targets(
        self,
        *,
        source_ids: set[str],
        evidence_ids: set[str],
        claim_ids: set[str],
    ) -> None:
        """Validate artifact-related failure conditions."""

        target_sets = {
            ExpectedFailureConditionType
            .MISSING_REQUIRED_SOURCE: source_ids,
            ExpectedFailureConditionType
            .MISSING_REQUIRED_EVIDENCE: evidence_ids,
            ExpectedFailureConditionType
            .MISSING_REQUIRED_CLAIM: claim_ids,
        }

        for condition in self.failure_conditions:
            target_ids = target_sets.get(
                condition.condition_type
            )

            if (
                target_ids is not None
                and condition.target_id is not None
                and condition.target_id.strip().casefold()
                not in target_ids
            ):
                raise ValueError(
                    "failure condition must reference "
                    "an expected artifact"
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

    @property
    def required_thresholds(
        self,
    ) -> list[EvaluationScoreThreshold]:
        """Return required score thresholds."""

        return [
            threshold
            for threshold in self.score_thresholds
            if threshold.required
        ]

    @property
    def blocking_failure_conditions(
        self,
    ) -> list[ExpectedFailureCondition]:
        """Return blocking failure conditions."""

        return [
            condition
            for condition in self.failure_conditions
            if condition.blocking
        ]
