"""Offline tests for the bounded scholarly evidence workflow."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.research.bounded_scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflow,
)
from app.research.scholarly_identifier_normalizer import (
    normalize_scholarly_identifier,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflowResult,
)
from app.schemas.scholarly_provider import (
    ScholarlyProviderError,
    ScholarlyProviderUsage,
    ScholarlyRecordFailure,
    ScholarlySearchRequest,
    ScholarlySearchResult,
    ScholarlySearchStatus,
)
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


class FixtureProvider(ScholarlyMetadataProvider):
    def __init__(self, result: ScholarlySearchResult) -> None:
        self._result = result
        self.calls = 0

    @property
    def name(self) -> str:
        return "fixture-provider"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        self.calls += 1
        return self._result


def _request() -> ScholarlySearchRequest:
    return ScholarlySearchRequest(
        request_id="request-001",
        query="bounded scholarly evidence",
        maximum_results=4,
        maximum_provider_requests=1,
    )


def _identifier(
    identifier_type: ScholarlyIdentifierType,
    value: str,
) -> ScholarlyIdentifier:
    return normalize_scholarly_identifier(identifier_type, value)


def _work(
    work_id: str,
    *,
    abstract: str | None,
    identifiers: tuple[ScholarlyIdentifier, ...],
) -> ScholarlyWork:
    return ScholarlyWork(
        work_id=work_id,
        title=f"Scholarly fixture {work_id}",
        work_type=ScholarlyWorkType.JOURNAL_ARTICLE,
        version_type=ScholarlyVersionType.UNKNOWN,
        identifiers=identifiers,
        abstract=(
            ScholarlyAbstract(
                text=abstract,
                provider="fixture-provider",
                provider_record_id=work_id,
                source_url=f"https://api.example.test/{work_id}",
            )
            if abstract is not None
            else None
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


def test_reports_bounded_counts_for_success_with_omission_and_duplicates() -> None:
    request = _request()
    shared_doi = _identifier(ScholarlyIdentifierType.DOI, "10.1234/shared")
    first = _work(
        "work-1",
        abstract="First exact abstract.",
        identifiers=(
            _identifier(ScholarlyIdentifierType.OPENALEX, "W101"),
            shared_doi,
        ),
    )
    duplicate = _work(
        "work-2",
        abstract="Second exact abstract.",
        identifiers=(
            _identifier(ScholarlyIdentifierType.OPENALEX, "W102"),
            shared_doi,
        ),
    )
    omitted = _work(
        "work-3",
        abstract=None,
        identifiers=(_identifier(ScholarlyIdentifierType.OPENALEX, "W103"),),
    )
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.SUCCEEDED,
        works=(first, duplicate, omitted),
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=3,
            records_accepted=3,
            records_rejected=0,
            duration_ms=1.0,
        ),
    )
    provider = FixtureProvider(result)

    workflow_result = BoundedScholarlyEvidenceWorkflow(provider=provider).run(
        request, task_id="task-001"
    )

    assert provider.calls == 1
    assert workflow_result.maximum_provider_requests == 1
    assert workflow_result.actual_provider_requests == 1
    assert workflow_result.records_received == 3
    assert workflow_result.works_accepted == 3
    assert workflow_result.records_rejected == 0
    assert workflow_result.abstract_documents_created == 2
    assert workflow_result.works_omitted_without_abstract == 1
    assert workflow_result.whole_abstract_evidence_created == 2
    assert workflow_result.duplicate_identity_groups == 1


def test_reports_partial_provider_failure_without_losing_evidence() -> None:
    request = _request()
    work = _work(
        "work-1",
        abstract="Accepted exact abstract.",
        identifiers=(_identifier(ScholarlyIdentifierType.OPENALEX, "W101"),),
    )
    failure = ScholarlyRecordFailure(
        provider_position=2,
        provider_record_id="bad-2",
        error_type="RecordValidationError",
        message="Malformed provider record.",
    )
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.PARTIAL,
        works=(work,),
        record_failures=(failure,),
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=2,
            records_accepted=1,
            records_rejected=1,
            duration_ms=1.0,
        ),
    )

    workflow_result = BoundedScholarlyEvidenceWorkflow(
        provider=FixtureProvider(result)
    ).run(request, task_id="task-001")

    assert workflow_result.records_rejected == 1
    assert workflow_result.whole_abstract_evidence_created == 1
    nested = workflow_result.adaptation.document_adaptation.artifact.result
    assert nested.status is ScholarlySearchStatus.PARTIAL
    assert nested.record_failures == (failure,)


def test_failed_provider_result_has_observed_request_and_zero_evidence() -> None:
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
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=0,
            records_accepted=0,
            records_rejected=0,
            duration_ms=1.0,
        ),
    )

    workflow_result = BoundedScholarlyEvidenceWorkflow(
        provider=FixtureProvider(result)
    ).run(request, task_id="task-001")

    assert workflow_result.actual_provider_requests == 1
    assert workflow_result.records_received == 0
    assert workflow_result.abstract_documents_created == 0
    assert workflow_result.whole_abstract_evidence_created == 0


def test_rejects_blank_task_before_provider_call() -> None:
    request = _request()
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.NO_RESULTS,
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=0,
            records_accepted=0,
            records_rejected=0,
            duration_ms=1.0,
        ),
    )
    provider = FixtureProvider(result)

    with pytest.raises(ValueError, match="task_id must not be blank"):
        BoundedScholarlyEvidenceWorkflow(provider=provider).run(
            request,
            task_id=" ",
        )

    assert provider.calls == 0


def test_summary_cannot_diverge_from_nested_artifact() -> None:
    request = _request()
    work = _work(
        "work-1",
        abstract="Exact abstract.",
        identifiers=(_identifier(ScholarlyIdentifierType.OPENALEX, "W101"),),
    )
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.SUCCEEDED,
        works=(work,),
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=1,
            records_accepted=1,
            records_rejected=0,
            duration_ms=1.0,
        ),
    )
    workflow_result = BoundedScholarlyEvidenceWorkflow(
        provider=FixtureProvider(result)
    ).run(request, task_id="task-001")

    payload = workflow_result.model_dump()
    payload["whole_abstract_evidence_created"] = 2
    with pytest.raises(ValidationError, match="must match nested artifact"):
        BoundedScholarlyEvidenceWorkflowResult.model_validate(
            payload,
            strict=True,
        )


def test_output_contains_no_quality_ranking_or_permission_fields() -> None:
    request = _request()
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.NO_RESULTS,
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=0,
            records_accepted=0,
            records_rejected=0,
            duration_ms=1.0,
        ),
    )
    workflow_result = BoundedScholarlyEvidenceWorkflow(
        provider=FixtureProvider(result)
    ).run(request, task_id="task-001")

    keys = _all_keys(workflow_result.model_dump(mode="json"))
    assert {
        "winner",
        "rank",
        "paper_quality_score",
        "citation_impact",
        "license_permission",
    }.isdisjoint(keys)


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for nested in value.values():
            keys.update(_all_keys(nested))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for nested in value:
            keys.update(_all_keys(nested))
        return keys
    return set()
