"""Tests for set-level pipeline source adapters."""

from __future__ import annotations

from app.research.in_memory_research_source_reader import (
    InMemoryResearchSourceReader,
)
from app.research.in_memory_research_source_search_tool import (
    InMemoryResearchSourceSearchTool,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceReaderAdapter,
    PipelineSourceSearchAdapter,
)
from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentRecord,
)
from app.schemas.in_memory_research_source import (
    InMemoryResearchSourceRecord,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_document import (
    ResearchSourceDocumentStatus,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)


def task_graph() -> ResearchTaskGraph:
    """Return one graph used by query-set tests."""

    return ResearchTaskGraph(
        request_id="request-001",
        tasks=[
            ResearchTask(
                task_id="task-001",
                request_id="request-001",
                title="Grounded research",
                question=(
                    "How does grounded research use evidence?"
                ),
                objective=(
                    "Explain evidence use in grounded research."
                ),
                completion_criteria=[
                    "Identify traceable evidence."
                ],
                expected_output="Supported findings.",
            )
        ],
    )


def query_set() -> ResearchSearchQuerySet:
    """Return two overlapping search queries."""

    graph = task_graph()

    return ResearchSearchQuerySet(
        request_id="request-001",
        task_graph=graph,
        queries=[
            ResearchSearchQuery(
                query_id="query-001",
                request_id="request-001",
                task_id="task-001",
                query_text="grounded research evidence",
            ),
            ResearchSearchQuery(
                query_id="query-002",
                request_id="request-001",
                task_id="task-001",
                query_text="traceable evidence research",
            ),
        ],
    )


def source_records() -> list[InMemoryResearchSourceRecord]:
    """Return searchable local-style source records."""

    return [
        InMemoryResearchSourceRecord(
            source_id="source-001",
            title="Grounded Research Evidence",
            url="https://local.aira.invalid/source/source-001",
            source_type=ResearchSourceType.OTHER,
            snippet=(
                "Grounded research connects claims to "
                "traceable evidence."
            ),
            keywords=[
                "grounded",
                "research",
                "evidence",
                "traceable",
            ],
        ),
        InMemoryResearchSourceRecord(
            source_id="source-002",
            title="Unrelated Notes",
            url="https://local.aira.invalid/source/source-002",
            source_type=ResearchSourceType.OTHER,
            snippet="Notes about an unrelated subject.",
            keywords=["unrelated", "notes"],
        ),
    ]


def document_records() -> list[
    InMemoryResearchDocumentRecord
]:
    """Return readable documents for both sources."""

    return [
        InMemoryResearchDocumentRecord(
            source_id="source-001",
            url="https://local.aira.invalid/source/source-001",
            content=(
                "Grounded research connects claims to "
                "traceable evidence."
            ),
            language="en",
        ),
        InMemoryResearchDocumentRecord(
            source_id="source-002",
            url="https://local.aira.invalid/source/source-002",
            content="Notes about an unrelated subject.",
            language="en",
        ),
    ]


def test_search_adapter_combines_query_results() -> None:
    adapter = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(
            records=source_records()
        )
    )

    candidates = adapter.search(query_set())

    assert candidates.request_id == "request-001"
    assert len(candidates.candidates) == 1
    assert candidates.candidates[0].source_id == "source-001"


def test_search_adapter_removes_duplicate_sources() -> None:
    adapter = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(
            records=source_records()
        )
    )

    candidates = adapter.search(query_set())

    source_ids = [
        candidate.source_id
        for candidate in candidates.candidates
    ]

    assert source_ids == ["source-001"]


def test_search_adapter_can_return_empty_candidate_set() -> None:
    graph = task_graph()
    queries = ResearchSearchQuerySet(
        request_id="request-001",
        task_graph=graph,
        queries=[
            ResearchSearchQuery(
                query_id="query-003",
                request_id="request-001",
                task_id="task-001",
                query_text="nonexistent terminology",
            )
        ],
    )
    adapter = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(
            records=source_records()
        )
    )

    candidates = adapter.search(queries)

    assert candidates.candidates == []


def test_reader_adapter_reads_all_candidates() -> None:
    search_adapter = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(
            records=source_records()
        )
    )
    candidate_set = search_adapter.search(query_set())
    reader_adapter = PipelineSourceReaderAdapter(
        InMemoryResearchSourceReader(
            records=document_records()
        )
    )

    documents = reader_adapter.read(candidate_set)

    assert documents.request_id == "request-001"
    assert len(documents.documents) == 1
    assert documents.documents[0].status is (
        ResearchSourceDocumentStatus.READ
    )
    assert (
        documents.documents[0].candidate.source_id
        == "source-001"
    )


def test_reader_adapter_preserves_read_failures() -> None:
    search_adapter = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(
            records=source_records()
        )
    )
    candidate_set = search_adapter.search(query_set())
    reader_adapter = PipelineSourceReaderAdapter(
        InMemoryResearchSourceReader(records=[])
    )

    documents = reader_adapter.read(candidate_set)

    assert len(documents.documents) == 1
    assert documents.documents[0].status is (
        ResearchSourceDocumentStatus.FAILED
    )
    assert documents.successful_documents() == []


def test_search_adapter_limits_total_candidates() -> None:
    records = [
        InMemoryResearchSourceRecord(
            source_id="source-001",
            title="Grounded Research Evidence One",
            url=(
                "https://local.aira.invalid/source/"
                "source-001"
            ),
            source_type=ResearchSourceType.OTHER,
            snippet=(
                "Grounded research uses traceable evidence."
            ),
            keywords=[
                "grounded",
                "research",
                "evidence",
                "traceable",
            ],
        ),
        InMemoryResearchSourceRecord(
            source_id="source-002",
            title="Grounded Research Evidence Two",
            url=(
                "https://local.aira.invalid/source/"
                "source-002"
            ),
            source_type=ResearchSourceType.OTHER,
            snippet=(
                "Traceable evidence supports grounded research."
            ),
            keywords=[
                "grounded",
                "research",
                "evidence",
                "traceable",
            ],
        ),
    ]
    adapter = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(
            records=records
        ),
        maximum_candidates=1,
    )

    candidates = adapter.search(query_set())

    assert len(candidates.candidates) == 1
    assert candidates.candidates[0].source_id == (
        "source-001"
    )


def test_search_adapter_rejects_invalid_candidate_limit() -> None:
    import pytest

    with pytest.raises(
        ValueError,
        match=(
            "maximum_candidates must be greater than zero"
        ),
    ):
        PipelineSourceSearchAdapter(
            InMemoryResearchSourceSearchTool(
                records=source_records()
            ),
            maximum_candidates=0,
        )
