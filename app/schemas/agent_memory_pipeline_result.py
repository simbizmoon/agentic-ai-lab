"""Result schema for the end-to-end agent memory pipeline."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.memory_prompt import (
    MemoryAugmentedPrompt,
)
from app.schemas.memory_retrieval_result import (
    MemoryRetrievalResult,
)


class AgentMemoryPipelineResult(BaseModel):
    """Combined memory retrieval and prompt result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    retrieval: MemoryRetrievalResult
    prompt: MemoryAugmentedPrompt

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentMemoryPipelineResult:
        """Ensure retrieval and prompt use the same memories."""

        if (
            self.prompt.memory_ids
            != self.retrieval.retrieved_memory_ids
        ):
            raise ValueError(
                "prompt memory IDs must match retrieval IDs"
            )

        expected_memory_used = bool(
            self.retrieval.retrieved_memory_ids
        )

        if self.prompt.memory_used != expected_memory_used:
            raise ValueError(
                "prompt memory flag must match retrieval"
            )

        return self
