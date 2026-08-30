"""OpenAI web-search binding that returns source URLs, never answer text."""

from __future__ import annotations

from typing import Any, Protocol

from app.research.stage9_verified_official_source_provider import (
    Stage9OfficialSourceCandidate,
)


class _ResponsesProtocol(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _OpenAIClientProtocol(Protocol):
    responses: _ResponsesProtocol


class Stage9OpenAIOfficialSourceDiscoveryError(RuntimeError):
    """OpenAI discovery did not preserve the locked URL-only boundary."""


class Stage9OpenAIOfficialSourceDiscovery:
    """Discover official URLs through one forced, domain-filtered web search."""

    def __init__(self, *, client: _OpenAIClientProtocol, model: str) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        self._client = client
        self._model = model

    def discover(
        self,
        *,
        query: str,
        allowed_domains: tuple[str, ...],
        maximum_results: int,
    ) -> tuple[Stage9OfficialSourceCandidate, ...]:
        if not query.strip():
            raise ValueError("query must not be blank")
        if not allowed_domains or any(not value.strip() for value in allowed_domains):
            raise ValueError("allowed_domains must contain nonblank domains")
        if maximum_results < 1 or maximum_results > 2:
            raise ValueError("maximum_results must be between 1 and 2")

        response = self._client.responses.create(
            model=self._model,
            input=(
                "Find official source pages for this research question. "
                "Return no unsupported claims. Query: " + query
            ),
            tools=[
                {
                    "type": "web_search",
                    "filters": {"allowed_domains": list(allowed_domains)},
                }
            ],
            tool_choice={"type": "web_search"},
            include=["web_search_call.action.sources"],
            max_tool_calls=1,
            max_output_tokens=128,
            store=False,
        )
        if getattr(response, "status", None) != "completed":
            raise Stage9OpenAIOfficialSourceDiscoveryError(
                "web-search discovery did not complete"
            )

        candidates: list[Stage9OfficialSourceCandidate] = []
        seen: set[str] = set()
        for item in getattr(response, "output", ()):
            if getattr(item, "type", None) != "web_search_call":
                continue
            action = getattr(item, "action", None)
            for source in getattr(action, "sources", ()):
                url = str(getattr(source, "url", "")).strip()
                title = str(getattr(source, "title", "")).strip() or url
                if not url or url.casefold() in seen:
                    continue
                seen.add(url.casefold())
                candidates.append(Stage9OfficialSourceCandidate(url=url, title=title))
                if len(candidates) == maximum_results:
                    return tuple(candidates)
        return tuple(candidates)
