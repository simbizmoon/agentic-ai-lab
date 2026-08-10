"""Tests for the verified local LLM reasoning dataset."""

from app.evals.local_llm_reasoning_dataset import (
    reasoning_cases,
    verify_reasoning_dataset,
)


def test_every_reasoning_case_has_verified_unique_answer() -> None:
    cases = reasoning_cases()
    verified = verify_reasoning_dataset()

    assert len(cases) == 5
    assert set(verified) == {case.case_id for case in cases}

    for case in cases:
        assert verified[case.case_id] == case.expected_answer


def test_expected_answer_is_not_leaked_as_final_answer() -> None:
    for case in reasoning_cases():
        leaked = f"정답: {case.expected_answer}"
        assert leaked not in case.prompt
