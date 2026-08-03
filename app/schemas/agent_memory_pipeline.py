"""Schemas for the end-to-end agent memory pipeline."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.memory_retrieval import (
    MemoryRetrievalRequest,
)


class AgentMemoryPipelineRequest(BaseModel):
    """Input for retrieval and prompt composition."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    system_instructions: str
    user_query: str
    retrieval: MemoryRetrievalRequest

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> AgentMemoryPipelineRequest:
        """Validate trusted instructions and query consistency."""

        if not self.system_instructions.strip():
            raise ValueError(
                "system instructions must not be blank"
            )

        if not self.user_query.strip():
            raise ValueError(
                "user query must not be blank"
            )

        if (
            self.user_query.strip()
            != self.retrieval.query.strip()
        ):
            raise ValueError(
                "user_query must match retrieval query"
            )

        return self
