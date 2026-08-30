"""Offline tests for the final Stage 9 development execution bundle."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_REVIEW_SHA256,
    load_approved_baseline,
)
from app.evals.stage9_development_execution_bundle import (
    Stage9DevelopmentExecutionBundle,
    create_stage9_development_execution_bundle,
)
from app.schemas.stage9_development_baseline_run import (
    STAGE9_DEVELOPMENT_CASE_IDS,
)

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)


class NoCallResearchLoop:
    def run(self, *, request):
        raise AssertionError(f"paid research execution was not expected: {request}")


def test_composes_exact_approved_development_request_without_execution(
    tmp_path: Path,
) -> None:
    output = tmp_path / "artifacts"
    bundle = create_stage9_development_execution_bundle(
        experiment=load_approved_baseline(MANIFEST, REVIEW),
        research_loop=NoCallResearchLoop(),
        output_directory=output,
        run_id="stage9-development-live-001",
    )

    assert isinstance(bundle, Stage9DevelopmentExecutionBundle)
    assert bundle.request.case_ids == STAGE9_DEVELOPMENT_CASE_IDS
    assert bundle.request.manifest_sha256 == EXPECTED_MANIFEST_SHA256
    assert bundle.request.review_sha256 == EXPECTED_REVIEW_SHA256
    assert bundle.request.allow_blind_holdout is False
    assert bundle.request.budget.maximum_provider_requests == 16
    assert bundle.request.budget.maximum_external_requests == 24
    assert bundle.request.budget.maximum_recorded_tokens == 120_000
    assert bundle.request.budget.maximum_elapsed_seconds == 2_880.0
    assert bundle.request.budget.maximum_estimated_cost == Decimal("1.50")
    assert not output.exists()


@pytest.mark.parametrize(
    "run_id",
    ["", " leading", "contains/slash", "contains space"],
)
def test_rejects_unsafe_run_identity_before_any_execution(
    tmp_path: Path,
    run_id: str,
) -> None:
    with pytest.raises(ValueError, match="filesystem-safe"):
        create_stage9_development_execution_bundle(
            experiment=load_approved_baseline(MANIFEST, REVIEW),
            research_loop=NoCallResearchLoop(),
            output_directory=tmp_path,
            run_id=run_id,
        )


def test_rejects_symbolic_link_output_before_any_execution(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        create_stage9_development_execution_bundle(
            experiment=load_approved_baseline(MANIFEST, REVIEW),
            research_loop=NoCallResearchLoop(),
            output_directory=link,
            run_id="stage9-development-live-001",
        )
