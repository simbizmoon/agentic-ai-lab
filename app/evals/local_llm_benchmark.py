"""Schemas for local LLM runtime benchmark executions."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LocalLLMBenchmarkRequest(BaseModel):
    """One reproducible local LLM benchmark request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    benchmark_id: str
    model: str
    prompt: str
    think: bool
    run_label: str = "baseline"
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
                raise ValueError(f"{field_name} must not be blank")
        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError("metadata keys must not be blank")
            if not value.strip():
                raise ValueError("metadata values must not be blank")
        return self


class LocalLLMBenchmarkMetrics(BaseModel):
    """Measured Ollama runtime metrics for one benchmark run."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    total_duration_ns: int = Field(ge=0)
    load_duration_ns: int = Field(ge=0)
    prompt_eval_count: int = Field(ge=0)
    prompt_eval_duration_ns: int = Field(ge=0)
    eval_count: int = Field(ge=0)
    eval_duration_ns: int = Field(ge=0)
    prompt_tokens_per_second: float | None = Field(default=None, ge=0)
    generation_tokens_per_second: float | None = Field(default=None, ge=0)


class LocalLLMBenchmarkResult(BaseModel):
    """Normalized result of one local LLM benchmark execution."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    benchmark_id: str
    run_label: str
    model: str
    think: bool
    response: str
    thinking: str
    done_reason: str | None = None
    metrics: LocalLLMBenchmarkMetrics
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate result identity and response semantics."""
        required_text = {
            "benchmark_id": self.benchmark_id,
            "run_label": self.run_label,
            "model": self.model,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(f"{field_name} must not be blank")
        if not self.response.strip():
            raise ValueError("response must not be blank for a successful benchmark")
        if self.done_reason is not None and not self.done_reason.strip():
            raise ValueError("done_reason must not be blank when provided")
        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError("metadata keys must not be blank")
            if not value.strip():
                raise ValueError("metadata values must not be blank")
        return self
