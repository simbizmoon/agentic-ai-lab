"""Offline tests for Stage 9 bounded scholarly acquisition."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.bounded_scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflow,
)
from app.research.scholarly_identifier_normalizer import (
    normalize_scholarly_identifier,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.research.stage9_scholarly_acquisition_adapter import (
    Stage9ScholarlyAcquisitionAdapter,
)
from app.schemas.scholarly_provider import (
    ScholarlyProviderError,
    ScholarlyProviderUsage,
    ScholarlySearchRequest,
    ScholarlySearchResult,
    ScholarlySearchStatus,
)
from app.schemas.scholarly_work import (
    ScholarlyAbstract,
    ScholarlyAccess,
    ScholarlyAccessState,
    ScholarlyIdentifierType,
    ScholarlyProviderProvenance,
    ScholarlyVersionType,
    ScholarlyWork,
    ScholarlyWorkType,
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


def _request(case_id: str):
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    case = next(
        item
        for item in experiment.plan.manifest.cases
        if item.definition.case_id == case_id
    )
    return Stage9DevelopmentAcquisitionRequestBuilder().build(
        case=case,
        request_id=f"stage9-scholarly-{case_id}",
    )


def _work(request: ScholarlySearchRequest) -> ScholarlyWork:
    return ScholarlyWork(
        work_id="independently-discovered-work",
        title="Independently discovered scholarly work",
        work_type=ScholarlyWorkType.JOURNAL_ARTICLE,
        version_type=ScholarlyVersionType.UNKNOWN,
        identifiers=(
            normalize_scholarly_identifier(
                ScholarlyIdentifierType.OPENALEX,
                "W1234567890",
            ),
        ),
        abstract=ScholarlyAbstract(
            text="An independently acquired abstract used for offline testing.",
            provider="fixture-openalex",
            provider_record_id="W1234567890",
            source_url="https://api.openalex.org/works/W1234567890",
        ),
        access=ScholarlyAccess(
            state=ScholarlyAccessState.METADATA_ONLY,
            landing_page_url="https://openalex.org/W1234567890",
        ),
        provenance=ScholarlyProviderProvenance(
            provider="fixture-openalex",
            provider_record_id="W1234567890",
            request_url=f"https://api.openalex.org/works?search={request.query}",
            retrieved_at="2026-08-30T12:00:00+09:00",
            response_sha256="a" * 64,
        ),
    )


class DynamicFixtureProvider(ScholarlyMetadataProvider):
    def __init__(self, status: ScholarlySearchStatus) -> None:
        self.status = status
        self.requests: list[ScholarlySearchRequest] = []

    @property
    def name(self) -> str:
        return "fixture-openalex"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        self.requests.append(request)
        if self.status is ScholarlySearchStatus.FAILED:
            return ScholarlySearchResult(
                request=request,
                provider=self.name,
                status=self.status,
                error=ScholarlyProviderError(
                    error_type="ControlledProviderFailure",
                    message="Controlled local provider failure.",
                ),
                usage=ScholarlyProviderUsage(
                    request_count=1,
                    records_received=0,
                    records_accepted=0,
                    records_rejected=0,
                    duration_ms=1.0,
                ),
            )
        works = (
            (_work(request),) if self.status is ScholarlySearchStatus.SUCCEEDED else ()
        )
        return ScholarlySearchResult(
            request=request,
            provider=self.name,
            status=self.status,
            works=works,
            usage=ScholarlyProviderUsage(
                request_count=1,
                records_received=len(works),
                records_accepted=len(works),
                records_rejected=0,
                duration_ms=1.0,
            ),
        )


def _adapter(provider: ScholarlyMetadataProvider):
    return Stage9ScholarlyAcquisitionAdapter(
        workflow=BoundedScholarlyEvidenceWorkflow(provider=provider)
    )


def test_uses_exact_case_question_without_golden_source_injection() -> None:
    provider = DynamicFixtureProvider(ScholarlySearchStatus.SUCCEEDED)
    request = _request("academic-01")
    result = _adapter(provider).acquire(
        request=request,
        channel=Stage9AcquisitionChannel.SCHOLARLY_PRIMARY,
    )

    provider_request = provider.requests[0]
    assert provider_request.query == request.question
    assert provider_request.require_abstract is True
    assert provider_request.maximum_provider_requests == 1
    assert provider_request.metadata["golden_evidence_supplied"] == "false"
    assert "2005.11401" not in provider_request.query
    assert result.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
    assert len(result.evidence_set.evidence) == 1
    assert result.provider_requests == result.external_requests == 1


def test_no_results_remains_explicit_no_evidence() -> None:
    provider = DynamicFixtureProvider(ScholarlySearchStatus.NO_RESULTS)
    result = _adapter(provider).acquire(
        request=_request("academic-01"),
        channel=Stage9AcquisitionChannel.SCHOLARLY_PRIMARY,
    )

    assert result.status is Stage9AcquisitionStatus.NO_EVIDENCE
    assert result.evidence_set.evidence == []


def test_provider_failure_is_preserved_without_invented_evidence() -> None:
    provider = DynamicFixtureProvider(ScholarlySearchStatus.FAILED)
    result = _adapter(provider).acquire(
        request=_request("academic-01"),
        channel=Stage9AcquisitionChannel.SCHOLARLY_PRIMARY,
    )

    assert result.status is Stage9AcquisitionStatus.FAILED
    assert result.failure_code == "ControlledProviderFailure"
    assert result.evidence_set.evidence == []


def test_cross_source_case_may_use_scholarly_channel() -> None:
    provider = DynamicFixtureProvider(ScholarlySearchStatus.SUCCEEDED)
    result = _adapter(provider).acquire(
        request=_request("cross-01"),
        channel=Stage9AcquisitionChannel.SCHOLARLY_PRIMARY,
    )

    assert result.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE


def test_adapter_rejects_wrong_channel() -> None:
    provider = DynamicFixtureProvider(ScholarlySearchStatus.SUCCEEDED)
    with pytest.raises(ValueError, match="scholarly_primary"):
        _adapter(provider).acquire(
            request=_request("academic-01"),
            channel=Stage9AcquisitionChannel.EPO_PATENT,
        )
