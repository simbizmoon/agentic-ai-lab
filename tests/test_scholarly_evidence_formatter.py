"""Offline tests for deterministic scholarly evidence formatting."""

from __future__ import annotations

import json

import pytest

from app.research.bounded_scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflow,
)
from app.research.scholarly_evidence_formatter import (
    DeterministicScholarlyEvidenceFormatter,
)
from app.research.scholarly_identifier_normalizer import (
    normalize_scholarly_identifier,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_provider import (
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
    ScholarlyIdentifierType,
    ScholarlyProviderProvenance,
    ScholarlyVersionType,
    ScholarlyWork,
    ScholarlyWorkType,
)


class FixtureProvider(ScholarlyMetadataProvider):
    def __init__(self, result: ScholarlySearchResult) -> None:
        self._result = result

    @property
    def name(self) -> str:
        return "fixture-provider"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        assert request == self._result.request
        return self._result


def _work(work_id: str, *, abstract: str | None, doi: bool) -> ScholarlyWork:
    identifiers = [
        normalize_scholarly_identifier(
            ScholarlyIdentifierType.OPENALEX,
            "W101" if work_id == "work-1" else "W102",
        )
    ]
    if doi:
        identifiers.append(
            normalize_scholarly_identifier(
                ScholarlyIdentifierType.DOI, "10.1234/exact.1"
            )
        )
    return ScholarlyWork(
        work_id=work_id,
        title=f"Fixture {work_id}",
        work_type=ScholarlyWorkType.JOURNAL_ARTICLE,
        version_type=ScholarlyVersionType.UNKNOWN,
        identifiers=tuple(identifiers),
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
            response_sha256=("a" if work_id == "work-1" else "b") * 64,
        ),
    )


def _result():
    request = ScholarlySearchRequest(
        request_id="request-001",
        query="exact scholarly evidence",
        maximum_results=3,
        maximum_provider_requests=1,
    )
    failure = ScholarlyRecordFailure(
        provider_position=3,
        provider_record_id="bad-3",
        error_type="RecordValidationError",
        message="Malformed provider record.",
    )
    provider_result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.PARTIAL,
        works=(
            _work("work-1", abstract="Exact abstract with ``` fence.", doi=True),
            _work("work-2", abstract=None, doi=False),
        ),
        record_failures=(failure,),
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=3,
            records_accepted=2,
            records_rejected=1,
            duration_ms=1.0,
        ),
    )
    return BoundedScholarlyEvidenceWorkflow(
        provider=FixtureProvider(provider_result)
    ).run(request, task_id="task-001")


def test_formats_deterministically() -> None:
    formatter = DeterministicScholarlyEvidenceFormatter()
    first = formatter.format(_result())
    second = formatter.format(_result())
    assert first == second
    assert first.markdown.endswith("\n")
    assert first.json_text.endswith("\n")


def test_json_is_complete_lossless_workflow_contract() -> None:
    result = _result()
    formatted = DeterministicScholarlyEvidenceFormatter().format(result)
    assert json.loads(formatted.json_text) == result.model_dump(mode="json")


def test_markdown_preserves_exact_provenance_and_offsets() -> None:
    result = _result()
    item = result.adaptation.evidence_set.evidence[0]
    markdown = DeterministicScholarlyEvidenceFormatter().format(result).markdown
    assert f"Evidence ID: {item.evidence_id}" in markdown
    assert f"Source ID: {item.source_id}" in markdown
    assert f"Document ID: {item.document_id}" in markdown
    assert f"Character range: 0:{len(item.excerpt)}" in markdown
    assert item.excerpt in markdown
    assert "Response SHA-256: " + "a" * 64 in markdown
    assert "````\nExact abstract with ``` fence.\n````" in markdown


def test_markdown_keeps_absence_omission_and_rejection_distinct() -> None:
    markdown = DeterministicScholarlyEvidenceFormatter().format(_result()).markdown
    assert "DOI: 10.1234/exact.1" in markdown
    assert "DOI: ABSENT" in markdown
    assert "Abstract evidence: OMITTED (abstract absent)" in markdown
    assert "Provider record ID: bad-3" in markdown
    assert "Error type: RecordValidationError" in markdown


def test_scope_notice_states_non_semantic_boundary() -> None:
    markdown = DeterministicScholarlyEvidenceFormatter().format(_result()).markdown
    assert "does not assess semantic relevance" in markdown
    assert "paper quality" in markdown
    assert "citation impact" in markdown
    assert "systematic-review completeness" in markdown
    assert "permission to obtain or use full text" in markdown
    assert "winner" not in markdown.casefold()
    assert "rank" not in markdown.casefold()


def test_rejects_wrong_input_type() -> None:
    with pytest.raises(
        TypeError,
        match="result must be a BoundedScholarlyEvidenceWorkflowResult",
    ):
        DeterministicScholarlyEvidenceFormatter().format(object())  # type: ignore[arg-type]
