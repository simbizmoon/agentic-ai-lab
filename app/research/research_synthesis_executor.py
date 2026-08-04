"""Contract and schemas for specialist report synthesis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.schemas.research_agent_assignment import (
    ResearchAgentTaskAssignment,
)


class ResearchSynthesisExecutorError(RuntimeError):
    """Structured exception raised by a synthesis executor."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SYNTHESIS_EXECUTOR_ERROR",
        retryable: bool = False,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)

        if not code.strip():
            raise ValueError("code must not be blank")

        self.code = code
        self.retryable = retryable
        self.details = details or {}


class ResearchSynthesizedSection(BaseModel):
    """One structured section of a research report."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    section_id: str
    heading: str
    content: str
    claim_ids: list[str] = Field(default_factory=list)
    order: int = Field(ge=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_section(self) -> Self:
        """Validate synthesized section content."""

        for field_name, value in {
            "section_id": self.section_id,
            "heading": self.heading,
            "content": self.content,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if any(
            not claim_id.strip()
            for claim_id in self.claim_ids
        ):
            raise ValueError(
                "claim_ids must not contain blank values"
            )

        normalized = [
            claim_id.strip().casefold()
            for claim_id in self.claim_ids
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "claim_ids must not contain duplicates"
            )

        return self


class ResearchSynthesizedReport(BaseModel):
    """One complete structured research report draft."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    report_id: str
    title: str
    executive_summary: str
    sections: list[ResearchSynthesizedSection] = Field(
        min_length=1
    )
    limitations: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        """Validate report structure and ordering."""

        for field_name, value in {
            "report_id": self.report_id,
            "title": self.title,
            "executive_summary": self.executive_summary,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        section_ids = [
            section.section_id.strip().casefold()
            for section in self.sections
        ]

        if len(set(section_ids)) != len(section_ids):
            raise ValueError(
                "sections must have unique section IDs"
            )

        orders = [
            section.order
            for section in self.sections
        ]

        if len(set(orders)) != len(orders):
            raise ValueError(
                "sections must have unique order values"
            )

        if orders != sorted(orders):
            raise ValueError(
                "sections must be sorted by order"
            )

        self._validate_unique_text(
            self.limitations,
            field_name="limitations",
        )
        self._validate_unique_text(
            self.follow_up_questions,
            field_name="follow_up_questions",
        )

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate nonblank unique text entries."""

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


class ResearchSynthesisFailure(BaseModel):
    """Failure to synthesize one requested report section."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    section_key: str
    code: str
    message: str
    retryable: bool = False

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate synthesis failure."""

        for field_name, value in {
            "section_key": self.section_key,
            "code": self.code,
            "message": self.message,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class ResearchSynthesisExecutionResult(BaseModel):
    """Normalized report synthesis result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    requested_section_count: int = Field(ge=1)
    report: ResearchSynthesizedReport | None = None
    failures: list[ResearchSynthesisFailure] = Field(
        default_factory=list
    )
    tool_call_count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    input_token_count: int = Field(default=0, ge=0)
    output_token_count: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate synthesized report accounting."""

        if (
            self.report is not None
            and len(self.report.sections)
            + len(self.failures)
            > self.requested_section_count
        ):
            raise ValueError(
                "sections and failures must not exceed "
                "requested_section_count"
            )

        failure_keys = [
            failure.section_key.strip().casefold()
            for failure in self.failures
        ]

        if len(set(failure_keys)) != len(failure_keys):
            raise ValueError(
                "failures must have unique section keys"
            )

        return self

    @property
    def completed_section_count(self) -> int:
        """Return synthesized section count."""

        if self.report is None:
            return 0

        return len(self.report.sections)

    @property
    def is_complete(self) -> bool:
        """Return whether every requested section was produced."""

        return (
            self.report is not None
            and self.completed_section_count
            == self.requested_section_count
            and not self.failures
        )


class ResearchSynthesisExecutor(ABC):
    """Abstract report synthesis execution contract."""

    @abstractmethod
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSynthesisExecutionResult:
        """Synthesize one report assignment."""
