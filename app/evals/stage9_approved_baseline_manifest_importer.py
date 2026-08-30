"""Offline verification of the repository-approved Stage 9 baseline lock."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.schemas.stage9_baseline_runtime_stack import (
    Stage9LockedBaselineExperiment,
)

EXPECTED_MANIFEST_SHA256 = (
    "60179543f5290136d434d4f4c72598af8f74eb569a1d06b43c7490320d81e191"
)
EXPECTED_REVIEW_SHA256 = (
    "f36c0b7bee7cc9548f2f3a36946e4b49293883b69349b4499f2c80d27190cae7"
)


class ApprovedBaselineImportError(ValueError):
    """The approved baseline lock is missing, changed, or inconsistent."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ApprovedBaselineImportError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_approved_baseline(
    manifest_path: Path,
    review_path: Path,
) -> Stage9LockedBaselineExperiment:
    """Verify exact bytes, approval evidence, and the complete typed experiment."""

    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != EXPECTED_MANIFEST_SHA256:
        raise ApprovedBaselineImportError("approved manifest checksum mismatch")

    checksum_path = Path(str(manifest_path) + ".sha256")
    checksum_fields = checksum_path.read_text(encoding="ascii").split()
    if checksum_fields != [EXPECTED_MANIFEST_SHA256, manifest_path.name]:
        raise ApprovedBaselineImportError("manifest checksum sidecar mismatch")

    review_sha256 = hashlib.sha256(review_path.read_bytes()).hexdigest()
    if review_sha256 != EXPECTED_REVIEW_SHA256:
        raise ApprovedBaselineImportError("human review checksum mismatch")

    wrapper = json.loads(
        manifest_bytes,
        object_pairs_hook=_reject_duplicate_keys,
    )
    if wrapper.get("lock_version") != "1.0.0":
        raise ApprovedBaselineImportError("unsupported approved lock version")
    approval = wrapper.get("approval")
    if not isinstance(approval, dict):
        raise ApprovedBaselineImportError("approved lock has no approval record")
    if approval.get("review_sha256") != review_sha256:
        raise ApprovedBaselineImportError("manifest and human review are not linked")
    if approval.get("reviewer_id") != "moon":
        raise ApprovedBaselineImportError("unexpected reviewer identity")
    if approval.get("reviewed_at") != "2026-08-30T09:21:35+09:00":
        raise ApprovedBaselineImportError("unexpected review timestamp")

    experiment = Stage9LockedBaselineExperiment.model_validate_json(
        json.dumps(wrapper.get("experiment"), ensure_ascii=False)
    )
    if experiment.plan.manifest.manifest_id != "stage9-single-agent-baseline-live-v1":
        raise ApprovedBaselineImportError("unexpected live manifest identity")
    if experiment.plan.planned_case_executions != 10:
        raise ApprovedBaselineImportError("approved plan must contain ten executions")
    return experiment
