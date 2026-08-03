"""Tests for agent memory pipeline result schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.agent_memory_pipeline_result import (
    AgentMemoryPipelineResult,
)
from app.schemas.memory_context import (
    MemoryContext,
    MemoryContextItem,
)
from app.schemas.memory_prompt import (
    MemoryAugmentedPrompt,
    PromptMessage,
    PromptRole,
)
from app.schemas.memory_record import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)
from app.schemas.memory_retrieval_result import (
    MemoryRetrievalResult,
)
from app.schemas.memory_search_result import (
    MemoryScoreBreakdown,
    MemorySearchResult,
)

NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)


def search_result(
    memory_id: str,
) -> MemorySearchResult:
    """Return one valid memory search result."""

    memory = MemoryRecord(
        memory_id=memory_id,
        kind=MemoryKind.SEMANTIC,
        scope=MemoryScope.USER,
        source=MemorySource.USER_STATEMENT,
        content="The user prefers verified commands.",
        subject_id="user-001",
        importance=0.8,
        confidence=1.0,
        created_at=NOW,
        updated_at=NOW,
    )

    return MemorySearchResult(
        memory=memory,
        score=0.8,
        matched_terms=["commands"],
        breakdown=MemoryScoreBreakdown(
            content_overlap=1.0,
            tag_overlap=0.0,
            phrase_match=0.0,
            importance=0.8,
            confidence=1.0,
        ),
    )


def retrieval(
    memory_id: str,
) -> MemoryRetrievalResult:
    """Return retrieval containing one memory."""

    return MemoryRetrievalResult(
        search_results=[search_result(memory_id)],
        context=MemoryContext(
            query="verified commands",
            items=[
                MemoryContextItem(
                    memory_id=memory_id,
                    content=(
                        "The user prefers verified commands."
                    ),
                    score=0.8,
                )
            ],
            rendered_text="<memory_context />",
        ),
        retrieved_memory_ids=[memory_id],
        access_recorded=False,
    )


def prompt(
    memory_id: str,
) -> MemoryAugmentedPrompt:
    """Return prompt referencing one memory."""

    return MemoryAugmentedPrompt(
        messages=[
            PromptMessage(
                role=PromptRole.SYSTEM,
                content="System instructions.",
            ),
            PromptMessage(
                role=PromptRole.USER,
                content="User request.",
            ),
        ],
        memory_ids=[memory_id],
        memory_used=True,
    )


def test_result_accepts_matching_memory_ids() -> None:
    result = AgentMemoryPipelineResult(
        retrieval=retrieval("mem-001"),
        prompt=prompt("mem-001"),
    )

    assert result.prompt.memory_ids == [
        "mem-001"
    ]


def test_result_rejects_mismatched_memory_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="memory IDs must match",
    ):
        AgentMemoryPipelineResult(
            retrieval=retrieval("mem-001"),
            prompt=prompt("mem-002"),
        )


def test_result_rejects_prompt_memory_for_empty_retrieval() -> None:
    empty_retrieval = MemoryRetrievalResult(
        search_results=[],
        context=MemoryContext(
            query="unknown",
            items=[],
            rendered_text="<memory_context />",
        ),
        retrieved_memory_ids=[],
        access_recorded=False,
    )

    invalid_prompt = MemoryAugmentedPrompt(
        messages=[
            PromptMessage(
                role=PromptRole.SYSTEM,
                content="System instructions.",
            ),
            PromptMessage(
                role=PromptRole.USER,
                content="User request.",
            ),
        ],
        memory_ids=["mem-001"],
        memory_used=True,
    )

    with pytest.raises(
        ValidationError,
        match="memory IDs must match",
    ):
        AgentMemoryPipelineResult(
            retrieval=empty_retrieval,
            prompt=invalid_prompt,
        )
