"""Tests for provider-neutral scholarly work contracts."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.scholarly_work import (
    ScholarlyAbstract,
    ScholarlyAccess,
    ScholarlyAccessState,
    ScholarlyAuthor,
    ScholarlyIdentifier,
    ScholarlyIdentifierType,
    ScholarlyIntegrityStatus,
    ScholarlyProviderProvenance,
    ScholarlyVersionType,
    ScholarlyWork,
    ScholarlyWorkType,
)


def _identifier() -> ScholarlyIdentifier:
    return ScholarlyIdentifier(
        identifier_type=ScholarlyIdentifierType.DOI,
        value="https://doi.org/10.1234/Example.1",
        normalized_value="10.1234/example.1",
    )


def _provenance() -> ScholarlyProviderProvenance:
    return ScholarlyProviderProvenance(
        provider="fixture-provider",
        provider_record_id="record-001",
        request_url="https://api.example.test/works/record-001",
        retrieved_at="2026-08-23T12:00:00+09:00",
        response_sha256="a" * 64,
    )


def _access() -> ScholarlyAccess:
    return ScholarlyAccess(
        state=ScholarlyAccessState.OPEN,
        landing_page_url="https://example.test/work/record-001",
        full_text_url="https://example.test/work/record-001.pdf",
        license="CC-BY-4.0",
        is_open_access=True,
    )


def _work(**changes: object) -> ScholarlyWork:
    values: dict[str, object] = {
        "work_id": "scholarly-work-001",
        "title": "A bounded academic research fixture",
        "work_type": ScholarlyWorkType.JOURNAL_ARTICLE,
        "version_type": ScholarlyVersionType.VERSION_OF_RECORD,
        "identifiers": (_identifier(),),
        "authors": (
            ScholarlyAuthor(
                display_name="Ada Example",
                position=1,
                given_name="Ada",
                family_name="Example",
                orcid="0000-0000-0000-0001",
                affiliations=("Example University",),
            ),
        ),
        "publication_date": date(2026, 8, 20),
        "publication_year": 2026,
        "venue": "Journal of Deterministic Fixtures",
        "publisher": "Example Publisher",
        "abstract": ScholarlyAbstract(
            text="This fixture describes a bounded research contract.",
            language="en",
            provider="fixture-provider",
            provider_record_id="record-001",
            source_url="https://api.example.test/works/record-001",
        ),
        "access": _access(),
        "integrity_status": ScholarlyIntegrityStatus.ACTIVE,
        "related_work_ids": (),
        "provenance": _provenance(),
        "metadata": {"fixture": "true"},
    }
    values.update(changes)
    return ScholarlyWork(**values)  # type: ignore[arg-type]


def test_builds_exact_provider_neutral_work() -> None:
    work = _work()

    assert work.identifiers[0].normalized_value == "10.1234/example.1"
    assert work.authors[0].position == 1
    assert work.abstract is not None
    assert work.abstract.provider_record_id == work.provenance.provider_record_id
    assert work.access.state is ScholarlyAccessState.OPEN


def test_models_unknown_and_metadata_only_without_guessing() -> None:
    work = _work(
        version_type=ScholarlyVersionType.UNKNOWN,
        publication_date=None,
        publication_year=None,
        venue=None,
        publisher=None,
        abstract=None,
        access=ScholarlyAccess(
            state=ScholarlyAccessState.METADATA_ONLY,
            landing_page_url="https://example.test/work/record-001",
            full_text_url=None,
            license=None,
            is_open_access=None,
        ),
        integrity_status=ScholarlyIntegrityStatus.UNKNOWN,
    )

    assert work.abstract is None
    assert work.publication_date is None
    assert work.access.full_text_url is None


def test_requires_at_least_one_exact_identifier() -> None:
    with pytest.raises(ValidationError, match="at least one identifier"):
        _work(identifiers=())


def test_rejects_duplicate_normalized_identifier() -> None:
    duplicate = ScholarlyIdentifier(
        identifier_type=ScholarlyIdentifierType.DOI,
        value="10.1234/example.1",
        normalized_value="10.1234/EXAMPLE.1",
    )

    with pytest.raises(ValidationError, match="must not contain duplicates"):
        _work(identifiers=(_identifier(), duplicate))


def test_provider_identifier_requires_provider_name() -> None:
    with pytest.raises(ValidationError, match="requires provider"):
        ScholarlyIdentifier(
            identifier_type=ScholarlyIdentifierType.PROVIDER,
            value="record-001",
            normalized_value="record-001",
        )


def test_nonprovider_identifier_rejects_provider_name() -> None:
    with pytest.raises(ValidationError, match="only valid"):
        ScholarlyIdentifier(
            identifier_type=ScholarlyIdentifierType.DOI,
            value="10.1234/example.1",
            normalized_value="10.1234/example.1",
            provider="fixture-provider",
        )


def test_rejects_noncontiguous_author_positions() -> None:
    with pytest.raises(ValidationError, match="contiguous"):
        _work(
            authors=(
                ScholarlyAuthor(display_name="First Author", position=1),
                ScholarlyAuthor(display_name="Third Author", position=3),
            )
        )


def test_rejects_publication_year_mismatch() -> None:
    with pytest.raises(ValidationError, match="must match"):
        _work(publication_year=2025)


def test_open_access_requires_explicit_boolean_and_full_text_url() -> None:
    with pytest.raises(ValidationError, match="is_open_access=True"):
        ScholarlyAccess(
            state=ScholarlyAccessState.OPEN,
            landing_page_url="https://example.test/work/record-001",
            full_text_url="https://example.test/work/record-001.pdf",
            is_open_access=None,
        )

    with pytest.raises(ValidationError, match="requires full_text_url"):
        ScholarlyAccess(
            state=ScholarlyAccessState.OPEN,
            landing_page_url="https://example.test/work/record-001",
            full_text_url=None,
            is_open_access=True,
        )


def test_metadata_only_rejects_full_text_url() -> None:
    with pytest.raises(ValidationError, match="must not include"):
        ScholarlyAccess(
            state=ScholarlyAccessState.METADATA_ONLY,
            landing_page_url="https://example.test/work/record-001",
            full_text_url="https://example.test/work/record-001.pdf",
        )


def test_rejects_invalid_urls_and_response_digest() -> None:
    with pytest.raises(ValidationError, match="absolute HTTP"):
        ScholarlyAccess(
            state=ScholarlyAccessState.UNKNOWN,
            landing_page_url="relative/path",
        )

    with pytest.raises(ValidationError, match="64-character hex"):
        ScholarlyProviderProvenance(
            provider="fixture-provider",
            provider_record_id="record-001",
            request_url="https://api.example.test/works/record-001",
            retrieved_at="2026-08-23T12:00:00+09:00",
            response_sha256="not-a-digest",
        )


def test_abstract_must_bind_to_same_provider_record() -> None:
    with pytest.raises(ValidationError, match="abstract record must match"):
        _work(
            abstract=ScholarlyAbstract(
                text="An abstract from a different record.",
                provider="fixture-provider",
                provider_record_id="record-999",
                source_url="https://api.example.test/works/record-999",
            )
        )


def test_rejects_self_and_duplicate_related_work_ids() -> None:
    with pytest.raises(ValidationError, match="must not contain work_id"):
        _work(related_work_ids=("SCHOLARLY-WORK-001",))

    with pytest.raises(ValidationError, match="must not contain duplicates"):
        _work(related_work_ids=("work-002", "WORK-002"))


def test_models_preprint_without_claiming_version_of_record() -> None:
    work = _work(
        work_type=ScholarlyWorkType.PREPRINT,
        version_type=ScholarlyVersionType.PREPRINT,
        identifiers=(
            ScholarlyIdentifier(
                identifier_type=ScholarlyIdentifierType.ARXIV,
                value="arXiv:2608.12345v2",
                normalized_value="2608.12345v2",
            ),
        ),
    )

    assert work.work_type is ScholarlyWorkType.PREPRINT
    assert work.version_type is ScholarlyVersionType.PREPRINT


def test_schema_is_strict_and_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ScholarlyIdentifier.model_validate(
            {
                "identifier_type": "doi",
                "value": "10.1234/example.1",
                "normalized_value": "10.1234/example.1",
                "unexpected": "value",
            },
            strict=True,
        )
