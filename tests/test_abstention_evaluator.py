"""Tests for deterministic abstention detection."""

from app.rag.abstention_evaluator import (
    find_abstention_markers,
    is_abstention_answer,
    normalize_answer_text,
)


def test_normalize_answer_text() -> None:
    assert normalize_answer_text(
        "  근거가   부족합니다.\n"
    ) == "근거가 부족합니다."


def test_detects_korean_abstention_marker() -> None:
    answer = (
        "제공된 근거만으로는 해당 질문에 "
        "답변할 수 없습니다."
    )

    matches = find_abstention_markers(
        answer_text=answer,
        markers=[
            "근거만으로는",
            "답변할 수 없",
        ],
    )

    assert matches == [
        "근거만으로는",
        "답변할 수 없",
    ]


def test_detects_english_marker_case_insensitively() -> None:
    assert is_abstention_answer(
        answer_text=(
            "There is NOT ENOUGH INFORMATION "
            "to answer this question."
        ),
        markers=["not enough information"],
    )


def test_regular_answer_is_not_abstention() -> None:
    assert not is_abstention_answer(
        answer_text="파이썬을 사용할 수 있습니다.",
        markers=["근거가 부족", "답변할 수 없"],
    )


def test_blank_marker_is_ignored() -> None:
    matches = find_abstention_markers(
        answer_text="일반적인 답변입니다.",
        markers=["", "   "],
    )

    assert matches == []
