"""Schemas for end-to-end memory retrieval results."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.memory_context import MemoryContext
from app.schemas.memory_search_result import (
    MemorySearchResult,
)


class MemoryRetrievalResult(BaseModel):
    """Search results and safe context produced together."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    search_results: list[MemorySearchResult]
    context: MemoryContext
    retrieved_memory_ids: list[str]
    access_recorded: bool

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> MemoryRetrievalResult:
        """Validate retrieved IDs and context consistency."""

        if len(self.retrieved_memory_ids) != len(
            set(self.retrieved_memory_ids)
        ):
            raise ValueError(
                "retrieved memory IDs must be unique"
            )

        search_ids = {
            result.memory.memory_id
            for result in self.search_results
        }

        if not set(
            self.retrieved_memory_ids
        ).issubset(search_ids):
            raise ValueError(
                "retrieved IDs must come from search results"
            )

        context_ids = {
            item.memory_id
            for item in self.context.items
        }

        if context_ids != set(
            self.retrieved_memory_ids
        ):
            raise ValueError(
                "retrieved IDs must match context items"
            )

        return self
