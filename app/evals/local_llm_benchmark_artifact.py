"""JSON artifact schemas and writer for local LLM benchmark runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.evals.local_llm_benchmark import LocalLLMBenchmarkResult


class LocalLLMBenchmarkArtifact(BaseModel):
    """Persisted artifact containing related local benchmark results."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    artifact_version: str = "1.0.0"
    created_at: datetime
    model: str
    benchmark_group: str
    results: list[LocalLLMBenchmarkResult] = Field(min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_artifact(self) -> Self:
        """Validate artifact identity and model consistency."""
        if not self.artifact_version.strip():
            raise ValueError("artifact_version must not be blank")
        if not self.model.strip():
            raise ValueError("model must not be blank")
        if not self.benchmark_group.strip():
            raise ValueError("benchmark_group must not be blank")

        normalized_model = self.model.strip().casefold()
        if any(
            result.model.strip().casefold() != normalized_model
            for result in self.results
        ):
            raise ValueError(
                "all benchmark results must use artifact model"
            )

        run_labels = [
            result.run_label.strip().casefold()
            for result in self.results
        ]
        if len(set(run_labels)) != len(run_labels):
            raise ValueError(
                "benchmark result run labels must be unique"
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


class LocalLLMBenchmarkArtifactWriter:
    """Write one benchmark artifact as stable UTF-8 JSON."""

    def write(
        self,
        *,
        artifact: LocalLLMBenchmarkArtifact,
        path: Path,
    ) -> Path:
        """Write artifact atomically enough for local benchmark usage."""
        if not path.name:
            raise ValueError("path must include a file name")

        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = artifact.model_dump(
            mode="json",
            exclude_none=False,
        )
        path.write_text(
            json.dumps(
                serialized,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return path
