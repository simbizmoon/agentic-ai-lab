"""Tests for lazy bounded OpenAlex scholarly evidence composition."""

from __future__ import annotations

import pytest

from app.research.openalex_scholarly_metadata_provider import (
    OpenAlexScholarlyMetadataProvider,
)
from app.research.scholarly_evidence_factory import (
    build_openalex_scholarly_evidence_workflow,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_evidence_request import ScholarlyEvidenceRequest
from app.schemas.scholarly_provider import ScholarlySearchRequest, ScholarlySearchResult


class NeverCalledProvider(ScholarlyMetadataProvider):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "fixture-provider"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        self.calls += 1
        raise AssertionError("factory construction must not search")


def request() -> ScholarlyEvidenceRequest:
    return ScholarlyEvidenceRequest(query="bounded factory")


def test_factory_uses_injected_provider_without_calling_it() -> None:
    provider = NeverCalledProvider()
    workflow = build_openalex_scholarly_evidence_workflow(request(), provider=provider)
    assert workflow is not None
    assert provider.calls == 0


def test_factory_builds_default_openalex_provider_without_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = OpenAlexScholarlyMetadataProvider.search

    def fail_if_called(self, provider_request):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(self, provider_request)

    monkeypatch.setattr(OpenAlexScholarlyMetadataProvider, "search", fail_if_called)
    workflow = build_openalex_scholarly_evidence_workflow(request())
    assert workflow is not None
    assert calls == 0


def test_factory_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError, match="request must be a ScholarlyEvidenceRequest"):
        build_openalex_scholarly_evidence_workflow(object())  # type: ignore[arg-type]


def test_factory_rejects_client_with_injected_provider() -> None:
    with pytest.raises(
        ValueError, match="client must not be supplied with an injected provider"
    ):
        build_openalex_scholarly_evidence_workflow(
            request(),
            provider=NeverCalledProvider(),
            client=object(),  # type: ignore[arg-type]
        )
