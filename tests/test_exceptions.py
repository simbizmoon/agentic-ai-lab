from app.exceptions import (
    AgenticAILabError,
    StructuredAnalysisError,
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)


def test_structured_analysis_error_inherits_from_project_error() -> None:
    assert issubclass(StructuredAnalysisError, AgenticAILabError)


def test_concrete_structured_analysis_errors_inherit_from_base_error() -> None:
    for exception_type in (
        StructuredResponseIncompleteError,
        StructuredResponseRefusalError,
        StructuredResponseParseError,
        StructuredResponseStatusError,
        StructuredResponseValidationError,
    ):
        assert issubclass(exception_type, StructuredAnalysisError)


def test_concrete_structured_analysis_errors_are_distinct_classes() -> None:
    exception_types = {
        StructuredResponseIncompleteError,
        StructuredResponseRefusalError,
        StructuredResponseParseError,
        StructuredResponseStatusError,
        StructuredResponseValidationError,
    }

    assert len(exception_types) == 5


def test_structured_response_validation_error_stores_default_metadata() -> None:
    error = StructuredResponseValidationError(
        "validation failed",
        elapsed_seconds=0.25,
    )

    assert str(error) == "validation failed"
    assert error.elapsed_seconds == 0.25
    assert error.attempts == 1


def test_structured_response_validation_error_stores_attempt_count() -> None:
    error = StructuredResponseValidationError(
        "validation failed",
        elapsed_seconds=0.75,
        attempts=2,
    )

    assert error.elapsed_seconds == 0.75
    assert error.attempts == 2
