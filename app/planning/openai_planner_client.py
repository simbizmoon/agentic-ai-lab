"""OpenAI Responses API client for structured agent planning."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.planning.openai_responses_protocol import (
    OpenAIResponsesClient,
)
from app.planning.planner_client import (
    PlannerClient,
    PlannerClientError,
)
from app.planning.planner_output_validator import (
    PlannerOutputValidator,
)
from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planner_client_config import (
    PlannerClientConfig,
)
from app.schemas.planner_client_result import (
    PlannerClientResult,
)
from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_prompt import (
    PlannerPrompt,
    PlannerPromptRole,
)


class OpenAIPlannerClient(PlannerClient):
    """Generate structured plan drafts using OpenAI Responses."""

    def __init__(
        self,
        *,
        client: OpenAIResponsesClient,
        config: PlannerClientConfig | None = None,
        validator: PlannerOutputValidator | None = None,
    ) -> None:
        self._client = client
        self._config = config or PlannerClientConfig()
        self._validator = (
            validator or PlannerOutputValidator()
        )

    @property
    def config(self) -> PlannerClientConfig:
        """Return the configured planner client options."""

        return self._config

    @property
    def validator(self) -> PlannerOutputValidator:
        """Return the configured output validator."""

        return self._validator

    def create_plan(
        self,
        *,
        request: PlanCreationRequest,
        prompt: PlannerPrompt,
    ) -> PlannerClientResult:
        """Generate, parse, and validate one plan draft."""

        self._validate_prompt_request(
            request=request,
            prompt=prompt,
        )

        response = self._client.responses.create(
            model=self.config.model,
            input=[
                {
                    "role": message.role.value,
                    "content": message.content,
                }
                for message in prompt.messages
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "plan_draft_output",
                    "description": (
                        "Structured steps for an executable "
                        "agent plan."
                    ),
                    "strict": True,
                    "schema": (
                        PlanDraftOutput.model_json_schema()
                    ),
                }
            },
            max_output_tokens=(
                self.config.max_output_tokens
            ),
            store=self.config.store,
            **self._reasoning_arguments(),
        )

        raw_output = getattr(
            response,
            "output_text",
            None,
        )

        if not isinstance(raw_output, str):
            raise PlannerClientError(
                "OpenAI response did not contain output_text"
            )

        if not raw_output.strip():
            raise PlannerClientError(
                "OpenAI planner returned blank output"
            )

        try:
            output = PlanDraftOutput.model_validate_json(
                raw_output
            )
        except ValidationError as exc:
            raise PlannerClientError(
                "OpenAI planner output failed "
                "PlanDraftOutput validation"
            ) from exc

        validation = self.validator.validate(
            request=request,
            output=output,
        )

        return PlannerClientResult(
            output=output,
            validation=validation,
            response_id=self._optional_text_attribute(
                response,
                "id",
            ),
            model=self._optional_text_attribute(
                response,
                "model",
            ),
        )

    def _reasoning_arguments(
        self,
    ) -> dict[str, Any]:
        """Return optional Responses reasoning arguments."""

        if self.config.reasoning_effort is None:
            return {}

        return {
            "reasoning": {
                "effort": self.config.reasoning_effort
            }
        }

    @staticmethod
    def _validate_prompt_request(
        *,
        request: PlanCreationRequest,
        prompt: PlannerPrompt,
    ) -> None:
        """Validate prompt metadata against its request."""

        if prompt.maximum_steps != request.maximum_steps:
            raise PlannerClientError(
                "prompt maximum_steps does not match request"
            )

        if prompt.available_tools != request.available_tools:
            raise PlannerClientError(
                "prompt available_tools do not match request"
            )

        if [
            message.role
            for message in prompt.messages
        ] != [
            PlannerPromptRole.SYSTEM,
            PlannerPromptRole.USER,
        ]:
            raise PlannerClientError(
                "planner prompt role order is invalid"
            )

    @staticmethod
    def _optional_text_attribute(
        response: object,
        attribute: str,
    ) -> str | None:
        """Return one optional nonblank response attribute."""

        value = getattr(response, attribute, None)

        if value is None:
            return None

        if not isinstance(value, str):
            return str(value)

        return value or None
