"""Tests for research source search result schemas."""

import pytest
from pydantic import ValidationError

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
    ResearchSourceSearchError,
    ResearchSourceSearchResult,
    ResearchSourceSearchStatus,
)


def query() -> ResearchSearchQuery:
    """Return one valid search query."""

    return ResearchSearchQuery(
        query_id="query-001",
        request_id="research-001",
        task_id="task-001",
        query_text="agent memory architecture",
    )


def candidate(
    *,
    source_id: str = "source-001",
    rank: int = 1,
    url: str = "https://example.com/source",
    request_id: str = "research-001",
    task_id: str = "task-001",
    query_id: str = "query-001",
) -> ResearchSourceCandidate:
    """Return one valid search candidate."""

    return ResearchSourceCandidate(
        source_id=source_id,
        request_id=request_id,
        task_id=task_id,
        query_id=query_id,
        title="Agent memory architecture",
        url=url,
        source_type=(
            ResearchSourceType.PRIMARY_RESEARCH
        ),
        rank=rank,
    )


def error() -> ResearchSourceSearchError:
    """Return one valid search error."""

    return ResearchSourceSearchError(
        error_type="ProviderUnavailable",
        message="Search provider is unavailable.",
        retryable=True,
    )


def test_succeeded_result_accepts_candidates() -> None:
    result = ResearchSourceSearchResult(
        query=query(),
        status=ResearchSourceSearchStatus.SUCCEEDED,
        provider="in-memory",
        candidates=[candidate()],
        duration_ms=12,
    )

    assert len(result.candidates) == 1
    assert result.error is None


def test_no_results_accepts_empty_candidates() -> None:
    result = ResearchSourceSearchResult(
        query=query(),
        status=ResearchSourceSearchStatus.NO_RESULTS,
        provider="in-memory",
        candidates=[],
        duration_ms=5,
    )

    assert result.candidates == []
    assert result.error is None


def test_failed_result_requires_error() -> None:
    result = ResearchSourceSearchResult(
        query=query(),
        status=ResearchSourceSearchStatus.FAILED,
        provider="in-memory",
        candidates=[],
        error=error(),
        duration_ms=3,
    )

    assert result.error is not None
    assert result.error.retryable is True


def test_succeeded_result_requires_candidate() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "succeeded search must contain "
            "at least one candidate"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider="in-memory",
            candidates=[],
            duration_ms=1,
        )


def test_succeeded_result_rejects_error() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "succeeded search must not contain an error"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider="in-memory",
            candidates=[candidate()],
            error=error(),
            duration_ms=1,
        )


def test_no_results_rejects_candidates() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "no-results search must not "
            "contain candidates"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.NO_RESULTS
            ),
            provider="in-memory",
            candidates=[candidate()],
            duration_ms=1,
        )


def test_failed_result_requires_structured_error() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed search must contain an error"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=ResearchSourceSearchStatus.FAILED,
            provider="in-memory",
            candidates=[],
            duration_ms=1,
        )


def test_failed_result_rejects_candidates() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed search must not contain candidates"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=ResearchSourceSearchStatus.FAILED,
            provider="in-memory",
            candidates=[candidate()],
            error=error(),
            duration_ms=1,
        )


def test_result_rejects_candidate_request_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "candidate request_id must match"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider="in-memory",
            candidates=[
                candidate(request_id="research-002")
            ],
            duration_ms=1,
        )


def test_result_rejects_candidate_task_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "candidate task_id must match"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider="in-memory",
            candidates=[
                candidate(task_id="task-002")
            ],
            duration_ms=1,
        )


def test_result_rejects_candidate_query_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "candidate query_id must match"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider="in-memory",
            candidates=[
                candidate(query_id="query-002")
            ],
            duration_ms=1,
        )


def test_result_rejects_duplicate_source_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "search result source IDs must be unique"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider="in-memory",
            candidates=[
                candidate(
                    source_id="source-001",
                    rank=1,
                ),
                candidate(
                    source_id=" SOURCE-001 ",
                    rank=2,
                    url="https://example.org/other",
                ),
            ],
            duration_ms=1,
        )


def test_result_rejects_duplicate_urls() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "candidate URLs must be unique"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider="in-memory",
            candidates=[
                candidate(
                    source_id="source-001",
                    rank=1,
                    url="https://example.com/source/",
                ),
                candidate(
                    source_id="source-002",
                    rank=2,
                    url=(
                        "HTTPS://EXAMPLE.COM:443/source"
                    ),
                ),
            ],
            duration_ms=1,
        )


def test_result_rejects_duplicate_ranks() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "candidate ranks must be unique"
        ),
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider="in-memory",
            candidates=[
                candidate(
                    source_id="source-001",
                    rank=1,
                ),
                candidate(
                    source_id="source-002",
                    rank=1,
                    url="https://example.org/other",
                ),
            ],
            duration_ms=1,
        )


def test_result_rejects_blank_provider() -> None:
    with pytest.raises(
        ValidationError,
        match="provider must not be blank",
    ):
        ResearchSourceSearchResult(
            query=query(),
            status=(
                ResearchSourceSearchStatus.NO_RESULTS
            ),
            provider=" ",
            duration_ms=1,
        )


def test_error_rejects_blank_values() -> None:
    with pytest.raises(
        ValidationError,
        match="error_type must not be blank",
    ):
        ResearchSourceSearchError(
            error_type=" ",
            message="Failure.",
        )

    with pytest.raises(
        ValidationError,
        match="message must not be blank",
    ):
        ResearchSourceSearchError(
            error_type="Failure",
            message=" ",
        )
