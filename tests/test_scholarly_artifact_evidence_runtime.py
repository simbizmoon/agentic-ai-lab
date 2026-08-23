"""Offline integration tests for scholarly artifact-to-evidence runtime."""

from __future__ import annotations

from app.research.bounded_scholarly_search_workflow import (
    BoundedScholarlySearchWorkflow,
)
from app.research.scholarly_artifact_evidence_runtime import (
    ScholarlyArtifactEvidenceRuntime,
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
        maximum_results=5,
        maximum_provider_requests=1,
    )


def _doi() -> ScholarlyIdentifier:
    return normalize_scholarly_identifier(
        ScholarlyIdentifierType.DOI,
        "10.1234/shared-work",
    )


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
                language="en",
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
            response_sha256=("a" if work_id.endswith("1") else "b") * 64,
        ),
    )


def _openalex(value: str) -> ScholarlyIdentifier:
    return normalize_scholarly_identifier(
        ScholarlyIdentifierType.OPENALEX,
        value,
    )


def test_preserves_partial_failures_duplicates_omissions_and_exact_evidence() -> None:
    request = _request()
    first = _work(
        "work-1",
        abstract="First exact provider abstract.",
        identifiers=(_openalex("W101"), _doi()),
    )
    second = _work(
        "work-2",
        abstract="Second exact provider abstract.",
        identifiers=(_openalex("W102"), _doi()),
    )
    no_abstract = _work(
        "work-3",
        abstract=None,
        identifiers=(_openalex("W103"),),
    )
    failure = ScholarlyRecordFailure(
        provider_position=4,
        provider_record_id="bad-record-4",
        error_type="RecordValidationError",
        message="Malformed provider record.",
    )
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.PARTIAL,
        works=(first, second, no_abstract),
        record_failures=(failure,),
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=4,
            records_accepted=3,
            records_rejected=1,
            duration_ms=1.0,
        ),
    )
    provider = FixtureProvider(result)
    artifact = BoundedScholarlySearchWorkflow(provider=provider).run(request)

    adaptation = ScholarlyArtifactEvidenceRuntime().build(
        artifact,
        task_id="task-001",
    )

    assert provider.calls == 1
    assert adaptation.document_adaptation.artifact == artifact
    assert artifact.result.record_failures == (failure,)
    assert len(artifact.duplicate_groups) == 1
    assert artifact.duplicate_groups[0].member_work_ids == (
        "work-1",
        "work-2",
    )
    assert adaptation.document_adaptation.omitted_work_ids == ("work-3",)
    documents = adaptation.evidence_set.document_set.documents
    evidence = adaptation.evidence_set.evidence
    assert len(documents) == 2
    assert len(evidence) == 2
    for document, item in zip(documents, evidence, strict=True):
        assert item.source_id == document.candidate.source_id
        assert item.document_id == document.document_id
        assert item.section_id == document.sections[0].section_id
        assert item.excerpt == document.content
        assert item.start_character == 0
        assert item.end_character == len(document.content)
        assert (
            item.metadata["scholarly_response_sha256"]
            == (document.metadata["scholarly_response_sha256"])
        )
        assert item.metadata["relevance_assessment"] == "not_performed"


def test_failed_search_artifact_produces_empty_documents_and_evidence() -> None:
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
    artifact = BoundedScholarlySearchWorkflow(provider=FixtureProvider(result)).run(
        request
    )

    adaptation = ScholarlyArtifactEvidenceRuntime().build(
        artifact,
        task_id="task-001",
    )

    assert adaptation.document_adaptation.document_set.documents == []
    assert adaptation.evidence_set.evidence == []
    assert adaptation.document_adaptation.artifact.result.error == result.error


def test_runtime_is_deterministic_and_ids_are_stable() -> None:
    request = _request()
    work = _work(
        "work-1",
        abstract="Stable exact provider abstract.",
        identifiers=(_openalex("W101"),),
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
    artifact = BoundedScholarlySearchWorkflow(provider=FixtureProvider(result)).run(
        request
    )
    runtime = ScholarlyArtifactEvidenceRuntime()

    first = runtime.build(artifact, task_id="task-001")
    second = runtime.build(artifact, task_id="task-001")

    assert first == second
    assert first.evidence_set.evidence[0].evidence_id == (
        second.evidence_set.evidence[0].evidence_id
    )


def test_runtime_performs_no_semantic_or_access_permission_judgment() -> None:
    request = _request()
    work = _work(
        "work-1",
        abstract="Provider abstract only.",
        identifiers=(_openalex("W101"),),
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
    artifact = BoundedScholarlySearchWorkflow(provider=FixtureProvider(result)).run(
        request
    )

    adaptation = ScholarlyArtifactEvidenceRuntime().build(
        artifact,
        task_id="task-001",
    )

    dumped = adaptation.model_dump(mode="json")
    keys = _all_keys(dumped)
    assert "paper_quality_score" not in keys
    assert "citation_impact" not in keys
    assert "full_text" not in keys
    assert "license_permission" not in keys
    item = adaptation.evidence_set.evidence[0]
    assert item.metadata["paper_quality_assessment"] == "not_performed"


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
