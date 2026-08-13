"""Tests for the in-memory research source search adapter."""

from datetime import date

import pytest

from app.research.in_memory_research_source_search_tool import (
    InMemoryResearchSourceSearchTool,
)
from app.research.research_source_search_tool_validator import (
    ResearchSourceSearchToolValidator,
)
from app.schemas.in_memory_research_source import (
    InMemoryResearchSourceRecord,
)
from app.schemas.research_request import (
    ResearchSourceType,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
)
from app.schemas.research_source_search import (
    ResearchSourceSearchStatus,
)


def record(
    *,
    source_id: str,
    title: str,
    url: str,
    source_type: ResearchSourceType,
    snippet: str = "",
    keywords: list[str] | None = None,
    published_at: date | None = None,
    metadata: dict[str, str] | None = None,
) -> InMemoryResearchSourceRecord:
    """Return one source record."""

    return InMemoryResearchSourceRecord(
        source_id=source_id,
        title=title,
        url=url,
        source_type=source_type,
        snippet=snippet,
        keywords=keywords or [],
        published_at=published_at,
        metadata=metadata or {},
    )


def records() -> list[InMemoryResearchSourceRecord]:
    """Return deterministic source records."""

    return [
        record(
            source_id="source-working",
            title="Working memory for autonomous agents",
            url="https://example.com/working",
            source_type=(
                ResearchSourceType.PRIMARY_RESEARCH
            ),
            snippet=(
                "Working memory supports temporary "
                "agent state."
            ),
            keywords=[
                "agent memory",
                "working memory",
            ],
            published_at=date(2026, 1, 10),
        ),
        record(
            source_id="source-episodic",
            title="Episodic memory in AI agents",
            url="https://example.com/episodic",
            source_type=ResearchSourceType.ACADEMIC,
            snippet=(
                "Episodic memory stores past agent "
                "experiences."
            ),
            keywords=[
                "agent memory",
                "episodic memory",
            ],
            published_at=date(2025, 6, 1),
        ),
        record(
            source_id="source-official",
            title="Official agent memory documentation",
            url="https://example.com/official",
            source_type=(
                ResearchSourceType.OFFICIAL_DOCUMENTATION
            ),
            snippet=(
                "Official documentation for agent "
                "memory features."
            ),
            keywords=[
                "official documentation",
                "agent memory",
            ],
            published_at=date(2026, 2, 1),
        ),
        record(
            source_id="source-unrelated",
            title="Computer graphics rendering",
            url="https://example.com/graphics",
            source_type=ResearchSourceType.INDUSTRY,
            snippet="Rendering methods for graphics.",
            keywords=["graphics"],
            published_at=date(2026, 1, 1),
        ),
    ]


def query(
    **overrides: object,
) -> ResearchSearchQuery:
    """Return one valid search query."""

    values: dict[str, object] = {
        "query_id": "query-001",
        "request_id": "research-001",
        "task_id": "task-001",
        "query_text": "agent working memory",
        "maximum_results": 10,
    }
    values.update(overrides)

    return ResearchSearchQuery.model_validate(values)


def tool() -> InMemoryResearchSourceSearchTool:
    """Return the search adapter under test."""

    return InMemoryResearchSourceSearchTool(
        records=records()
    )


def test_tool_returns_matching_candidates() -> None:
    result = tool().search(query())

    assert result.status is (
        ResearchSourceSearchStatus.SUCCEEDED
    )
    assert next(
        candidate.source_id
        for candidate in result.candidates
    ) == "source-working"


def test_tool_returns_no_results() -> None:
    result = tool().search(
        query(query_text="quantum biology")
    )

    assert result.status is (
        ResearchSourceSearchStatus.NO_RESULTS
    )
    assert result.candidates == []
    assert result.error is None


def test_tool_applies_source_type_filter() -> None:
    result = tool().search(
        query(
            query_text="agent memory",
            preferred_source_types=[
                ResearchSourceType.OFFICIAL_DOCUMENTATION
            ],
        )
    )

    assert [
        candidate.source_id
        for candidate in result.candidates
    ] == [
        "source-official"
    ]


