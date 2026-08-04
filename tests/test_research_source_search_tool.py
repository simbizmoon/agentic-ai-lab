"""Tests for the research source search tool contract."""

import pytest

from app.research.research_source_search_tool import (
    ResearchSourceSearchTool,
)
from app.research.research_source_search_tool_validator import (
    ResearchSourceSearchToolValidator,
)
from app.schemas.research_request import (
    ResearchSourceType,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_search import (
    ResearchSourceSearchResult,
    ResearchSourceSearchStatus,
)


def query(
    *,
    query_id: str = "query-001",
) -> ResearchSearchQuery:
    """Return one valid search query."""

    return ResearchSearchQuery(
        query_id=query_id,
        request_id="research-001",
        task_id="task-001",
        query_text="agent memory architecture",
    )


class StubSourceSearchTool(ResearchSourceSearchTool):
    """Simple tool implementation for contract tests."""

    def __init__(
        self,
        *,
        name: str = "stub_source_search",
        provider: str = "stub-provider",
    ) -> None:
        self._name = name
        self._provider = provider

    @property
    def name(self) -> str:
        """Return the tool name."""

        return self._name

    @property
    def provider(self) -> str:
        """Return the provider name."""

        return self._provider

    def search(
        self,
        query: ResearchSearchQuery,
    ) -> ResearchSourceSearchResult:
        """Return one deterministic candidate."""

        return ResearchSourceSearchResult(
            query=query,
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider=self.provider,
            candidates=[
                ResearchSourceCandidate(
                    source_id="source-001",
                    request_id=query.request_id,
                    task_id=query.task_id,
                    query_id=query.query_id,
                    title="Agent memory architecture",
                    url="https://example.com/source",
                    source_type=(
                        ResearchSourceType.PRIMARY_RESEARCH
                    ),
                    rank=1,
                )
            ],
            duration_ms=0,
        )


def test_tool_implements_search_contract() -> None:
    tool = StubSourceSearchTool()
    value = query()

    result = tool.search(value)

    assert tool.name == "stub_source_search"
    assert tool.provider == "stub-provider"
    assert result.query == value
    assert result.provider == tool.provider


def test_validator_accepts_valid_tool_and_result() -> None:
    tool = StubSourceSearchTool()
    value = query()
    result = tool.search(value)

    validator = ResearchSourceSearchToolValidator()

    validator.validate_tool(tool)
    validator.validate_result(
        tool=tool,
        query=value,
        result=result,
    )


def test_validator_rejects_blank_tool_name() -> None:
    tool = StubSourceSearchTool(name=" ")

    with pytest.raises(
        ValueError,
        match="search tool name must not be blank",
    ):
        ResearchSourceSearchToolValidator().validate_tool(
            tool
        )


def test_validator_rejects_blank_provider() -> None:
    tool = StubSourceSearchTool(provider=" ")

    with pytest.raises(
        ValueError,
        match=(
            "search tool provider must not be blank"
        ),
    ):
        ResearchSourceSearchToolValidator().validate_tool(
            tool
        )


def test_validator_rejects_different_result_query() -> None:
    tool = StubSourceSearchTool()
    invoked_query = query(query_id="query-001")
    result_query = query(query_id="query-002")
    result = tool.search(result_query)

    with pytest.raises(
        ValueError,
        match=(
            "search result query must match "
            "the invoked query"
        ),
    ):
        ResearchSourceSearchToolValidator().validate_result(
            tool=tool,
            query=invoked_query,
            result=result,
        )


def test_validator_rejects_provider_mismatch() -> None:
    tool = StubSourceSearchTool()

    result = ResearchSourceSearchResult(
        query=query(),
        status=ResearchSourceSearchStatus.NO_RESULTS,
        provider="different-provider",
        candidates=[],
        duration_ms=0,
    )

    with pytest.raises(
        ValueError,
        match=(
            "search result provider must match "
            "the tool provider"
        ),
    ):
        ResearchSourceSearchToolValidator().validate_result(
            tool=tool,
            query=query(),
            result=result,
        )
