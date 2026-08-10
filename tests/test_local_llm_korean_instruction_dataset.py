"""Tests for Korean instruction-following dataset and scoring."""

from app.evals.local_llm_korean_instruction_dataset import (
    evaluate_korean_instruction_response,
    korean_instruction_cases,
)


def case_by_id(case_id: str):
    return next(
        case
        for case in korean_instruction_cases()
        if case.case_id == case_id
    )


def test_dataset_has_stable_unique_cases() -> None:
    cases = korean_instruction_cases()

    assert len(cases) == 8
    assert len({case.case_id for case in cases}) == len(cases)
    assert [case.case_id for case in cases] == [
        "exact-001",
        "extract-001",
        "order-001",
        "lines-001",
        "transform-001",
        "selection-001",
        "format-001",
        "negative-001",
    ]


def test_exact_case_passes_only_exact_output() -> None:
    case = case_by_id("exact-001")

    assert evaluate_korean_instruction_response(
        case,
        "작업 완료",
    ).passed
    assert not evaluate_korean_instruction_response(
        case,
        "완료했습니다. 작업 완료",
    ).passed


def test_two_line_case_enforces_structure() -> None:
    case = case_by_id("lines-001")

    passing = evaluate_korean_instruction_response(
        case,
        "상태: 정상\n재시도: 0",
    )
    failing = evaluate_korean_instruction_response(
        case,
        "1. 상태: 정상\n2. 재시도: 0",
    )

    assert passing.passed
    assert passing.checks_passed == passing.checks_total
    assert not failing.passed


def test_korean_only_case_rejects_english_letters() -> None:
    case = case_by_id("negative-001")

    assert evaluate_korean_instruction_response(
        case,
        "시스템 상태는 안정적입니다.",
    ).passed

    score = evaluate_korean_instruction_response(
        case,
        "시스템 상태는 stable입니다.",
    )
    assert not score.passed
