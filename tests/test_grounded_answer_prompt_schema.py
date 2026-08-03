"""Tests for grounded answer prompt schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.grounded_answer_prompt import (
    GroundedAnswerPrompt,
)
from app.schemas.rag_context import (
    RagCitation,
    RagContext,
)


def context_with_citation() -> RagContext:
    """Return one grounded context block."""

    return RagContext(
        context_text="[S1]\nRelevant evidence.",
        citations=[
            RagCitation(
                citation_id="S1",
                document_id="doc-1",
                chunk_id="doc-1:chunk:0000",
                rank=1,
                score=0.9,
                start_char=0,
                end_char=18,
                source="sample.txt",
            )
        ],
    )


def test_grounded_prompt_accepts_valid_data() -> None:
    prompt = GroundedAnswerPrompt(
        system_instructions="Use only supplied evidence.",
        user_prompt=(
            "Question: What is relevant?\n"
            "Evidence: [S1] Relevant evidence."
        ),
        question="What is relevant?",
        context=context_with_citation(),
    )

    assert prompt.question == "What is relevant?"
    assert "[S1]" in prompt.user_prompt


@pytest.mark.parametrize(
    "question",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_grounded_prompt_rejects_blank_question(
    question: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="question must not be blank",
    ):
        GroundedAnswerPrompt(
            system_instructions="Use the evidence.",
            user_prompt="[S1] Evidence.",
            question=question,
            context=context_with_citation(),
        )


def test_grounded_prompt_rejects_missing_citation_marker() -> None:
    with pytest.raises(
        ValidationError,
        match="include every citation marker",
    ):
        GroundedAnswerPrompt(
            system_instructions="Use the evidence.",
            user_prompt="Evidence without its marker.",
            question="What is relevant?",
            context=context_with_citation(),
        )


def test_grounded_prompt_allows_empty_context() -> None:
    prompt = GroundedAnswerPrompt(
        system_instructions="Use only supplied evidence.",
        user_prompt="No evidence was retrieved.",
        question="What is unknown?",
        context=RagContext(
            context_text="",
            citations=[],
        ),
    )

    assert prompt.context.citations == []


def test_grounded_prompt_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        GroundedAnswerPrompt(
            system_instructions="Use the evidence.",
            user_prompt="[S1] Evidence.",
            question="What is relevant?",
            context=context_with_citation(),
            unknown_field="not allowed",
        )
