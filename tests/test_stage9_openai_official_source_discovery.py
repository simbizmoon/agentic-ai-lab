"""Offline tests for URL-only OpenAI official-source discovery."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.research.stage9_openai_official_source_discovery import (
    Stage9OpenAIOfficialSourceDiscovery,
    Stage9OpenAIOfficialSourceDiscoveryError,
)


class FixtureResponses:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _response(*sources, status="completed"):
    return SimpleNamespace(
        status=status,
        output=(
            SimpleNamespace(
                type="web_search_call",
                action=SimpleNamespace(sources=sources),
            ),
            SimpleNamespace(
                type="message",
                content="generated answer must not become evidence",
            ),
        ),
    )


def _source(url, title="NIST source"):
    return SimpleNamespace(url=url, title=title)


def test_forces_one_domain_filtered_search_and_returns_only_source_urls() -> None:
    responses = FixtureResponses(
        _response(
            _source("https://www.nist.gov/example-one"),
            _source("https://nvlpubs.nist.gov/example-two.pdf"),
        )
    )
    discovery = Stage9OpenAIOfficialSourceDiscovery(
        client=SimpleNamespace(responses=responses), model="gpt-5.6-terra"
    )

    candidates = discovery.discover(
        query="NIST GAI risk actions site:nist.gov",
        allowed_domains=("nist.gov",),
        maximum_results=2,
    )

    assert [item.url for item in candidates] == [
        "https://www.nist.gov/example-one",
        "https://nvlpubs.nist.gov/example-two.pdf",
    ]
    call = responses.calls[0]
    assert call["tools"] == [
        {
            "type": "web_search",
            "filters": {"allowed_domains": ["nist.gov"]},
        }
    ]
    assert call["tool_choice"] == {"type": "web_search"}
    assert call["include"] == ["web_search_call.action.sources"]
    assert call["max_tool_calls"] == 1
    assert call["store"] is False
    assert all("generated answer" not in item.title for item in candidates)


def test_deduplicates_sources_and_honors_result_ceiling() -> None:
    source = _source("https://www.nist.gov/example")
    responses = FixtureResponses(_response(source, source, _source("https://x.test")))

    candidates = Stage9OpenAIOfficialSourceDiscovery(
        client=SimpleNamespace(responses=responses), model="gpt-5.6-terra"
    ).discover(
        query="NIST",
        allowed_domains=("nist.gov",),
        maximum_results=1,
    )

    assert len(candidates) == 1


def test_rejects_noncompleted_discovery() -> None:
    discovery = Stage9OpenAIOfficialSourceDiscovery(
        client=SimpleNamespace(responses=FixtureResponses(_response(status="failed"))),
        model="gpt-5.6-terra",
    )

    with pytest.raises(Stage9OpenAIOfficialSourceDiscoveryError, match="complete"):
        discovery.discover(
            query="NIST", allowed_domains=("nist.gov",), maximum_results=1
        )
