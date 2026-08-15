"""Tests for the Tavily research search adapter."""

import json
from datetime import date

import httpx
from pydantic import SecretStr

from app.research.research_source_search_tool_validator import (
    ResearchSourceSearchToolValidator,
)
from app.research.research_source_type_classifier import (
    ResearchSourceTypeClassifier,
)
from app.research.tavily_research_source_search_tool import (
    TavilyResearchSourceSearchTool,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_query import ResearchSearchQuery
from app.schemas.research_source_search import ResearchSourceSearchStatus
from app.schemas.tavily_search_config import TavilySearchConfig


def query(**overrides: object) -> ResearchSearchQuery:
    values: dict[str, object] = {
        "query_id": "query-001",
        "request_id": "research-001",
        "task_id": "task-001",
        "query_text": "agent memory architecture",
        "maximum_results": 5,
    }
    values.update(overrides)
    return ResearchSearchQuery.model_validate(values)


def config(**overrides: object) -> TavilySearchConfig:
    values: dict[str, object] = {
        "api_key": SecretStr("secret-key"),
        "maximum_results": 3,
    }
    values.update(overrides)
    return TavilySearchConfig.model_validate(values)


def response_payload() -> dict[str, object]:
    return {
        "query": "agent memory architecture",
        "results": [
            {
                "title": "Agent memory",
                "url": "https://example.com/agent-memory",
                "content": "Research about agent memory.",
                "score": 0.91,
            },
            {
                "title": "Episodic memory",
                "url": "https://example.org/episodic",
                "content": "Research about episodic memory.",
                "score": 0.82,
            },
        ],
        "response_time": 0.42,
        "request_id": "request-tavily-001",
        "usage": {"credits": 1},
    }


def tool_for(
    transport: httpx.MockTransport,
    *,
    value: TavilySearchConfig | None = None,
) -> TavilyResearchSourceSearchTool:
    return TavilyResearchSourceSearchTool(
        config=value or config(),
        client=httpx.Client(transport=transport),
    )


def test_tool_maps_successful_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json=response_payload(), request=request
        )
    )

    result = tool_for(transport).search(query())

    assert result.status is ResearchSourceSearchStatus.SUCCEEDED
    assert [c.rank for c in result.candidates] == [1, 2]
    assert result.candidates[0].metadata["provider_score"] == "0.91"
    assert result.candidates[0].metadata["research_origin"] == "web"
    assert (
        result.candidates[0].metadata["search_query_text"]
        == "agent memory architecture"
    )
    assert result.metadata["request_id"] == "request-tavily-001"
    assert result.metadata["usage_credits"] == "1"


def test_tool_builds_expected_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(
            request.content.decode("utf-8")
        )
        return httpx.Response(
            200, json=response_payload(), request=request
        )

    result = tool_for(
        httpx.MockTransport(handler),
        value=config(project_id="project-001"),
    ).search(
        query(
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
            maximum_results=10,
        )
    )

    assert result.status is ResearchSourceSearchStatus.SUCCEEDED
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["search_depth"] == "basic"
    assert payload["auto_parameters"] is False
    assert payload["include_answer"] is False
    assert payload["include_raw_content"] is False
    assert payload["include_images"] is False
    assert payload["include_usage"] is True
    assert payload["max_results"] == 3
    assert payload["start_date"] == "2025-01-01"
    assert payload["end_date"] == "2026-01-01"

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["authorization"] == "Bearer secret-key"
    assert headers["x-project-id"] == "project-001"


def test_tool_returns_no_results() -> None:
    payload = response_payload()
    payload["results"] = []
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json=payload, request=request
        )
    )

    result = tool_for(transport).search(query())

    assert result.status is ResearchSourceSearchStatus.NO_RESULTS
    assert result.candidates == []
    assert result.error is None


