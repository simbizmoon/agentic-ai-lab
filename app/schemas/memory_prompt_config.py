"""Configuration for memory-augmented prompt composition."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MemoryPromptConfig(BaseModel):
    """Options controlling memory prompt composition."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    include_empty_memory_context: bool = False
    include_memory_ids_in_prompt: bool = False
