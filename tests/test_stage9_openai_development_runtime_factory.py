"""Offline tests for the complete locked Stage 9 OpenAI runtime composition."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.stage9_development_runtime_factory import Stage9DevelopmentRuntime
from app.research.stage9_openai_development_runtime_factory import (
    create_stage9_openai_development_runtime,
)
from app.research.stage9_real_provider_binding_preflight import (
    EPO_CONSUMER_KEY_ENV,
    EPO_CONSUMER_SECRET_ENV,
)

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)


class NoCallResponses:
    def create(self, **kwargs):
        raise AssertionError(f"responses.create was not expected: {kwargs}")

    def parse(self, **kwargs):
        raise AssertionError(f"responses.parse was not expected: {kwargs}")


def _never_http(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"HTTP request was not expected: {request.url}")


def _environment():
    return {
        EPO_CONSUMER_KEY_ENV: "private-epo-key",
        EPO_CONSUMER_SECRET_ENV: "private-epo-secret",
    }


def test_composes_locked_openai_and_acquisition_runtime_without_calls() -> None:
    no_http = httpx.Client(transport=httpx.MockTransport(_never_http))
    runtime = create_stage9_openai_development_runtime(
        experiment=load_approved_baseline(MANIFEST, REVIEW),
        environ=_environment(),
        repository_root=Path.cwd(),
        openai_client=SimpleNamespace(responses=NoCallResponses()),
        official_web_client=no_http,
        tavily_client=no_http,
        openalex_client=no_http,
        epo_client=no_http,
    )

    assert isinstance(runtime, Stage9DevelopmentRuntime)
    representation = repr(runtime)
    assert all(secret not in representation for secret in _environment().values())
    assert "Stage9TavilyOfficialWebProvider" not in representation


@pytest.mark.parametrize("missing_method", ["create", "parse"])
def test_requires_both_locked_responses_operations(missing_method: str) -> None:
    methods = {
        "create": lambda **kwargs: kwargs,
        "parse": lambda **kwargs: kwargs,
    }
    methods.pop(missing_method)
    client = SimpleNamespace(responses=SimpleNamespace(**methods))
    with pytest.raises(TypeError, match=f"responses.{missing_method}"):
        create_stage9_openai_development_runtime(
            experiment=load_approved_baseline(MANIFEST, REVIEW),
            environ=_environment(),
            repository_root=Path.cwd(),
            openai_client=client,
        )
