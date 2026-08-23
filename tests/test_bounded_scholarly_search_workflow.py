"""Offline tests for bounded scholarly workflow integration."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.research.bounded_scholarly_search_workflow import (
    BoundedScholarlySearchWorkflow,
    ScholarlySearchWorkflowContractError,
)
from app.research.scholarly_identifier_normalizer import (
    normalize_scholarly_identifier,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_provider import (
    ScholarlyProviderError,
    ScholarlyProviderUsage,
    ScholarlyRecordFailure,
    ScholarlySearchRequest,
    ScholarlySearchResult,
    ScholarlySearchStatus,
)
from app.schemas.scholarly_search_workflow import ScholarlySearchWorkflowArtifact
from app.schemas.scholarly_work import (
    ScholarlyAbstract,
    ScholarlyAccess,
    ScholarlyAccessState,
    ScholarlyIdentifier,
    ScholarlyIdentifierType,
    ScholarlyProviderProvenance,
    ScholarlyVersionType,
    ScholarlyWork,
    ScholarlyWorkType,
)


def _request(request_id: str = "request-001") -> ScholarlySearchRequest:
    return ScholarlySearchRequest(
        request_id=request_id,
        query="bounded academic research",
        maximum_results=5,
        maximum_provider_requests=1,
        require_abstract=True,
    )


def _provider_identifier(value: str) -> ScholarlyIdentifier:
    return normalize_scholarly_identifier(
        ScholarlyIdentifierType.PROVIDER,
        value,
        provider="fixture-provider",
    )


def _work(
    work_id: str,
    *identifiers: ScholarlyIdentifier,
    title: str = "A scholarly fixture",
) -> ScholarlyWork:
    return ScholarlyWork(
        work_id=work_id,
        title=title,
        work_type=ScholarlyWorkType.JOURNAL_ARTICLE,
        version_type=ScholarlyVersionType.UNKNOWN,
        identifiers=identifiers,
        abstract=ScholarlyAbstract(
            text=f"Exact abstract for {work_id}.",
            provider="fixture-provider",
            provider_record_id=work_id,
            source_url=f"https://api.example.test/{work_id}",
        ),
        access=ScholarlyAccess(
            state=ScholarlyAccessState.METADATA_ONLY,
            landing_page_url=f"https://example.test/{work_id}",
        ),
        provenance=ScholarlyProviderProvenance(
            provider="fixture-provider",
            provider_record_id=work_id,
            request_url=f"https://api.example.test/{work_id}",
            retrieved_at="2026-08-23T12:00:00+09:00",
            response_sha256="a" * 64,
        ),
    )


def _usage(received: int, accepted: int, rejected: int = 0) -> ScholarlyProviderUsage:
    return ScholarlyProviderUsage(
        request_count=1,
        records_received=received,
        records_accepted=accepted,
        records_rejected=rejected,
        duration_ms=1.0,
    )


@dataclass
class FixtureProvider(ScholarlyMetadataProvider):
    result: ScholarlySearchResult
    calls: int = 0

    @property
    def name(self) -> str:
        return "fixture-provider"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        self.calls += 1
        return self.result


def _successful_result(
    request: ScholarlySearchRequest,
    *works: ScholarlyWork,
) -> ScholarlySearchResult:
    return ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.SUCCEEDED,
        works=works,
        usage=_usage(len(works), len(works)),
    )


def test_calls_provider_once_and_preserves_exact_work_provenance() -> None:
    request = _request()
    work = _work("work-1", _provider_identifier("record-1"))
    provider = FixtureProvider(_successful_result(request, work))

    artifact = BoundedScholarlySearchWorkflow(provider=provider).run(request)

    assert provider.calls == 1
    assert artifact.result.works[0] == work
    assert artifact.result.works[0].abstract == work.abstract
    assert artifact.result.works[0].provenance == work.provenance
    assert artifact.distinct_identity_group_count == 1


def test_groups_exact_doi_duplicates_without_discarding_records() -> None:
    request = _request()
    first = _work(
        "work-1",
        normalize_scholarly_identifier(
            ScholarlyIdentifierType.DOI, "doi:10.1234/EXAMPLE"
        ),
    )
    second = _work(
        "work-2",
        normalize_scholarly_identifier(
            ScholarlyIdentifierType.DOI, "https://doi.org/10.1234/example"
        ),
    )
    provider = FixtureProvider(_successful_result(request, first, second))

    artifact = BoundedScholarlySearchWorkflow(provider=provider).run(request)

    assert len(artifact.result.works) == 2
    assert len(artifact.duplicate_groups) == 1
    group = artifact.duplicate_groups[0]
    assert group.member_work_ids == ("work-1", "work-2")
    assert group.shared_identity_keys == ("doi|10.1234/example",)
    assert artifact.distinct_identity_group_count == 1
    assert "winner" not in artifact.model_dump()
    assert "rank" not in artifact.model_dump()


def test_same_title_without_shared_identifier_stays_separate() -> None:
    request = _request()
    first = _work("work-1", _provider_identifier("record-1"), title="Same title")
    second = _work("work-2", _provider_identifier("record-2"), title="Same title")
    provider = FixtureProvider(_successful_result(request, first, second))

    artifact = BoundedScholarlySearchWorkflow(provider=provider).run(request)

    assert artifact.duplicate_groups == ()
    assert artifact.distinct_identity_group_count == 2


def test_preserves_partial_provider_result_and_failure() -> None:
    request = _request()
    work = _work("work-1", _provider_identifier("record-1"))
    failure = ScholarlyRecordFailure(
        provider_position=2,
        provider_record_id="bad-2",
        error_type="RecordValidationError",
        message="Malformed fixture record.",
    )
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.PARTIAL,
        works=(work,),
        record_failures=(failure,),
        usage=_usage(2, 1, 1),
    )

    artifact = BoundedScholarlySearchWorkflow(provider=FixtureProvider(result)).run(
        request
    )

    assert artifact.result.status is ScholarlySearchStatus.PARTIAL
    assert artifact.result.record_failures == (failure,)


def test_preserves_failed_provider_result_without_duplicate_groups() -> None:
    request = _request()
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.FAILED,
        error=ScholarlyProviderError(
            error_type="ProviderTimeout",
            message="Provider timed out.",
            retryable=True,
        ),
        usage=_usage(0, 0),
    )

    artifact = BoundedScholarlySearchWorkflow(provider=FixtureProvider(result)).run(
        request
    )

    assert artifact.result.status is ScholarlySearchStatus.FAILED
    assert artifact.duplicate_groups == ()
    assert artifact.distinct_identity_group_count == 0


def test_rejects_provider_result_bound_to_different_request() -> None:
    request = _request()
    other = _request("request-999")
    provider = FixtureProvider(
        ScholarlySearchResult(
            request=other,
            provider="fixture-provider",
            status=ScholarlySearchStatus.NO_RESULTS,
            usage=_usage(0, 0),
        )
    )

    with pytest.raises(ScholarlySearchWorkflowContractError, match="does not match"):
        BoundedScholarlySearchWorkflow(provider=provider).run(request)


class WrongNameProvider(FixtureProvider):
    @property
    def name(self) -> str:
        return "wrong-provider"


def test_rejects_result_from_different_provider_name() -> None:
    request = _request()
    provider = WrongNameProvider(
        ScholarlySearchResult(
            request=request,
            provider="fixture-provider",
            status=ScholarlySearchStatus.NO_RESULTS,
            usage=_usage(0, 0),
        )
    )

    with pytest.raises(
        ScholarlySearchWorkflowContractError, match="name does not match"
    ):
        BoundedScholarlySearchWorkflow(provider=provider).run(request)


def test_artifact_rejects_unknown_or_repeated_group_members() -> None:
    request = _request()
    work = _work("work-1", _provider_identifier("record-1"))
    artifact = BoundedScholarlySearchWorkflow(
        provider=FixtureProvider(_successful_result(request, work))
    ).run(request)

    with pytest.raises(ValueError):
        ScholarlySearchWorkflowArtifact.model_validate(
            {
                **artifact.model_dump(),
                "distinct_identity_group_count": 2,
            },
            strict=True,
        )
