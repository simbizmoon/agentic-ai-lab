"""Schemas for local LLM runtime benchmark executions."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LocalLLMBenchmarkStatus(StrEnum):
    """Terminal status of one local LLM benchmark run."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class LocalLLMBenchmarkRequest(BaseModel):
    """One reproducible local LLM benchmark request."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    benchmark_id: str
    model: str
    prompt: str
    think: bool
    run_label: str = "baseline"
    keep_alive: str | int | None = None
    expected_substring: str | None = None
    expected_answer: str | None = None
    num_predict: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0)
    seed: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate benchmark identity and input."""
        required_text = {
            "benchmark_id": self.benchmark_id,
            "model": self.model,
            "prompt": self.prompt,
            "run_label": self.run_label,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            isinstance(self.keep_alive, str)
            and not self.keep_alive.strip()
        ):
            raise ValueError(
                "keep_alive must not be blank when provided"
            )

        optional_text = {
            "expected_substring": self.expected_substring,
            "expected_answer": self.expected_answer,
        }
        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank when provided"
                )

        if (
            self.expected_substring is not None
            and self.expected_answer is not None
        ):
            raise ValueError(
                "use either expected_substring or expected_answer"
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


class LocalLLMBenchmarkMetrics(BaseModel):
    """Measured Ollama runtime metrics for one benchmark run."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    total_duration_ns: int = Field(ge=0)
    load_duration_ns: int = Field(ge=0)
    prompt_eval_count: int = Field(ge=0)
    prompt_eval_duration_ns: int = Field(ge=0)
    eval_count: int = Field(ge=0)
    eval_duration_ns: int = Field(ge=0)
    prompt_tokens_per_second: float | None = Field(
        default=None,
        ge=0,
    )
    generation_tokens_per_second: float | None = Field(
        default=None,
        ge=0,
    )


class LocalLLMBenchmarkResult(BaseModel):
    """Normalized result of one local LLM benchmark execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    benchmark_id: str
    run_label: str
    model: str
    think: bool
    status: LocalLLMBenchmarkStatus
    response: str
    thinking: str
    done_reason: str | None = None
    failure_reason: str | None = None
    quality_passed: bool | None = None
    expected_substring: str | None = None
    expected_answer: str | None = None
    parsed_answer: str | None = None
    metrics: LocalLLMBenchmarkMetrics
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def response_char_count(self) -> int:
        """Return final-response character count."""
        return len(self.response)

    @property
    def thinking_char_count(self) -> int:
        """Return thinking-trace character count."""
        return len(self.thinking)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate result identity and success/failure semantics."""
        required_text = {
            "benchmark_id": self.benchmark_id,
            "run_label": self.run_label,
            "model": self.model,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if self.status is LocalLLMBenchmarkStatus.SUCCEEDED:
            if not self.response.strip():
                raise ValueError(
                    "successful benchmark must include response"
                )
            if self.failure_reason is not None:
                raise ValueError(
                    "successful benchmark must not include failure_reason"
                )
        elif (
            self.failure_reason is None
            or not self.failure_reason.strip()
        ):
            raise ValueError(
                "failed benchmark must include failure_reason"
            )

        return self
