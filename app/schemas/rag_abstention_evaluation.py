"""Schemas for RAG insufficient-evidence evaluation."""

from __future__ import annotations

import math

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RagAbstentionEvaluationCase(BaseModel):
    """One question expected to have insufficient evidence."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    case_id: str = Field(min_length=1)
    question: str
    top_k: int = Field(ge=1)
    minimum_score: float = Field(ge=-1.0, le=1.0)
    expected_markers: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_case(
        self,
    ) -> RagAbstentionEvaluationCase:
        """Reject blank case values and duplicate markers."""

        if not self.case_id.strip():
            raise ValueError(
                "abstention evaluation case ID must not be blank"
            )

        if not self.question.strip():
            raise ValueError(
                "abstention evaluation question must not be blank"
            )

        normalized_markers = [
            marker.strip()
            for marker in self.expected_markers
        ]

        if any(not marker for marker in normalized_markers):
            raise ValueError(
                "abstention markers must not be blank"
            )

        if len(normalized_markers) != len(
            set(normalized_markers)
        ):
            raise ValueError(
                "abstention markers must be unique"
            )

        return self


class RagAbstentionCaseEvaluation(BaseModel):
    """Evaluation result for one insufficient-evidence case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    retrieved_document_ids: list[str] = Field(
        default_factory=list
    )
    cited_ids: list[str] = Field(default_factory=list)
    answer_text: str | None = None
    matched_markers: list[str] = Field(default_factory=list)
    no_evidence: bool
    no_citations: bool
    abstention_detected: bool
    answer_generated: bool
    error_code: str | None = None
    error_message: str | None = None
    passed: bool

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> RagAbstentionCaseEvaluation:
        """Validate successful and failed evaluation consistency."""

        if self.answer_generated:
            if not self.answer_text:
                raise ValueError(
                    "generated abstention requires answer_text"
                )

            if self.error_code is not None:
                raise ValueError(
                    "generated answer must not contain error_code"
                )

            if self.error_message is not None:
                raise ValueError(
                    "generated answer must not contain error_message"
                )
        else:
            if self.answer_text is not None:
                raise ValueError(
                    "failed generation must not contain answer_text"
                )

            if not self.error_code or not self.error_message:
                raise ValueError(
                    "failed generation requires error details"
                )

        expected_passed = (
            self.answer_generated
            and self.no_evidence
            and self.no_citations
            and self.abstention_detected
        )

        if self.passed != expected_passed:
            raise ValueError(
                "abstention passed flag is inconsistent"
            )

        return self


class RagAbstentionEvaluationSummary(BaseModel):
    """Aggregate metrics for insufficient-evidence cases."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    cases: list[RagAbstentionCaseEvaluation] = Field(
        default_factory=list
    )
    case_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    answer_generated_count: int = Field(ge=0)
    no_evidence_count: int = Field(ge=0)
    no_citation_count: int = Field(ge=0)
    abstention_detected_count: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    abstention_rate: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_summary(
        self,
    ) -> RagAbstentionEvaluationSummary:
        """Validate aggregate metrics and counts."""

        if not math.isfinite(self.pass_rate):
            raise ValueError(
                "pass_rate must be finite"
            )

        if not math.isfinite(self.abstention_rate):
            raise ValueError(
                "abstention_rate must be finite"
            )

        if self.case_count != len(self.cases):
            raise ValueError(
                "case_count must match cases length"
            )

        if self.passed_count != sum(
            case.passed for case in self.cases
        ):
            raise ValueError(
                "passed_count must match passed cases"
            )

        if self.answer_generated_count != sum(
            case.answer_generated for case in self.cases
        ):
            raise ValueError(
                "answer_generated_count must match cases"
            )

        if self.no_evidence_count != sum(
            case.no_evidence for case in self.cases
        ):
            raise ValueError(
                "no_evidence_count must match cases"
            )

        if self.no_citation_count != sum(
            case.no_citations for case in self.cases
        ):
            raise ValueError(
                "no_citation_count must match cases"
            )

        if self.abstention_detected_count != sum(
            case.abstention_detected for case in self.cases
        ):
            raise ValueError(
                "abstention count must match cases"
            )

        return self
