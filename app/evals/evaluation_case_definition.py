"""Complete evaluation case definition with expected outcome."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.evals.evaluation_dataset import (
    EvaluationCaseStatus,
    EvaluationDifficulty,
)
from app.evals.evaluation_expected_outcome import (
    EvaluationExpectedOutcome,
)


class EvaluationInput(BaseModel):
    """Input supplied to one research evaluation execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    research_question: str
    context: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_input(self) -> Self:
        """Validate evaluation input."""

        if not self.research_question.strip():
            raise ValueError(
                "research_question must not be blank"
            )

        self._validate_unique_text(
            self.context,
            field_name="context",
        )
        self._validate_unique_text(
            self.constraints,
            field_name="constraints",
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


class EvaluationCaseDefinition(BaseModel):
    """One reusable evaluation case and expected outcome."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    case_id: str
    name: str
    description: str
    status: EvaluationCaseStatus = (
        EvaluationCaseStatus.ACTIVE
    )
    difficulty: EvaluationDifficulty
    evaluation_input: EvaluationInput
    expected_outcome: EvaluationExpectedOutcome
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_case(self) -> Self:
        """Validate case identity and metadata."""

        required_text = {
            "case_id": self.case_id,
            "name": self.name,
            "description": self.description,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
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
