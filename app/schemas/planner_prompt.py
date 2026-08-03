"""Schemas for structured planner prompts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PlannerPromptKind(StrEnum):
    """Kinds of prompts supplied to a planner model."""

    INITIAL_PLAN = "initial_plan"
    REPLAN = "replan"


class PlannerPromptRole(StrEnum):
    """Supported message roles for planner prompts."""

    SYSTEM = "system"
    USER = "user"


class PlannerPromptMessage(BaseModel):
    """One message supplied to the planner model."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    role: PlannerPromptRole
    content: str

    @model_validator(mode="after")
    def validate_message(
        self,
    ) -> PlannerPromptMessage:
        """Reject blank prompt messages."""

        if not self.content.strip():
            raise ValueError(
                "planner prompt content must not be blank"
            )

        return self


class PlannerPrompt(BaseModel):
    """Complete prompt for initial planning or replanning."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    kind: PlannerPromptKind
    messages: list[PlannerPromptMessage] = Field(
        min_length=2,
        max_length=2,
    )
    maximum_steps: int = Field(ge=1, le=100)
    available_tools: list[str] = Field(
        default_factory=list
    )
    source_plan_id: str | None = None

    @model_validator(mode="after")
    def validate_prompt(
        self,
    ) -> PlannerPrompt:
        """Validate role order and prompt metadata."""

        if [
            message.role
            for message in self.messages
        ] != [
            PlannerPromptRole.SYSTEM,
            PlannerPromptRole.USER,
        ]:
            raise ValueError(
                "planner prompt must contain system "
                "then user messages"
            )

        if any(
            not tool_name.strip()
            for tool_name in self.available_tools
        ):
            raise ValueError(
                "available tools must not contain blanks"
            )

        normalized_tools = [
            tool_name.strip().casefold()
            for tool_name in self.available_tools
        ]

        if len(normalized_tools) != len(
            set(normalized_tools)
        ):
            raise ValueError(
                "available tools must be unique"
            )

        if (
            self.kind is PlannerPromptKind.INITIAL_PLAN
            and self.source_plan_id is not None
        ):
            raise ValueError(
                "initial plan prompt must not have "
                "a source plan ID"
            )

        if (
            self.kind is PlannerPromptKind.REPLAN
            and (
                self.source_plan_id is None
                or not self.source_plan_id.strip()
            )
        ):
            raise ValueError(
                "replan prompt requires a source plan ID"
            )

        return self
