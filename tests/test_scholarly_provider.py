"""Tests for scholarly provider request and response contracts."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

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
from app.schemas.scholarly_work import (
    ScholarlyAccess,
    ScholarlyAccessState,
    ScholarlyIdentifierType,
    ScholarlyProviderProvenance,
    ScholarlyVersionType,
    ScholarlyWork,
    ScholarlyWorkType,
)


def _request(**changes: object) -> ScholarlySearchRequest:
    values: dict[str, object] = {
        "request_id": "academic-request-001",
        "query": "bounded academic research",
        "maximum_results": 2,
        "maximum_provider_requests": 1,
        "start_date": date(2020, 1, 1),
        "end_date": date(2026, 8, 23),
        "work_types": (ScholarlyWorkType.JOURNAL_ARTICLE,),
        "require_abstract": True,
    }
    values.update(changes)
    return ScholarlySearchRequest(**values)  # type: ignore[arg-type]


def _work(work_id: str = "work-001") -> ScholarlyWork:
    return ScholarlyWork(
        work_id=work_id,
        title="A bounded scholarly provider fixture",
        work_type=ScholarlyWorkType.JOURNAL_ARTICLE,
        version_type=ScholarlyVersionType.VERSION_OF_RECORD,
        identifiers=(
            normalize_scholarly_identifier(
                ScholarlyIdentifierType.DOI,
                f"10.1234/{work_id}",
            ),
        ),
        publication_year=2026,
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


def _usage(
    *,
    received: int,
    accepted: int,
    rejected: int,
    requests: int = 1,
) -> ScholarlyProviderUsage:
    return ScholarlyProviderUsage(
        request_count=requests,
        records_received=received,
        records_accepted=accepted,
        records_rejected=rejected,
        duration_ms=12.5,
    )


def _failure(position: int = 2) -> ScholarlyRecordFailure:
    return ScholarlyRecordFailure(
        provider_position=position,
        provider_record_id="malformed-002",
        error_type="RecordValidationError",
        message="The provider record could not be normalized.",
    )


def test_accepts_explicit_bounded_request() -> None:
    request = _request()

    assert request.maximum_results == 2
    assert request.maximum_provider_requests == 1
    assert request.require_abstract is True


@pytest.mark.parametrize("field", ["request_id", "query"])
def test_request_rejects_blank_required_text(field: str) -> None:
    with pytest.raises(ValidationError, match=f"{field} must not be blank"):
        _request(**{field: " "})


def test_request_rejects_reversed_dates_and_duplicate_types() -> None:
    with pytest.raises(ValidationError, match="must not be after"):
        _request(start_date=date(2026, 1, 2), end_date=date(2026, 1, 1))

    with pytest.raises(ValidationError, match="must not contain duplicates"):
        _request(
            work_types=(
                ScholarlyWorkType.PREPRINT,
                ScholarlyWorkType.PREPRINT,
            )
        )


def test_succeeded_result_contains_only_accepted_works() -> None:
    result = ScholarlySearchResult(
        request=_request(),
        provider="fixture-provider",
        status=ScholarlySearchStatus.SUCCEEDED,
        works=(_work(),),
        usage=_usage(received=1, accepted=1, rejected=0),
    )

    assert result.status is ScholarlySearchStatus.SUCCEEDED
    assert result.usage.request_count == 1


def test_no_results_is_successful_empty_observation() -> None:
    result = ScholarlySearchResult(
        request=_request(),
        provider="fixture-provider",
        status=ScholarlySearchStatus.NO_RESULTS,
        usage=_usage(received=0, accepted=0, rejected=0),
    )

    assert result.works == ()
    assert result.error is None


def test_partial_result_preserves_good_work_and_record_failure() -> None:
    result = ScholarlySearchResult(
        request=_request(),
        provider="fixture-provider",
        status=ScholarlySearchStatus.PARTIAL,
        works=(_work(),),
        record_failures=(_failure(),),
        usage=_usage(received=2, accepted=1, rejected=1),
    )

    assert len(result.works) == 1
    assert result.record_failures[0].provider_position == 2


def test_failed_result_contains_structured_provider_error() -> None:
    result = ScholarlySearchResult(
        request=_request(),
        provider="fixture-provider",
        status=ScholarlySearchStatus.FAILED,
        error=ScholarlyProviderError(
            error_type="ProviderTimeout",
            message="The provider timed out.",
            retryable=True,
        ),
        usage=_usage(
            received=0,
            accepted=0,
            rejected=0,
        ),
    )

    assert result.error is not None
    assert result.error.retryable is True


def test_rejects_provider_request_budget_overrun() -> None:
    with pytest.raises(ValidationError, match="exceeds request budget"):
        ScholarlySearchResult(
            request=_request(maximum_provider_requests=1),
            provider="fixture-provider",
            status=ScholarlySearchStatus.NO_RESULTS,
            usage=_usage(
                received=0,
                accepted=0,
                rejected=0,
                requests=2,
            ),
        )


def test_rejects_result_count_overrun() -> None:
    with pytest.raises(ValidationError, match="exceeds maximum_results"):
        ScholarlySearchResult(
            request=_request(maximum_results=1),
            provider="fixture-provider",
            status=ScholarlySearchStatus.SUCCEEDED,
            works=(_work("work-001"), _work("work-002")),
            usage=_usage(received=2, accepted=2, rejected=0),
        )


def test_rejects_usage_that_does_not_reconcile() -> None:
    with pytest.raises(ValidationError, match="must equal records_received"):
        _usage(received=3, accepted=1, rejected=1)

    with pytest.raises(ValidationError, match="must equal work count"):
        ScholarlySearchResult(
            request=_request(),
            provider="fixture-provider",
            status=ScholarlySearchStatus.SUCCEEDED,
            works=(_work(),),
            usage=_usage(received=2, accepted=2, rejected=0),
        )


def test_rejects_work_from_different_provider() -> None:
    work = _work().model_copy(
        update={
            "provenance": _work().provenance.model_copy(
                update={"provider": "another-provider"}
            )
        }
    )

    with pytest.raises(ValidationError, match="must match result provider"):
        ScholarlySearchResult(
            request=_request(),
            provider="fixture-provider",
            status=ScholarlySearchStatus.SUCCEEDED,
            works=(work,),
            usage=_usage(received=1, accepted=1, rejected=0),
        )


@pytest.mark.parametrize(
    ("status", "works", "failures", "error", "message"),
    [
        (ScholarlySearchStatus.SUCCEEDED, (), (), None, "succeeded result"),
        (
            ScholarlySearchStatus.NO_RESULTS,
            (_work(),),
            (),
            None,
            "no-results result",
        ),
        (
            ScholarlySearchStatus.PARTIAL,
            (_work(),),
            (),
            None,
            "partial result",
        ),
        (ScholarlySearchStatus.FAILED, (), (), None, "failed result"),
    ],
)
def test_rejects_inconsistent_status_shape(
    status: ScholarlySearchStatus,
    works: tuple[ScholarlyWork, ...],
    failures: tuple[ScholarlyRecordFailure, ...],
    error: ScholarlyProviderError | None,
    message: str,
) -> None:
    usage = _usage(
        received=len(works) + len(failures),
        accepted=len(works),
        rejected=len(failures),
    )
    with pytest.raises(ValidationError, match=message):
        ScholarlySearchResult(
            request=_request(),
            provider="fixture-provider",
            status=status,
            works=works,
            record_failures=failures,
            error=error,
            usage=usage,
        )


class FixtureScholarlyProvider(ScholarlyMetadataProvider):
    """Offline provider proving the abstract port contract."""

    @property
    def name(self) -> str:
        return "fixture-provider"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        return ScholarlySearchResult(
            request=request,
            provider=self.name,
            status=ScholarlySearchStatus.SUCCEEDED,
            works=(_work(),),
            usage=_usage(received=1, accepted=1, rejected=0),
        )


def test_offline_provider_implements_port_without_network() -> None:
    provider: ScholarlyMetadataProvider = FixtureScholarlyProvider()

    result = provider.search(_request())

    assert provider.name == "fixture-provider"
    assert result.status is ScholarlySearchStatus.SUCCEEDED
    assert result.usage.request_count == 1


def test_models_are_strict_and_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ScholarlySearchRequest.model_validate(
            {
                "request_id": "request-001",
                "query": "example",
                "unknown": "value",
            },
            strict=True,
        )


def test_failed_result_preserves_all_rejected_record_failures() -> None:
    result = ScholarlySearchResult(
        request=_request(),
        provider="fixture-provider",
        status=ScholarlySearchStatus.FAILED,
        record_failures=(_failure(position=1), _failure(position=2)),
        error=ScholarlyProviderError(
            error_type="AllRecordsRejected",
            message="All provider records failed validation.",
        ),
        usage=_usage(received=2, accepted=0, rejected=2),
    )

    assert result.works == ()
    assert len(result.record_failures) == 2
    assert result.usage.records_rejected == 2
