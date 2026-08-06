"""Adapt application research requests to research-domain requests."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.application.research_execution import (
    ApplicationResearchExecutionRequest,
)
from app.schemas.research_request import (
    ResearchDepth,
    ResearchOutputFormat,
    ResearchRequest,
    ResearchSourceType,
)


class ApplicationResearchRequestAdapter:
    """Convert an application request without hidden inference."""

    def adapt(
        self,
        request: ApplicationResearchExecutionRequest,
    ) -> ResearchRequest:
        """Return one validated research-domain request."""

        context = request.context
        objective = self._optional_text(
            context,
            key="objective",
        ) or (
            "Produce a grounded answer with traceable evidence "
            f"for the following question: {request.query.strip()}"
        )

        return ResearchRequest(
            request_id=request.request_id,
            question=request.query.strip(),
            objective=objective,
            depth=self._enum_value(
                context,
                key="depth",
                enum_type=ResearchDepth,
                default=ResearchDepth.STANDARD,
            ),
            output_format=self._enum_value(
                context,
                key="output_format",
                enum_type=ResearchOutputFormat,
                default=ResearchOutputFormat.DETAILED_REPORT,
            ),
            include_topics=self._text_list(
                context,
                key="include_topics",
            ),
            exclude_topics=self._text_list(
                context,
                key="exclude_topics",
            ),
            preferred_source_types=self._enum_list(
                context,
                key="preferred_source_types",
                enum_type=ResearchSourceType,
            ),
            start_date=self._optional_date(
                context,
                key="start_date",
            ),
            end_date=self._optional_date(
                context,
                key="end_date",
            ),
            maximum_sources=self._positive_int(
                context,
                key="maximum_sources",
                default=5,
            ),
            require_citations=self._boolean(
                context,
                key="require_citations",
                default=True,
            ),
            metadata={
                **request.metadata,
                "application_workspace_id": request.workspace_id,
                "application_agent_id": request.agent_id,
            },
        )

    @staticmethod
    def _optional_text(
        context: dict[str, Any],
        *,
        key: str,
    ) -> str | None:
        value = context.get(key)

        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"context.{key} must be a string")

        normalized = value.strip()
        if not normalized:
            raise ValueError(f"context.{key} must not be blank")

        return normalized

    @staticmethod
    def _text_list(
        context: dict[str, Any],
        *,
        key: str,
    ) -> list[str]:
        value = context.get(key, [])

        if not isinstance(value, list):
            raise TypeError(f"context.{key} must be a list")

        normalized: list[str] = []

        for item in value:
            if not isinstance(item, str):
                raise TypeError(
                    f"context.{key} must contain only strings"
                )

            text = item.strip()
            if not text:
                raise ValueError(
                    f"context.{key} must not contain blank values"
                )

            normalized.append(text)

        return normalized

    @classmethod
    def _enum_list(
        cls,
        context: dict[str, Any],
        *,
        key: str,
        enum_type: type,
    ) -> list[Any]:
        values = cls._text_list(context, key=key)
        converted: list[Any] = []

        for value in values:
            try:
                converted.append(enum_type(value))
            except ValueError as exc:
                raise ValueError(
                    f"context.{key} contains an unsupported value: "
                    f"{value}"
                ) from exc

        return converted

    @staticmethod
    def _enum_value(
        context: dict[str, Any],
        *,
        key: str,
        enum_type: type,
        default: Any,
    ) -> Any:
        value = context.get(key)

        if value is None:
            return default
        if not isinstance(value, str):
            raise TypeError(f"context.{key} must be a string")

        try:
            return enum_type(value.strip())
        except ValueError as exc:
            raise ValueError(
                f"context.{key} contains an unsupported value: "
                f"{value}"
            ) from exc

    @staticmethod
    def _optional_date(
        context: dict[str, Any],
        *,
        key: str,
    ) -> date | None:
        value = context.get(key)

        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(
                f"context.{key} must be an ISO date string"
            )

        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise TypeError(
                f"context.{key} must be an ISO date string"
            ) from exc

    @staticmethod
    def _positive_int(
        context: dict[str, Any],
        *,
        key: str,
        default: int,
    ) -> int:
        value = context.get(key, default)

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"context.{key} must be an integer")
        if value < 1:
            raise ValueError(
                f"context.{key} must be greater than zero"
            )

        return value

    @staticmethod
    def _boolean(
        context: dict[str, Any],
        *,
        key: str,
        default: bool,
    ) -> bool:
        value = context.get(key, default)

        if not isinstance(value, bool):
            raise TypeError(f"context.{key} must be a boolean")

        return value
