"""Offline tests for Stage 9 real acquisition runtime composition."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.stage9_development_runtime_factory import Stage9DevelopmentRuntime
from app.research.stage9_real_development_runtime_factory import (
    Stage9RealDevelopmentRuntimeFactoryError,
    create_stage9_real_development_runtime,
)
from app.research.stage9_real_provider_binding_preflight import (
    EPO_CONSUMER_KEY_ENV,
    EPO_CONSUMER_SECRET_ENV,
    TAVILY_API_KEY_ENV,
)

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)


class NoPaidLoopFactory:
    def create(self, *, case_id, packing):
        raise AssertionError(f"paid loop was not expected: {case_id}, {packing}")


class VerifiedOfficialProvider:
    def acquire(self, *, request, channel):
        raise AssertionError(f"acquisition was not expected: {request}:{channel}")


def _secrets() -> dict[str, str]:
    return {
        TAVILY_API_KEY_ENV: "private-tavily-value",
        EPO_CONSUMER_KEY_ENV: "private-epo-key",
        EPO_CONSUMER_SECRET_ENV: "private-epo-secret",
    }


def _never_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"external request was not expected: {request.url}")


def test_composes_all_real_acquisition_bindings_without_requests() -> None:
    never_client = httpx.Client(transport=httpx.MockTransport(_never_request))
    runtime = create_stage9_real_development_runtime(
        experiment=load_approved_baseline(MANIFEST, REVIEW),
        environ=_secrets(),
        repository_root=Path.cwd(),
        packed_loop_factory=NoPaidLoopFactory(),
        tavily_client=never_client,
        openalex_client=never_client,
        epo_client=never_client,
    )

    assert isinstance(runtime, Stage9DevelopmentRuntime)
    assert runtime.acquisition_router is not None
    assert runtime.research_loop is not None
    representation = repr(runtime)
    assert all(secret not in representation for secret in _secrets().values())


def test_missing_acquisition_secret_fails_before_client_use() -> None:
    secrets = _secrets()
    secrets[TAVILY_API_KEY_ENV] = " "
    with pytest.raises(
        Stage9RealDevelopmentRuntimeFactoryError,
        match=TAVILY_API_KEY_ENV,
    ):
        create_stage9_real_development_runtime(
            experiment=load_approved_baseline(MANIFEST, REVIEW),
            environ=secrets,
            repository_root=Path.cwd(),
            packed_loop_factory=NoPaidLoopFactory(),
        )


def test_verified_official_override_removes_tavily_credential_requirement() -> None:
    secrets = _secrets()
    secrets.pop(TAVILY_API_KEY_ENV)
    runtime = create_stage9_real_development_runtime(
        experiment=load_approved_baseline(MANIFEST, REVIEW),
        environ=secrets,
        repository_root=Path.cwd(),
        packed_loop_factory=NoPaidLoopFactory(),
        official_web=VerifiedOfficialProvider(),
    )

    assert isinstance(runtime, Stage9DevelopmentRuntime)
    assert "Stage9TavilyOfficialWebProvider" not in repr(runtime)


def test_repository_root_must_exist() -> None:
    with pytest.raises(FileNotFoundError):
        create_stage9_real_development_runtime(
            experiment=load_approved_baseline(MANIFEST, REVIEW),
            environ=_secrets(),
            repository_root=Path("does-not-exist-stage9"),
            packed_loop_factory=NoPaidLoopFactory(),
        )
