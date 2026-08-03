"""Tests for memory-augmented prompt schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.memory_prompt import (
    MemoryAugmentedPrompt,
    PromptMessage,
    PromptRole,
)


def messages() -> list[PromptMessage]:
    """Return one valid system-user message pair."""

    return [
        PromptMessage(
            role=PromptRole.SYSTEM,
            content="System instructions.",
        ),
        PromptMessage(
            role=PromptRole.USER,
            content="User request.",
        ),
    ]


def test_prompt_accepts_valid_messages() -> None:
    prompt = MemoryAugmentedPrompt(
        messages=messages(),
        memory_ids=["mem-001"],
        memory_used=True,
    )

    assert prompt.messages[0].role is PromptRole.SYSTEM
    assert prompt.messages[1].role is PromptRole.USER


def test_message_rejects_blank_content() -> None:
    with pytest.raises(
        ValidationError,
        match="content",
    ):
        PromptMessage(
            role=PromptRole.USER,
            content=" ",
        )


def test_prompt_rejects_reversed_roles() -> None:
    with pytest.raises(
        ValidationError,
        match="ordered system then user",
    ):
        MemoryAugmentedPrompt(
            messages=[
                PromptMessage(
                    role=PromptRole.USER,
                    content="User request.",
                ),
                PromptMessage(
                    role=PromptRole.SYSTEM,
                    content="System instructions.",
                ),
            ],
            memory_ids=[],
            memory_used=False,
        )


def test_prompt_rejects_duplicate_memory_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="must be unique",
    ):
        MemoryAugmentedPrompt(
            messages=messages(),
            memory_ids=[
                "mem-001",
                "mem-001",
            ],
            memory_used=True,
        )


def test_prompt_rejects_inconsistent_memory_flag() -> None:
    with pytest.raises(
        ValidationError,
        match="memory_used is inconsistent",
    ):
        MemoryAugmentedPrompt(
            messages=messages(),
            memory_ids=["mem-001"],
            memory_used=False,
        )


def test_prompt_without_memory_is_valid() -> None:
    prompt = MemoryAugmentedPrompt(
        messages=messages(),
        memory_ids=[],
        memory_used=False,
    )

    assert prompt.memory_used is False
