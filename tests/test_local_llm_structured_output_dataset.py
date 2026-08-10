"""Tests for structured-output benchmark dataset."""

from app.evals.local_llm_structured_output_dataset import (
    StructuredOutputMode,
    evaluate_structured_output,
    response_format_for,
    structured_output_cases,
)


def test_dataset_has_three_stable_cases() -> None:
    cases = structured_output_cases()

    assert [case.case_id for case in cases] == [
        "city-temp-001",
        "service-status-001",
        "seat-schedule-001",
    ]


def test_response_modes_return_expected_format() -> None:
    case = structured_output_cases()[0]

    assert response_format_for(
        case,
        StructuredOutputMode.PROMPT_ONLY,
    ) is None
    assert response_format_for(
        case,
        StructuredOutputMode.JSON,
    ) == "json"

    schema = response_format_for(
        case,
        StructuredOutputMode.JSON_SCHEMA,
    )
    assert isinstance(schema, dict)
    assert schema["type"] == "object"


def test_exact_structured_response_passes() -> None:
    case = structured_output_cases()[0]

    score = evaluate_structured_output(
        case,
        '{"city":"서울","temperature":24}',
    )

    assert score.json_parse_passed
    assert score.schema_passed
    assert score.exact_value_passed


def test_extra_text_fails_full_json_parse() -> None:
    case = structured_output_cases()[0]

    score = evaluate_structured_output(
        case,
        '결과: {"city":"서울","temperature":24}',
    )

    assert not score.json_parse_passed
    assert not score.schema_passed
    assert not score.exact_value_passed


def test_wrong_type_fails_strict_schema() -> None:
    case = structured_output_cases()[0]

    score = evaluate_structured_output(
        case,
        '{"city":"서울","temperature":"24"}',
    )

    assert score.json_parse_passed
    assert not score.schema_passed
    assert not score.exact_value_passed
