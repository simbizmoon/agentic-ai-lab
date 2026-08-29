"""Offline tests for immutable Stage 9 baseline manifest persistence."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.evals.stage9_baseline_manifest_builder import (
    Stage9BaselineManifestBuilder,
    Stage9BaselineManifestSettings,
)
from app.evals.stage9_baseline_manifest_writer import (
    STAGE9_MANIFEST_DIRECTORY_MODE,
    STAGE9_MANIFEST_FILE_MODE,
    Stage9BaselineManifestStorageError,
    Stage9BaselineManifestWriter,
)
from app.schemas.monetary_cost_budget import MonetaryCostBudget
from app.schemas.provider_cost import ModelPriceEntry, PriceRate, UsageUnit
from app.schemas.stage9_baseline_experiment_protocol import (
    Stage9ExecutionProtocol,
    Stage9OperationalBudget,
)
from app.schemas.stage9_evaluation_manifest import (
    HumanReviewDimension,
    Stage9HumanReviewCriterion,
    Stage9HumanReviewRubric,
)

DATASET = Path("evals/datasets/stage9/stage9-locked-golden-dataset-v1.json")


def _plan():
    price = ModelPriceEntry(
        price_entry_id="offline-writer-test-price",
        registry_version="offline-writer-test-registry-v1",
        provider_name="Offline Writer Test Provider",
        model_name="offline-writer-test-model",
        operation="grounded_answer",
        effective_from=date(2026, 8, 1),
        effective_through=date(2026, 8, 31),
        source_reference="offline fixture; not current pricing",
        rates=(
            PriceRate(
                usage_unit=UsageUnit.TOTAL_TOKEN,
                unit_size=Decimal(1_000_000),
                rate_amount=Decimal("1.00"),
                currency="USD",
            ),
        ),
    )
    rubric = Stage9HumanReviewRubric(
        rubric_id="stage9-writer-test-rubric-v1",
        version="1.0.0",
        criteria=tuple(
            Stage9HumanReviewCriterion(
                criterion_id=dimension.value,
                dimension=dimension,
                question=f"Score {dimension.value} from one to five.",
                minimum_score=4,
                blocking=dimension is HumanReviewDimension.CORRECTNESS,
            )
            for dimension in HumanReviewDimension
        ),
    )
    settings = Stage9BaselineManifestSettings(
        manifest_id="stage9-writer-test-manifest-v1",
        manifest_version="1.0.0",
        system_profile_id="stage9-writer-test-profile-v1",
        price_entry=price,
        pricing_date=date(2026, 8, 30),
        repetitions_per_case=1,
        monetary_budget=MonetaryCostBudget(
            currency="USD", maximum_execution_cost=Decimal("1.00")
        ),
        operational_budget=Stage9OperationalBudget(
            maximum_provider_requests=10,
            maximum_external_requests=10,
            maximum_recorded_tokens=100_000,
            maximum_elapsed_seconds=3_600.0,
        ),
        protocol=Stage9ExecutionProtocol(
            protocol_id="stage9-writer-test-protocol-v1",
            protocol_version="1.0.0",
        ),
        human_review_rubric=rubric,
    )
    return Stage9BaselineManifestBuilder().build(
        dataset_path=DATASET, settings=settings
    )


def test_writes_and_reloads_exact_typed_plan(tmp_path: Path) -> None:
    plan = _plan()
    writer = Stage9BaselineManifestWriter()
    paths = writer.write(plan, output_directory=tmp_path / "manifests")
    assert writer.load(paths.manifest_path) == plan
    assert len(paths.sha256) == 64
    assert paths.checksum_path.read_text(encoding="ascii").startswith(paths.sha256)


def test_write_is_byte_deterministic_across_directories(tmp_path: Path) -> None:
    plan = _plan()
    writer = Stage9BaselineManifestWriter()
    first = writer.write(plan, output_directory=tmp_path / "one")
    second = writer.write(plan, output_directory=tmp_path / "two")
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    assert first.sha256 == second.sha256


def test_uses_private_permissions(tmp_path: Path) -> None:
    paths = Stage9BaselineManifestWriter().write(_plan(), output_directory=tmp_path)
    assert paths.execution_directory.stat().st_mode & 0o777 == (
        STAGE9_MANIFEST_DIRECTORY_MODE
    )
    assert paths.manifest_path.stat().st_mode & 0o777 == STAGE9_MANIFEST_FILE_MODE
    assert paths.checksum_path.stat().st_mode & 0o777 == STAGE9_MANIFEST_FILE_MODE


def test_refuses_existing_manifest_directory(tmp_path: Path) -> None:
    writer = Stage9BaselineManifestWriter()
    writer.write(_plan(), output_directory=tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        writer.write(_plan(), output_directory=tmp_path)


def test_rejects_tampered_manifest(tmp_path: Path) -> None:
    writer = Stage9BaselineManifestWriter()
    paths = writer.write(_plan(), output_directory=tmp_path)
    paths.manifest_path.write_bytes(paths.manifest_path.read_bytes() + b" ")
    with pytest.raises(Stage9BaselineManifestStorageError, match="checksum"):
        writer.load(paths.manifest_path)


def test_rejects_tampered_checksum(tmp_path: Path) -> None:
    writer = Stage9BaselineManifestWriter()
    paths = writer.write(_plan(), output_directory=tmp_path)
    paths.checksum_path.write_text("0" * 64 + "  manifest.json\n", encoding="ascii")
    with pytest.raises(Stage9BaselineManifestStorageError, match="checksum"):
        writer.load(paths.manifest_path)


def test_rejects_symlink_manifest(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "manifest.json"
    os.symlink(target, link)
    Path(str(link) + ".sha256").write_text("0" * 64, encoding="ascii")
    with pytest.raises(Stage9BaselineManifestStorageError, match="regular file"):
        Stage9BaselineManifestWriter().load(link)


def test_rejects_manifest_above_size_ceiling(tmp_path: Path) -> None:
    writer = Stage9BaselineManifestWriter(maximum_manifest_bytes=1)
    with pytest.raises(Stage9BaselineManifestStorageError, match="maximum size"):
        writer.write(_plan(), output_directory=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_rejects_wrong_types(tmp_path: Path) -> None:
    writer = Stage9BaselineManifestWriter()
    with pytest.raises(TypeError, match="plan"):
        writer.write(object(), output_directory=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="output_directory"):
        writer.write(_plan(), output_directory="bad")  # type: ignore[arg-type]
