"""Schemas for prompts augmented with retrieved agent memory."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PromptRole(StrEnum):
    """Supported roles for generated prompt messages."""

    SYSTEM = "system"
    USER = "user"


class PromptMessage(BaseModel):
    """One role-separated prompt message."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    role: PromptRole
    content: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_message(self) -> PromptMessage:
        """Reject blank message content."""

        if not self.content.strip():
            raise ValueError(
                "prompt message content must not be blank"
            )

        return self


class MemoryAugmentedPrompt(BaseModel):
    """Role-separated prompt containing retrieved memory."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    messages: list[PromptMessage] = Field(
        min_length=2,
        max_length=2,
    )
    memory_ids: list[str] = Field(default_factory=list)
    memory_used: bool

    @model_validator(mode="after")
    def validate_prompt(
        self,
    ) -> MemoryAugmentedPrompt:
        """Validate message order and memory metadata."""

        expected_roles = [
            PromptRole.SYSTEM,
            PromptRole.USER,
        ]
        actual_roles = [
            message.role
            for message in self.messages
        ]

        if actual_roles != expected_roles:
            raise ValueError(
                "prompt messages must be ordered system then user"
            )

        if any(
            not memory_id.strip()
            for memory_id in self.memory_ids
        ):
            raise ValueError(
                "memory IDs must not be blank"
            )

        if len(self.memory_ids) != len(
            set(self.memory_ids)
        ):
            raise ValueError(
                "memory IDs must be unique"
            )

        if self.memory_used != bool(self.memory_ids):
            raise ValueError(
                "memory_used is inconsistent with memory_ids"
            )

        return self
