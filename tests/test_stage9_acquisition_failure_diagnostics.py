"""Offline tests for safe Stage 9 acquisition failure propagation."""

from __future__ import annotations

import pytest

from app.evals.stage9_bounded_development_baseline_runner import (
    Stage9DevelopmentCaseExecutionError,
)
from app.evals.stage9_safe_failure_diagnostics import safe_stage9_failure_code
from app.research.stage9_acquisition_aware_research_loop import (
    Stage9AcquisitionAwareResearchLoopError,
)


@pytest.mark.parametrize(
    ("provider_code", "expected"),
    [
        ("ProviderTimeout", "acquisition_provider_timeout"),
        ("ProviderNetworkError", "acquisition_provider_connection_failed"),
        ("ProviderHttpError", "acquisition_provider_http_failed"),
        ("ResponseValidationError", "acquisition_provider_response_invalid"),
    ],
)
def test_safe_acquisition_failure_code_survives_wrapping(
    provider_code: str, expected: str
) -> None:
    try:
        raise Stage9AcquisitionAwareResearchLoopError(
            "development acquisition failed safely",
            failure_code=provider_code,
        )
    except Stage9AcquisitionAwareResearchLoopError as inner:
        outer = Stage9DevelopmentCaseExecutionError("case failed safely")
        outer.__cause__ = inner

    assert safe_stage9_failure_code(outer) == expected


def test_unknown_acquisition_code_does_not_leak() -> None:
    error = Stage9AcquisitionAwareResearchLoopError(
        "secret provider detail must not be persisted",
        failure_code="UnexpectedSecretDetail",
    )

    assert safe_stage9_failure_code(error) == "acquisition_loop_failed"
