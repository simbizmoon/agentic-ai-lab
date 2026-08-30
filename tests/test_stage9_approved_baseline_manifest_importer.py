"""Offline tests for the repository-approved Stage 9 baseline lock."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_REVIEW_SHA256,
    ApprovedBaselineImportError,
    load_approved_baseline,
)
from app.schemas.stage9_baseline_runtime_stack import (
    Stage9RuntimeComponentRole,
)

DIRECTORY = Path("evals/manifests/stage9/stage9-single-agent-baseline-live-v1")
MANIFEST = DIRECTORY / "approved-live-baseline.json"
REVIEW = DIRECTORY / "runtime-budget-review.md"


def test_repository_lock_imports_with_exact_approval_and_runtime() -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    assert experiment.plan.planned_case_executions == 10
    assert len(experiment.plan.development_case_ids) == 4
    assert len(experiment.plan.blind_holdout_case_ids) == 6
    assert {item.model_name for item in experiment.runtime_stack.components} == {
        "gpt-5.6-terra"
    }
    assert (
        experiment.runtime_stack.component(
            Stage9RuntimeComponentRole.PLANNER
        ).reasoning_effort
        == "low"
    )


def test_expected_hashes_are_explicit_and_stable() -> None:
    assert EXPECTED_MANIFEST_SHA256 == (
        "60179543f5290136d434d4f4c72598af8f74eb569a1d06b43c7490320d81e191"
    )
    assert EXPECTED_REVIEW_SHA256 == (
        "f36c0b7bee7cc9548f2f3a36946e4b49293883b69349b4499f2c80d27190cae7"
    )


def test_tampered_manifest_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / MANIFEST.name
    manifest.write_bytes(MANIFEST.read_bytes() + b"\n")
    Path(str(manifest) + ".sha256").write_bytes(
        Path(str(MANIFEST) + ".sha256").read_bytes()
    )
    with pytest.raises(ApprovedBaselineImportError, match="checksum"):
        load_approved_baseline(manifest, REVIEW)


def test_tampered_review_is_rejected(tmp_path: Path) -> None:
    review = tmp_path / REVIEW.name
    review.write_bytes(REVIEW.read_bytes() + b"\n")
    with pytest.raises(ApprovedBaselineImportError, match="review checksum"):
        load_approved_baseline(MANIFEST, review)
