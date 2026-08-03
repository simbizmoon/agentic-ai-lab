"""Minimal protocols for injected OpenAI Responses clients."""

from __future__ import annotations

from typing import Any, Protocol


class ResponsesResource(Protocol):
    """Subset of the OpenAI Responses resource used here."""

    def create(
        self,
        **kwargs: Any,
    ) -> Any:
        """Create one model response."""


class OpenAIResponsesClient(Protocol):
    """Client exposing the Responses resource."""

    responses: ResponsesResource
