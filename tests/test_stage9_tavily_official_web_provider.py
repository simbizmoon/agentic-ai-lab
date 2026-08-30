"""Offline tests for the bounded Stage 9 Tavily official-web binding."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.research.stage9_tavily_official_web_provider import (
    Stage9TavilyContentSizeBoundaryError,
    Stage9TavilyDomainBoundaryError,
    Stage9TavilyHttpStatusError,
    Stage9TavilyOfficialWebProvider,
    Stage9TavilyRawContentUnavailableError,
    Stage9TavilyResultCountBoundaryError,
)

CONTENT = "# NIST AI RMF\n\nGovern, Map, Measure, and Manage are core functions."


def _provider(handler):
    return Stage9TavilyOfficialWebProvider(
        api_key="test-secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: datetime(2026, 8, 30, 3, 0, tzinfo=UTC),
    )


def _response(*results):
    return {"query": "NIST AI RMF", "results": list(results), "usage": {"credits": 1}}


def _result(**changes):
    value = {
        "title": "NIST AI Risk Management Framework",
        "url": "https://www.nist.gov/itl/ai-risk-management-framework",
        "content": "summary must not be used as evidence",
        "raw_content": CONTENT,
        "score": 0.99,
    }
    value.update(changes)
    return value


def test_sends_one_explicit_bounded_search_and_preserves_raw_markdown() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_response(_result()), request=request)

    documents = _provider(handler).acquire(
        query="NIST AI RMF",
        allowed_domains=("nist.gov",),
        maximum_results=2,
    )

    assert len(seen) == 1
    payload = json.loads(seen[0].content)
    assert payload == {
        "query": "NIST AI RMF",
        "topic": "general",
        "search_depth": "basic",
        "auto_parameters": False,
        "include_answer": False,
        "include_raw_content": "markdown",
        "include_images": False,
        "include_usage": True,
        "max_results": 2,
        "include_domains": ["nist.gov"],
    }
    assert seen[0].headers["authorization"] == "Bearer test-secret"
    assert documents[0].content == CONTENT
    assert (
        documents[0].response_sha256
        == hashlib.sha256(CONTENT.encode("utf-8")).hexdigest()
    )
    assert documents[0].retrieved_at == "2026-08-30T03:00:00+00:00"


def test_rejects_summary_fallback_when_raw_content_is_absent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_response(_result(raw_content=None)), request=request
        )

    with pytest.raises(Stage9TavilyRawContentUnavailableError, match="raw content"):
        _provider(handler).acquire(
            query="NIST AI RMF",
            allowed_domains=("nist.gov",),
            maximum_results=1,
        )


def test_retains_valid_exact_document_when_another_result_lacks_raw_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_response(_result(raw_content=None), _result()),
            request=request,
        )

    documents = _provider(handler).acquire(
        query="NIST GAI profile",
        allowed_domains=("nist.gov",),
        maximum_results=2,
    )

    assert len(documents) == 1
    assert documents[0].content == CONTENT


@pytest.mark.parametrize(
    "url",
    ["http://www.nist.gov/insecure", "https://nist.gov.example.com/copy"],
)
def test_rejects_non_https_or_cross_domain_results(url: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_response(_result(url=url)), request=request)

    with pytest.raises(Stage9TavilyDomainBoundaryError, match="allowlist"):
        _provider(handler).acquire(
            query="NIST AI RMF",
            allowed_domains=("nist.gov",),
            maximum_results=1,
        )


def test_retains_valid_document_when_another_result_is_outside_allowlist() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_response(
                _result(url="https://example.com/untrusted"),
                _result(),
            ),
            request=request,
        )

    documents = _provider(handler).acquire(
        query="NIST GAI profile",
        allowed_domains=("nist.gov",),
        maximum_results=2,
    )

    assert len(documents) == 1
    assert documents[0].url.startswith("https://www.nist.gov/")


def test_retains_valid_document_when_another_result_is_oversized() -> None:
    oversized = "x" * 512_001

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_response(_result(raw_content=oversized), _result()),
            request=request,
        )

    documents = _provider(handler).acquire(
        query="NIST GAI profile",
        allowed_domains=("nist.gov",),
        maximum_results=2,
    )

    assert len(documents) == 1
    assert documents[0].content == CONTENT


def test_rejects_all_oversized_results_with_typed_boundary() -> None:
    oversized = "x" * 512_001

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_response(_result(raw_content=oversized)),
            request=request,
        )

    with pytest.raises(Stage9TavilyContentSizeBoundaryError, match="byte boundary"):
        _provider(handler).acquire(
            query="NIST GAI profile",
            allowed_domains=("nist.gov",),
            maximum_results=1,
        )


def test_rejects_provider_result_count_over_requested_boundary() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_response(_result(), _result()), request=request
        )

    with pytest.raises(Stage9TavilyResultCountBoundaryError, match="result boundary"):
        _provider(handler).acquire(
            query="NIST AI RMF",
            allowed_domains=("nist.gov",),
            maximum_results=1,
        )


def test_maps_http_failure_without_retrying() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"detail": "limited"}, request=request)

    with pytest.raises(Stage9TavilyHttpStatusError, match="HTTP 429"):
        _provider(handler).acquire(
            query="NIST AI RMF",
            allowed_domains=("nist.gov",),
            maximum_results=1,
        )
    assert calls == 1


def test_rejects_invalid_local_bounds_before_any_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("request must not be sent")

    provider = _provider(handler)
    with pytest.raises(ValueError, match="between 1 and 2"):
        provider.acquire(
            query="NIST AI RMF",
            allowed_domains=("nist.gov",),
            maximum_results=3,
        )
