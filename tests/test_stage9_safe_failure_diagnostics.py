"""Offline tests for secret-safe Stage 9 failure classification."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.evals.stage9_bounded_development_baseline_runner import (
    BoundedStage9DevelopmentBaselineRunner,
    Stage9DevelopmentCaseExecutionError,
)
from app.evals.stage9_safe_failure_diagnostics import safe_stage9_failure_code
from app.schemas.stage9_development_baseline_run import (
    STAGE9_DEVELOPMENT_CASE_IDS,
    Stage9DevelopmentRunBudget,
    Stage9DevelopmentRunRequest,
)

DIRECTORY = Path("evals/manifests/stage9/stage9-single-agent-baseline-live-v1")
MANIFEST = DIRECTORY / "approved-live-baseline.json"
REVIEW = DIRECTORY / "runtime-budget-review.md"


def _chained_error(inner_name: str, secret: str) -> RuntimeError:
    inner_type = type(inner_name, (RuntimeError,), {})
    try:
        raise inner_type(secret)
    except RuntimeError as inner:
        try:
            raise RuntimeError("middle message") from inner
        except RuntimeError as middle:
            return Stage9DevelopmentCaseExecutionError("outer message").with_traceback(
                middle.__traceback__
            )


class FailingExecutor:
    def execute(self, *, case_id, request):
        del case_id, request
        inner_type = type("BadRequestError", (RuntimeError,), {})
        try:
            raise inner_type("secret-provider-payload")
        except RuntimeError as inner:
            raise Stage9DevelopmentCaseExecutionError("safe wrapper") from inner


def _request() -> Stage9DevelopmentRunRequest:
    return Stage9DevelopmentRunRequest(
        run_id="stage9-diagnostic-offline-001",
        manifest_sha256=(
            "60179543f5290136d434d4f4c72598af8f74eb569a1d06b43c7490320d81e191"
        ),
        review_sha256=(
            "f36c0b7bee7cc9548f2f3a36946e4b49293883b69349b4499f2c80d27190cae7"
        ),
        case_ids=STAGE9_DEVELOPMENT_CASE_IDS,
        repetitions_per_case=1,
        budget=Stage9DevelopmentRunBudget(
            maximum_provider_requests=16,
            maximum_external_requests=24,
            maximum_recorded_tokens=120_000,
            maximum_elapsed_seconds=2_880.0,
            maximum_estimated_cost=Decimal("1.50"),
            currency="USD",
        ),
    )


def test_classifies_known_provider_type_without_retaining_message() -> None:
    secret = "sk-never-retain-this"
    error_type = type("AuthenticationError", (RuntimeError,), {})
    error = error_type(secret)

    code = safe_stage9_failure_code(error)

    assert code == "provider_authentication_failed"
    assert secret not in code


def test_classifies_stage9_runtime_boundaries_without_retaining_messages() -> None:
    cases = {
        "Stage9TavilyTimeoutError": "official_web_provider_timeout",
        "Stage9TavilyConnectionError": "official_web_provider_connection_failed",
        "Stage9TavilyHttpStatusError": "official_web_provider_http_failed",
        "Stage9TavilyResponseValidationError": (
            "official_web_provider_response_invalid"
        ),
        "Stage9TavilyRawContentUnavailableError": (
            "official_web_raw_content_unavailable"
        ),
        "Stage9TavilyBoundaryError": "official_web_provider_boundary_failed",
        "Stage9TavilyOfficialWebProviderError": "official_web_provider_failed",
        "Stage9OfficialWebAcquisitionError": "official_web_evidence_invalid",
        "Stage9DevelopmentAcquisitionRouterError": "acquisition_routing_failed",
        "Stage9AcquisitionAwareResearchLoopError": "acquisition_loop_failed",
        "Stage9PackedResearchLoopFactoryError": "packed_loop_composition_failed",
        "Stage9DevelopmentCaseArtifactError": "artifact_persistence_failed",
        "Stage9ConservativeCostEstimationError": "cost_estimation_failed",
        "ValidationError": "contract_validation_failed",
    }
    secret = "secret-runtime-payload"

    for class_name, expected in cases.items():
        error_type = type(class_name, (RuntimeError,), {})
        error = error_type(secret)
        code = safe_stage9_failure_code(error)

        assert code == expected
        assert secret not in code


def test_specific_inner_failure_wins_over_generic_outer_failure() -> None:
    inner_type = type("Stage9OfficialWebAcquisitionError", (RuntimeError,), {})
    outer_type = type("Stage9AcquisitionAwareResearchLoopError", (RuntimeError,), {})
    try:
        raise inner_type("secret-inner-message")
    except RuntimeError as inner:
        try:
            raise outer_type("safe outer message") from inner
        except RuntimeError as outer:
            error = outer

    assert safe_stage9_failure_code(error) == "official_web_evidence_invalid"


def test_patched_runner_persists_only_safe_failure_code() -> None:
    runner = BoundedStage9DevelopmentBaselineRunner(
        experiment=load_approved_baseline(MANIFEST, REVIEW),
        executor=FailingExecutor(),
    )

    result = runner.run(_request())

    assert result.stop_reason == "case executor failed safely: provider_bad_request"
    assert "secret-provider-payload" not in result.stop_reason