def test_tool_removes_duplicate_and_invalid_urls() -> None:
    payload = response_payload()
    payload["results"] = [
        {
            "title": "First",
            "url": "https://example.com/source/",
            "content": "First.",
            "score": 1.0,
        },
        {
            "title": "Duplicate",
            "url": "HTTPS://EXAMPLE.COM:443/source",
            "content": "Duplicate.",
            "score": 0.9,
        },
        {
            "title": "Invalid",
            "url": "file:///tmp/source",
            "content": "Invalid.",
            "score": 0.8,
        },
    ]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json=payload, request=request
        )
    )

    result = tool_for(transport).search(query())

    assert result.status is ResearchSourceSearchStatus.SUCCEEDED
    assert len(result.candidates) == 1
    assert result.candidates[0].rank == 1


def test_tool_returns_structured_http_errors() -> None:
    cases = [
        (400, "SearchRequestValidationError", False),
        (401, "SearchAuthenticationError", False),
        (403, "SearchAuthenticationError", False),
        (429, "SearchRateLimitError", True),
        (500, "SearchProviderError", True),
        (503, "SearchProviderError", True),
    ]

    for status, error_type, retryable in cases:
        transport = httpx.MockTransport(
            lambda request, status=status: httpx.Response(
                status,
                headers={"Retry-After": "30"},
                request=request,
            )
        )
        result = tool_for(transport).search(query())

        assert result.status is ResearchSourceSearchStatus.FAILED
        assert result.error is not None
        assert result.error.error_type == error_type
        assert result.error.retryable is retryable

        if status == 429:
            assert result.metadata["retry_after"] == "30"


def test_tool_maps_timeout_and_network_errors() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    timeout_result = tool_for(
        httpx.MockTransport(timeout_handler)
    ).search(query())

    assert timeout_result.error is not None
    assert timeout_result.error.error_type == "SearchTimeout"

    def network_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network", request=request)

    network_result = tool_for(
        httpx.MockTransport(network_handler)
    ).search(query())

    assert network_result.error is not None
    assert network_result.error.error_type == "SearchNetworkError"


def test_tool_rejects_invalid_json_and_schema() -> None:
    invalid_json = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=b"not-json", request=request
        )
    )
    result = tool_for(invalid_json).search(query())
    assert result.error is not None
    assert (
        result.error.error_type
        == "SearchResponseValidationError"
    )

    invalid_schema = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"query": "test", "results": "wrong"},
            request=request,
        )
    )
    result = tool_for(invalid_schema).search(query())
    assert result.error is not None
    assert (
        result.error.error_type
        == "SearchResponseValidationError"
    )


def test_tool_error_does_not_expose_api_key() -> None:
    secret = "do-not-expose-secret"
    value = config(api_key=SecretStr(secret))
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            401,
            json={"detail": secret},
            request=request,
        )
    )

    result = tool_for(transport, value=value).search(query())

    assert result.error is not None
    assert secret not in result.error.message
    assert secret not in str(result)
    assert secret not in repr(result)


def test_tool_satisfies_existing_contract() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json=response_payload(), request=request
        )
    )
    value = tool_for(transport)
    search_query = query()
    result = value.search(search_query)

    ResearchSourceSearchToolValidator().validate_result(
        tool=value,
        query=search_query,
        result=result,
    )


def test_source_ids_are_deterministic() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json=response_payload(), request=request
        )
    )
    value = tool_for(transport)
    search_query = query()

    first = value.search(search_query)
    second = value.search(search_query)

    assert [c.source_id for c in first.candidates] == [
        c.source_id for c in second.candidates
    ]


def test_tool_classifies_injected_trusted_host() -> None:
    payload = response_payload()
    payload["results"] = [
        {
            "title": "OpenAI Agents SDK",
            "url": (
                "https://openai.github.io/"
                "openai-agents-python/"
            ),
            "content": "Official SDK documentation.",
            "score": 0.95,
        }
    ]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=payload,
            request=request,
        )
    )
    tool = TavilyResearchSourceSearchTool(
        config=config(),
        client=httpx.Client(transport=transport),
        source_type_classifier=(
            ResearchSourceTypeClassifier(
                official_documentation_hosts=(
                    frozenset({"openai.github.io"})
                )
            )
        ),
    )

    result = tool.search(query())

    assert result.candidates[0].source_type is (
        ResearchSourceType.OFFICIAL_DOCUMENTATION
    )
