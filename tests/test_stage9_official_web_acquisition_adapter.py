"""Offline tests for allowlisted Stage 9 official-web acquisition."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.stage9_official_web_acquisition_adapter import (
    Stage9OfficialWebAcquisitionAdapter,
    Stage9OfficialWebAcquisitionError,
    Stage9OfficialWebDocument,
)
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionChannel,
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequestBuilder,
)

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)
CONTENT = (
    "The NIST AI RMF organizes risk work through Govern, Map, Measure, and Manage.\n\n"
    "A GAI action can require bounded evaluation and retained evidence.\n\n"
    "This unrelated paragraph describes weather."
)


def _request():
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    case = next(
        item
        for item in experiment.plan.manifest.cases
        if item.definition.case_id == "tech-01"
    )
    return Stage9DevelopmentAcquisitionRequestBuilder().build(
        case=case,
        request_id="stage9-official-tech-01",
    )


def _document(url: str = "https://www.nist.gov/example"):
    return Stage9OfficialWebDocument(
        url=url,
        title="Controlled NIST fixture",
        content=CONTENT,
        retrieved_at="2026-08-30T12:00:00+09:00",
        response_sha256=hashlib.sha256(CONTENT.encode("utf-8")).hexdigest(),
    )


class FixtureOfficialProvider:
    def __init__(self, documents):
        self.documents = documents
        self.calls = []

    def acquire(self, *, query, allowed_domains, maximum_results):
        self.calls.append((query, allowed_domains, maximum_results))
        return self.documents


def test_expands_gai_terms_and_uses_nist_allowlist_without_golden_source() -> None:
    provider = FixtureOfficialProvider((_document(),))
    request = _request()
    result = Stage9OfficialWebAcquisitionAdapter(provider=provider).acquire(
        request=request,
        channel=Stage9AcquisitionChannel.OFFICIAL_WEB,
    )

    query, domains, maximum_results = provider.calls[0]
    assert query.startswith(request.question)
    assert "Generative Artificial Intelligence" in query
    assert "risk management profile" in query
    assert "suggested actions" in query
    assert "https://" not in query
    assert domains == ("nist.gov",)
    assert maximum_results == 2
    assert result.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
    assert result.provider_requests == result.external_requests == 1
    document = result.evidence_set.document_set.documents[0]
    assert document.candidate.metadata["golden_source_supplied"] == "false"
    assert "weather" not in document.content
    for evidence in result.evidence_set.evidence:
        assert document.content[evidence.start_character : evidence.end_character] == (
            evidence.excerpt
        )


def test_non_gai_provider_query_is_not_expanded() -> None:
    question = "Which NIST controls are relevant?"

    assert Stage9OfficialWebAcquisitionAdapter._provider_query(question) == question


def test_rejects_nonofficial_or_cross_domain_result() -> None:
    provider = FixtureOfficialProvider((_document("https://example.com/nist-copy"),))
    with pytest.raises(Stage9OfficialWebAcquisitionError, match="allowlist"):
        Stage9OfficialWebAcquisitionAdapter(provider=provider).acquire(
            request=_request(), channel=Stage9AcquisitionChannel.OFFICIAL_WEB
        )


def test_rejects_provider_result_over_boundary() -> None:
    provider = FixtureOfficialProvider((_document(), _document(), _document()))
    with pytest.raises(Stage9OfficialWebAcquisitionError, match="result boundary"):
        Stage9OfficialWebAcquisitionAdapter(provider=provider).acquire(
            request=_request(), channel=Stage9AcquisitionChannel.OFFICIAL_WEB
        )


def test_empty_provider_result_is_explicit_no_evidence() -> None:
    result = Stage9OfficialWebAcquisitionAdapter(
        provider=FixtureOfficialProvider(())
    ).acquire(request=_request(), channel=Stage9AcquisitionChannel.OFFICIAL_WEB)
    assert result.status is Stage9AcquisitionStatus.NO_EVIDENCE
    assert result.evidence_set.evidence == []


def test_rejects_wrong_channel() -> None:
    with pytest.raises(ValueError, match="official_web"):
        Stage9OfficialWebAcquisitionAdapter(
            provider=FixtureOfficialProvider((_document(),))
        ).acquire(
            request=_request(), channel=Stage9AcquisitionChannel.SCHOLARLY_PRIMARY
        )
