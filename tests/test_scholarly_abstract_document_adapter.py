"""Tests for exact scholarly abstract document adaptation."""

from __future__ import annotations

from app.research.bounded_scholarly_search_workflow import (
    BoundedScholarlySearchWorkflow,
)
from app.research.scholarly_abstract_document_adapter import (
    ScholarlyAbstractDocumentAdapter,
)
from app.research.scholarly_identifier_normalizer import (
    normalize_scholarly_identifier,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.research_request import ResearchSourceType
from app.schemas.scholarly_provider import (
    ScholarlyProviderUsage,
    ScholarlySearchRequest,
    ScholarlySearchResult,
    ScholarlySearchStatus,
)
from app.schemas.scholarly_work import (
    ScholarlyAbstract,
    ScholarlyAccess,
    ScholarlyAccessState,
    ScholarlyAuthor,
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
        return self._result


def _request() -> ScholarlySearchRequest:
    return ScholarlySearchRequest(
        request_id="request-001",
        query="retrieval augmented generation",
        maximum_results=3,
        maximum_provider_requests=1,
    )


def _work(work_id: str, *, abstract: str | None, doi: bool = True) -> ScholarlyWork:
    identifiers = [
        normalize_scholarly_identifier(
            ScholarlyIdentifierType.OPENALEX,
            f"W{work_id[-1]}123",
        )
    ]
    if doi:
        identifiers.append(
            normalize_scholarly_identifier(
                ScholarlyIdentifierType.DOI,
                f"10.1234/{work_id}",
            )
        )
    provider_abstract = (
        ScholarlyAbstract(
            text=abstract,
            language="en",
            provider="fixture-provider",
            provider_record_id=work_id,
            source_url=f"https://api.example.test/{work_id}",
        )
        if abstract is not None
        else None
    )
    return ScholarlyWork(
        work_id=work_id,
        title=f"Academic work {work_id}",
        work_type=ScholarlyWorkType.JOURNAL_ARTICLE,
        version_type=ScholarlyVersionType.UNKNOWN,
        identifiers=tuple(identifiers),
        authors=(ScholarlyAuthor(display_name="Ada Example", position=1),),
        venue="Example Journal",
        abstract=provider_abstract,
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


def _artifact(*works: ScholarlyWork):
    request = _request()
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.SUCCEEDED,
        works=works,
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=len(works),
            records_accepted=len(works),
            records_rejected=0,
            duration_ms=1.0,
        ),
    )
    return BoundedScholarlySearchWorkflow(provider=FixtureProvider(result)).run(request)


def test_adapts_exact_abstract_to_one_document_and_section() -> None:
    abstract = "A complete provider-supplied abstract with exact provenance."
    adaptation = ScholarlyAbstractDocumentAdapter().adapt(
        _artifact(_work("work-1", abstract=abstract)),
        task_id="task-001",
    )

    assert adaptation.omitted_work_ids == ()
    document = adaptation.document_set.documents[0]
    assert document.content == abstract
    assert document.character_count == len(abstract)
    assert document.word_count == len(abstract.split())
    assert document.candidate.source_type is ResearchSourceType.ACADEMIC
    assert document.candidate.snippet == abstract
    assert document.reader == "scholarly-abstract-document-adapter"
    section = document.sections[0]
    assert section.content == abstract
    assert section.start_character == 0
    assert section.end_character == len(abstract)


def test_preserves_identity_access_and_response_provenance_metadata() -> None:
    adaptation = ScholarlyAbstractDocumentAdapter().adapt(
        _artifact(_work("work-1", abstract="Exact abstract.")),
        task_id="task-001",
    )

    document = adaptation.document_set.documents[0]
    metadata = document.metadata
    assert metadata["scholarly_work_id"] == "work-1"
    assert metadata["scholarly_provider_record_id"] == "work-1"
    assert metadata["scholarly_response_sha256"] == "a" * 64
    assert metadata["scholarly_doi"] == "10.1234/work-1"
    assert metadata["scholarly_version_type"] == "unknown"
    assert metadata["scholarly_access_state"] == "metadata_only"
    assert metadata["scholarly_license"] == "ABSENT"
    assert metadata["scholarly_integrity_status"] == "unknown"


def test_records_explicit_doi_absence_without_fabrication() -> None:
    adaptation = ScholarlyAbstractDocumentAdapter().adapt(
        _artifact(_work("work-1", abstract="Exact abstract.", doi=False)),
        task_id="task-001",
    )

    document = adaptation.document_set.documents[0]
    assert document.metadata["scholarly_doi"] == "ABSENT"
    assert "doi" not in document.metadata["scholarly_identifiers_json"]


def test_omits_work_without_abstract_instead_of_creating_empty_document() -> None:
    with_abstract = _work("work-1", abstract="Exact abstract.")
    without_abstract = _work("work-2", abstract=None)

    adaptation = ScholarlyAbstractDocumentAdapter().adapt(
        _artifact(with_abstract, without_abstract),
        task_id="task-001",
    )

    assert len(adaptation.document_set.documents) == 1
    assert adaptation.omitted_work_ids == ("work-2",)
    assert adaptation.artifact.result.works == (with_abstract, without_abstract)


def test_ids_are_stable_across_position_and_repeated_adaptation() -> None:
    first = _work("work-1", abstract="First exact abstract.")
    second = _work("work-2", abstract="Second exact abstract.")
    adapter = ScholarlyAbstractDocumentAdapter()

    one = adapter.adapt(_artifact(first, second), task_id="task-001")
    two = adapter.adapt(_artifact(second, first), task_id="task-001")

    ids_one = {
        document.metadata["scholarly_work_id"]: (
            document.candidate.source_id,
            document.document_id,
        )
        for document in one.document_set.documents
    }
    ids_two = {
        document.metadata["scholarly_work_id"]: (
            document.candidate.source_id,
            document.document_id,
        )
        for document in two.document_set.documents
    }
    assert ids_one == ids_two


def test_rejects_blank_task_id_before_adaptation() -> None:
    artifact = _artifact(_work("work-1", abstract="Exact abstract."))

    import pytest

    with pytest.raises(ValueError, match="task_id must not be blank"):
        ScholarlyAbstractDocumentAdapter().adapt(artifact, task_id=" ")


def test_makes_no_pdf_or_full_text_content_claim() -> None:
    adaptation = ScholarlyAbstractDocumentAdapter().adapt(
        _artifact(_work("work-1", abstract="Abstract only.")),
        task_id="task-001",
    )

    document = adaptation.document_set.documents[0]
    assert document.content == "Abstract only."
    assert document.content_type.value == "text"
    assert "full_text" not in document.metadata
    assert "pdf" not in document.metadata
