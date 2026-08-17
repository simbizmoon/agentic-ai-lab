"""Tests for normalized patent source metadata."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
    PatentSourceFamily,
    PatentSourceMetadata,
)


def metadata(**overrides: object) -> PatentSourceMetadata:
    values: dict[str, object] = {
        "source_family": PatentSourceFamily.WIPO_PATENTSCOPE,
        "publication_number": "WO 2024/123456 A1",
        "title": "Example technical publication",
        "source_url": "https://patentscope.wipo.int/search/en/detail.jsf",
        "metadata_verification_state": (PatentMetadataVerificationState.UNVERIFIED),
    }
    values.update(overrides)
    return PatentSourceMetadata.model_validate(values)


def test_metadata_accepts_unverified_wipo_record() -> None:
    value = metadata()

    assert value.source_family is PatentSourceFamily.WIPO_PATENTSCOPE
    assert value.publication_number == "WO2024/123456A1"
    assert value.publication_date is None


def test_metadata_accepts_unverified_epo_ops_record() -> None:
    value = metadata(
        source_family=PatentSourceFamily.EPO_OPS,
        publication_number="EP 1000000 A1",
        source_url=(
            "https://ops.epo.org/3.2/rest-services/"
            "published-data/publication/epodoc/EP1000000.A1"
        ),
    )

    assert value.source_family is PatentSourceFamily.EPO_OPS
    assert value.publication_number == "EP1000000A1"


def test_metadata_accepts_nullable_or_real_publication_date() -> None:
    assert metadata(publication_date=None).publication_date is None
    published = date(2024, 2, 1)
    assert metadata(publication_date=published).publication_date == published


def test_verified_means_present_fields_verified_not_complete() -> None:
    value = metadata(
        metadata_verification_state=PatentMetadataVerificationState.VERIFIED,
        publication_date=None,
    )

    assert value.metadata_verification_state is (
        PatentMetadataVerificationState.VERIFIED
    )
    assert value.publication_date is None


@pytest.mark.parametrize(
    "source_url",
    [
        "http://patentscope.wipo.int/detail",
        "https://example.com/detail",
        "https://patentscope.wipo.int.evil.example/detail",
        "https://evil-patentscope.wipo.int/detail",
    ],
)
def test_metadata_rejects_unaccepted_source_url(source_url: str) -> None:
    with pytest.raises(ValidationError):
        metadata(source_url=source_url)


@pytest.mark.parametrize("field", ["publication_number", "title"])
def test_metadata_rejects_blank_required_text(field: str) -> None:
    with pytest.raises(ValidationError, match=f"{field} must not be blank"):
        metadata(**{field: "  "})


def test_metadata_is_strict_and_frozen() -> None:
    value = metadata()

    with pytest.raises(ValidationError):
        metadata(source_family="wipo_patentscope")
    with pytest.raises(ValidationError):
        metadata(publication_date="2024-02-01")
    with pytest.raises(ValidationError):
        value.title = "Changed"


def test_metadata_does_not_infer_date_or_jurisdiction() -> None:
    dumped = metadata(publication_number="WO 2024/123456 A1").model_dump()

    assert dumped["publication_date"] is None
    assert "jurisdiction" not in dumped
    assert "application_number" not in dumped
