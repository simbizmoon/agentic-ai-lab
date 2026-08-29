"""Offline tests for the human-locked Stage 9 dataset importer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evals.stage9_locked_dataset_importer import (
    DEVELOPMENT_IDS,
    EXPECTED_CASE_IDS,
    LockedDatasetImportError,
    _build_case,
    _verify_input,
    run,
)
from app.schemas.stage9_evaluation_manifest import Stage9DatasetPartition

DATASET = Path("evals/datasets/stage9/stage9-locked-golden-dataset-v1.json")


def test_locked_dataset_checksum_and_order_are_verified() -> None:
    value = _verify_input(DATASET)
    assert (
        value["dataset_sha256"]
        == "9405c96ec598c89ba2d7097dea61d01a9485c7f71a5bb4ac872da728999d0b2a"
    )
    assert tuple(value["case_order"]) == EXPECTED_CASE_IDS


def test_all_cases_import_through_existing_typed_contract() -> None:
    source = _verify_input(DATASET)
    cases = tuple(_build_case(item) for item in source["cases"])
    assert len(cases) == 10
    assert {
        case.definition.case_id
        for case in cases
        if case.partition is Stage9DatasetPartition.DEVELOPMENT
    } == DEVELOPMENT_IDS
    assert all(case.human_review_required for case in cases)
    assert all(
        evidence.semantic_match_allowed is False
        for case in cases
        for evidence in case.definition.expected_outcome.expected_evidence
    )


def test_derived_artifact_preserves_split_and_source_hash(tmp_path: Path) -> None:
    output = run(DATASET, tmp_path)
    value = json.loads(output.read_text(encoding="utf-8"))
    assert len(value["development_case_ids"]) == 4
    assert len(value["locked_holdout_case_ids"]) == 6
    assert (
        value["source_dataset_sha256"]
        == "9405c96ec598c89ba2d7097dea61d01a9485c7f71a5bb4ac872da728999d0b2a"
    )
    assert (
        value["manifest_status"]
        == "runtime_provider_model_price_and_budget_not_yet_locked"
    )


def test_tampered_file_is_rejected_before_import(tmp_path: Path) -> None:
    target = tmp_path / DATASET.name
    target.write_bytes(DATASET.read_bytes() + b"\n")
    Path(str(target) + ".sha256").write_text(
        Path(str(DATASET) + ".sha256").read_text(encoding="ascii"), encoding="ascii"
    )
    with pytest.raises(LockedDatasetImportError, match="checksum"):
        _verify_input(target)
