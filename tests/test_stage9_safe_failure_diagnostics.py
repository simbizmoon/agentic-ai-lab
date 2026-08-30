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


def test_patched_runner_persists_only_safe_failure_code() -> None:
    runner = BoundedStage9DevelopmentBaselineRunner(
        experiment=load_approved_baseline(MANIFEST, REVIEW),
        executor=FailingExecutor(),
    )

    result = runner.run(_request())

    assert result.stop_reason == "case executor failed safely: provider_bad_request"
    assert "secret-provider-payload" not in result.stop_reason