def test_tool_applies_date_range() -> None:
    result = tool().search(
        query(
            query_text="agent memory",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
    )

    assert {
        candidate.source_id
        for candidate in result.candidates
    } == {
        "source-working",
        "source-official",
    }


def test_tool_limits_candidate_count() -> None:
    result = tool().search(
        query(
            query_text="agent memory",
            maximum_results=2,
        )
    )

    assert len(result.candidates) == 2


def test_tool_assigns_sequential_ranks() -> None:
    result = tool().search(
        query(query_text="agent memory")
    )

    assert [
        candidate.rank
        for candidate in result.candidates
    ] == list(
        range(
            1,
            len(result.candidates) + 1,
        )
    )


def test_tool_adds_search_metadata() -> None:
    value = InMemoryResearchSourceSearchTool(
        records=[
            record(
                source_id="source-memory",
                title="Agent working memory",
                url="https://example.com/memory",
                source_type=ResearchSourceType.ACADEMIC,
                metadata={"document_path": "memory.md"},
            )
        ]
    )

    first_query = query(query_text="agent memory")
    second_query = query(query_text="working memory")

    first_candidate = value.search(
        first_query
    ).candidates[0]
    second_candidate = value.search(
        second_query
    ).candidates[0]

    assert first_candidate.metadata["provider"] == (
        "in-memory"
    )
    assert int(
        first_candidate.metadata["relevance_score"]
    ) > 0
    assert first_candidate.metadata["document_path"] == (
        "memory.md"
    )
    assert first_candidate.metadata[
        "search_query_text"
    ] == first_query.query_text
    assert second_candidate.metadata[
        "search_query_text"
    ] == second_query.query_text
    assert value.search(first_query).metadata["tool"] == (
        "in_memory_source_search"
    )


def test_tool_result_satisfies_contract_validator() -> None:
    value = tool()
    search_query = query()
    result = value.search(search_query)

    ResearchSourceSearchToolValidator().validate_result(
        tool=value,
        query=search_query,
        result=result,
    )


def test_tool_search_is_deterministic() -> None:
    value = tool()
    search_query = query()

    first = value.search(search_query)
    second = value.search(search_query)

    assert [
        candidate.model_dump(mode="json")
        for candidate in first.candidates
    ] == [
        candidate.model_dump(mode="json")
        for candidate in second.candidates
    ]


def test_tool_returns_defensive_record_copies() -> None:
    value = tool()

    returned = value.records()
    returned.clear()

    assert len(value.records()) == 4


def test_tool_rejects_duplicate_record_ids() -> None:
    duplicate_records = [
        record(
            source_id="source-001",
            title="First",
            url="https://example.com/first",
            source_type=ResearchSourceType.ACADEMIC,
        ),
        record(
            source_id=" SOURCE-001 ",
            title="Second",
            url="https://example.com/second",
            source_type=ResearchSourceType.ACADEMIC,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="record source IDs must be unique",
    ):
        InMemoryResearchSourceSearchTool(
            records=duplicate_records
        )


def test_tool_rejects_duplicate_record_urls() -> None:
    duplicate_records = [
        record(
            source_id="source-001",
            title="First",
            url="https://example.com/source/",
            source_type=ResearchSourceType.ACADEMIC,
        ),
        record(
            source_id="source-002",
            title="Second",
            url="HTTPS://EXAMPLE.COM:443/source",
            source_type=ResearchSourceType.ACADEMIC,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="record URLs must be unique",
    ):
        InMemoryResearchSourceSearchTool(
            records=duplicate_records
        )


def test_tool_rejects_blank_identity() -> None:
    with pytest.raises(
        ValueError,
        match="name must not be blank",
    ):
        InMemoryResearchSourceSearchTool(
            records=[],
            name=" ",
        )

    with pytest.raises(
        ValueError,
        match="provider must not be blank",
    ):
        InMemoryResearchSourceSearchTool(
            records=[],
            provider=" ",
        )
