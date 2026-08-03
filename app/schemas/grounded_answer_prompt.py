"""Schemas for grounded answer prompts."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.rag_context import RagContext


class GroundedAnswerPrompt(BaseModel):
    """Instructions and input for a grounded LLM answer."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    system_instructions: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    question: str
    context: RagContext

    @model_validator(mode="after")
    def validate_prompt(self) -> GroundedAnswerPrompt:
        """Validate grounded prompt consistency."""

        if not self.question.strip():
            raise ValueError(
                "grounded answer question must not be blank"
            )

        if self.context.citations:
            for citation in self.context.citations:
                marker = f"[{citation.citation_id}]"

                if marker not in self.user_prompt:
                    raise ValueError(
                        "user prompt must include every citation marker"
                    )

        return self
