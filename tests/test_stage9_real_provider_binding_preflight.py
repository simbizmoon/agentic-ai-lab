"""Offline tests for the secret-safe Stage 9 real-provider preflight."""

from __future__ import annotations

from pathlib import Path

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.stage9_real_provider_binding_preflight import (
    CONSERVATIVE_ACQUISITION_EXTERNAL_REQUESTS,
    DEVELOPMENT_MAXIMUM_ESTIMATED_COST,
    DEVELOPMENT_MAXIMUM_EXTERNAL_REQUESTS,
    DEVELOPMENT_MAXIMUM_PROVIDER_REQUESTS,
    REQUIRED_SECRET_ENV_NAMES,
    Stage9ProviderPreflightStatus,
    Stage9RealProviderBindingPreflight,
)

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)


def _experiment():
    return load_approved_baseline(MANIFEST, REVIEW)


def _repository(tmp_path: Path) -> Path:
    (tmp_path / "ROADMAP.md").write_text("# Stage 9\nReady.\n", encoding="utf-8")
    return tmp_path


def test_ready_result_contains_names_but_never_secret_values(tmp_path: Path) -> None:
    secrets = {
        name: f"private-value-for-{position}"
        for position, name in enumerate(REQUIRED_SECRET_ENV_NAMES, start=1)
    }
    result = Stage9RealProviderBindingPreflight().check(
        experiment=_experiment(),
        environ=secrets,
        repository_root=_repository(tmp_path),
    )

    assert result.status is Stage9ProviderPreflightStatus.READY
    assert result.missing_environment_names == ()
    assert result.maximum_provider_requests == DEVELOPMENT_MAXIMUM_PROVIDER_REQUESTS
    assert result.maximum_external_requests == DEVELOPMENT_MAXIMUM_EXTERNAL_REQUESTS
    assert result.conservative_acquisition_external_requests == (
        CONSERVATIVE_ACQUISITION_EXTERNAL_REQUESTS
    )
    assert result.maximum_estimated_cost == DEVELOPMENT_MAXIMUM_ESTIMATED_COST
    assert result.paid_execution_started is False
    serialized = result.model_dump_json()
    assert all(value not in serialized for value in secrets.values())


def test_missing_credentials_block_before_any_provider_call(tmp_path: Path) -> None:
    result = Stage9RealProviderBindingPreflight().check(
        experiment=_experiment(),
        environ={"OPENAI_API_KEY": "present", "TAVILY_API_KEY": "  "},
        repository_root=_repository(tmp_path),
    )

    assert result.status is Stage9ProviderPreflightStatus.BLOCKED
    assert result.missing_environment_names == (
        "TAVILY_API_KEY",
        "EPO_OPS_CONSUMER_KEY",
        "EPO_OPS_CONSUMER_SECRET",
    )
    assert result.paid_execution_started is False


def test_symlinked_roadmap_blocks_even_with_credentials(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    root = tmp_path / "repository"
    root.mkdir()
    (root / "ROADMAP.md").symlink_to(outside)
    result = Stage9RealProviderBindingPreflight().check(
        experiment=_experiment(),
        environ={name: "present" for name in REQUIRED_SECRET_ENV_NAMES},
        repository_root=root,
    )
    assert result.status is Stage9ProviderPreflightStatus.BLOCKED
    assert result.repository_roadmap_ready is False


def test_openalex_does_not_add_a_secret_requirement(tmp_path: Path) -> None:
    result = Stage9RealProviderBindingPreflight().check(
        experiment=_experiment(),
        environ={name: "present" for name in REQUIRED_SECRET_ENV_NAMES},
        repository_root=_repository(tmp_path),
    )
    assert "OPENALEX_API_KEY" not in REQUIRED_SECRET_ENV_NAMES
    assert result.openalex_credential_required is False
