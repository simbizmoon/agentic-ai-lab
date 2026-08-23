"""Tests for deterministic scholarly identity normalization."""

from __future__ import annotations

from datetime import date

import pytest

from app.research.scholarly_identifier_normalizer import (
    ScholarlyIdentifierNormalizationError,
    are_scholarly_works_duplicates,
    group_duplicate_scholarly_works,
    normalize_scholarly_identifier,
    scholarly_identifier_identity_key,
)
from app.schemas.scholarly_work import (
    ScholarlyAccess,
    ScholarlyAccessState,
    ScholarlyIdentifier,
    ScholarlyIdentifierType,
    ScholarlyProviderProvenance,
    ScholarlyVersionType,
    ScholarlyWork,
    ScholarlyWorkType,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10.1234/Example.1", "10.1234/example.1"),
        (" DOI: 10.1234/Example.1 ", "10.1234/example.1"),
        ("https://doi.org/10.1234/Example.1", "10.1234/example.1"),
        ("http://dx.doi.org/10.1234%2FExample.1", "10.1234/example.1"),
    ],
)
def test_normalizes_equivalent_doi_forms(value: str, expected: str) -> None:
    identifier = normalize_scholarly_identifier(
        ScholarlyIdentifierType.DOI,
        value,
    )

    assert identifier.value == value.strip()
    assert identifier.normalized_value == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("arXiv:2608.12345v2", "2608.12345v2"),
        ("https://arxiv.org/abs/2608.12345v2", "2608.12345v2"),
        ("https://arxiv.org/pdf/2608.12345v2.pdf", "2608.12345v2"),
        ("hep-th/9901001v1", "hep-th/9901001v1"),
    ],
)
def test_normalizes_arxiv_forms_and_preserves_version(
    value: str,
    expected: str,
) -> None:
    identifier = normalize_scholarly_identifier(
        ScholarlyIdentifierType.ARXIV,
        value,
    )

    assert identifier.normalized_value == expected


@pytest.mark.parametrize(
    ("identifier_type", "value", "expected"),
    [
        (ScholarlyIdentifierType.PMID, "PMID: 001234", "1234"),
        (ScholarlyIdentifierType.PMCID, "pmcid: pmc001234", "PMC1234"),
        (ScholarlyIdentifierType.PMCID, "001234", "PMC1234"),
        (ScholarlyIdentifierType.OPENALEX, "w1234", "W1234"),
        (
            ScholarlyIdentifierType.OPENALEX,
            "https://openalex.org/W1234",
            "W1234",
        ),
    ],
)
def test_normalizes_numeric_and_openalex_identifiers(
    identifier_type: ScholarlyIdentifierType,
    value: str,
    expected: str,
) -> None:
    identifier = normalize_scholarly_identifier(identifier_type, value)

    assert identifier.normalized_value == expected


@pytest.mark.parametrize(
    ("identifier_type", "value"),
    [
        (ScholarlyIdentifierType.DOI, "not-a-doi"),
        (ScholarlyIdentifierType.DOI, "https://example.test/10.1234/item"),
        (ScholarlyIdentifierType.ARXIV, "arXiv:not-valid"),
        (ScholarlyIdentifierType.PMID, "PMID: abc"),
        (ScholarlyIdentifierType.PMCID, "PMCabc"),
        (ScholarlyIdentifierType.OPENALEX, "A1234"),
    ],
)
def test_rejects_invalid_or_wrong_host_identifiers(
    identifier_type: ScholarlyIdentifierType,
    value: str,
) -> None:
    with pytest.raises(ScholarlyIdentifierNormalizationError):
        normalize_scholarly_identifier(identifier_type, value)


def _provider_identifier(provider: str, value: str) -> ScholarlyIdentifier:
    return normalize_scholarly_identifier(
        ScholarlyIdentifierType.PROVIDER,
        value,
        provider=provider,
    )


def _work(
    work_id: str,
    *identifiers: ScholarlyIdentifier,
    title: str = "A scholarly work",
) -> ScholarlyWork:
    return ScholarlyWork(
        work_id=work_id,
        title=title,
        work_type=ScholarlyWorkType.JOURNAL_ARTICLE,
        version_type=ScholarlyVersionType.UNKNOWN,
        identifiers=identifiers,
        authors=(),
        publication_date=date(2026, 8, 23),
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
            response_sha256=(work_id[-1] if work_id[-1].isalnum() else "a")
            .encode()
            .hex()
            .ljust(64, "a")[:64],
        ),
    )


def test_exact_normalized_doi_is_duplicate_across_records() -> None:
    left = _work(
        "work-1",
        normalize_scholarly_identifier(
            ScholarlyIdentifierType.DOI,
            "doi:10.1234/EXAMPLE.1",
        ),
    )
    right = _work(
        "work-2",
        normalize_scholarly_identifier(
            ScholarlyIdentifierType.DOI,
            "https://doi.org/10.1234/example.1",
        ),
    )

    assert are_scholarly_works_duplicates(left, right) is True


def test_similar_title_without_shared_identifier_is_not_duplicate() -> None:
    left = _work("work-1", _provider_identifier("one", "1"), title="Same title")
    right = _work("work-2", _provider_identifier("two", "1"), title="Same title")

    assert are_scholarly_works_duplicates(left, right) is False


def test_provider_identifier_matches_only_within_same_provider() -> None:
    first = _provider_identifier("provider-a", "Record-X")
    same = _provider_identifier("PROVIDER-A", "Record-X")
    other = _provider_identifier("provider-b", "Record-X")

    assert scholarly_identifier_identity_key(first) == (
        "provider",
        "provider-a",
        "Record-X",
    )
    assert scholarly_identifier_identity_key(first) == (
        scholarly_identifier_identity_key(same)
    )
    assert scholarly_identifier_identity_key(first) != (
        scholarly_identifier_identity_key(other)
    )


def test_different_arxiv_versions_are_not_exact_duplicates() -> None:
    version_one = _work(
        "work-1",
        normalize_scholarly_identifier(
            ScholarlyIdentifierType.ARXIV,
            "2608.12345v1",
        ),
    )
    version_two = _work(
        "work-2",
        normalize_scholarly_identifier(
            ScholarlyIdentifierType.ARXIV,
            "2608.12345v2",
        ),
    )

    assert are_scholarly_works_duplicates(version_one, version_two) is False


def test_groups_transitive_matches_in_input_order() -> None:
    doi = normalize_scholarly_identifier(
        ScholarlyIdentifierType.DOI,
        "10.1234/example.1",
    )
    provider_id = _provider_identifier("provider-a", "record-1")
    first = _work("work-1", doi)
    bridge = _work("work-2", doi, provider_id)
    third = _work("work-3", provider_id)
    separate = _work("work-4", _provider_identifier("provider-b", "record-1"))

    groups = group_duplicate_scholarly_works((first, bridge, third, separate))

    assert tuple(tuple(work.work_id for work in group) for group in groups) == (
        ("work-1", "work-2", "work-3"),
        ("work-4",),
    )


def test_grouping_rejects_duplicate_internal_work_ids() -> None:
    first = _work("work-1", _provider_identifier("provider-a", "one"))
    second = _work("WORK-1", _provider_identifier("provider-a", "two"))

    with pytest.raises(ValueError, match="work IDs must be unique"):
        group_duplicate_scholarly_works((first, second))
