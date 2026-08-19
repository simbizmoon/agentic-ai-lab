"""Tests for normalized patent source metadata."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.patent_source_metadata import (
    PatentCpcClassification,
    PatentIpcClassification,
    PatentMetadataVerificationState,
    PatentParty,
    PatentPriorityClaim,
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
    assert dumped["application_number"] is None
    assert "jurisdiction" not in dumped


def test_metadata_accepts_optional_application_number() -> None:
    value = PatentSourceMetadata(
        source_family=PatentSourceFamily.EPO_OPS,
        publication_number="EP123456A1",
        title="Test patent",
        source_url=(
            "https://ops.epo.org/3.2/rest-services/"
            "published-data/publication/docdb/EP.123456.A1/abstract"
        ),
        metadata_verification_state=PatentMetadataVerificationState.VERIFIED,
        application_number="EP2024123456",
    )

    assert value.application_number == "EP2024123456"


def test_metadata_rejects_blank_application_number_when_present() -> None:
    with pytest.raises(ValidationError, match="application_number"):
        PatentSourceMetadata(
            source_family=PatentSourceFamily.EPO_OPS,
            publication_number="EP123456A1",
            title="Test patent",
            source_url=(
                "https://ops.epo.org/3.2/rest-services/"
                "published-data/publication/docdb/EP.123456.A1/abstract"
            ),
            metadata_verification_state=PatentMetadataVerificationState.VERIFIED,
            application_number="   ",
        )


def test_priority_claim_contract_is_strict_frozen_and_provider_neutral() -> None:
    value = PatentPriorityClaim(
        priority_number="KR20250015704",
        priority_date=date(2025, 2, 7),
    )

    assert value.priority_number == "KR20250015704"
    assert value.priority_date == date(2025, 2, 7)

    with pytest.raises(ValidationError, match="priority_number"):
        PatentPriorityClaim(priority_number="   ")

    with pytest.raises(ValidationError):
        PatentPriorityClaim(priority_number="KR20250015704", priority_date="2025-02-07")

    with pytest.raises(ValidationError):
        value.priority_number = "CHANGED"


def test_metadata_accepts_zero_or_multiple_priority_claims_in_order() -> None:
    assert metadata().priority_claims == ()

    first = PatentPriorityClaim(
        priority_number="KR20250015704",
        priority_date=date(2025, 2, 7),
    )
    second = PatentPriorityClaim(
        priority_number="US202563756683P",
        priority_date=date(2025, 2, 10),
    )
    value = metadata(priority_claims=(first, second))

    assert value.priority_claims == (first, second)


def test_patent_party_contract_is_strict_frozen_and_nonblank() -> None:
    value = PatentParty(name="Electronics and Telecommunications Research Institute")

    assert value.name == "Electronics and Telecommunications Research Institute"

    with pytest.raises(ValidationError, match="name"):
        PatentParty(name="   ")

    with pytest.raises(ValidationError):
        value.name = "CHANGED"


def test_metadata_accepts_zero_or_multiple_applicants_and_inventors_in_order() -> None:
    assert metadata().applicants == ()
    assert metadata().inventors == ()

    applicant = PatentParty(
        name="Electronics and Telecommunications Research Institute",
    )
    first_inventor = PatentParty(name="HEO, Sewan")
    second_inventor = PatentParty(name="KU, Tai-yeon")

    value = metadata(
        applicants=(applicant,),
        inventors=(first_inventor, second_inventor),
    )

    assert value.applicants == (applicant,)
    assert value.inventors == (first_inventor, second_inventor)


def test_ipc_classification_contract_is_strict_frozen_and_nonblank() -> None:
    value = PatentIpcClassification(text="H02J 3/ 32 A I")

    assert value.text == "H02J 3/ 32 A I"

    with pytest.raises(ValidationError, match="text"):
        PatentIpcClassification(text="   ")

    with pytest.raises(ValidationError):
        value.text = "CHANGED"


def test_metadata_accepts_zero_or_multiple_ipc_classifications_in_order() -> None:
    assert metadata().ipc_classifications == ()

    first = PatentIpcClassification(text="H02J 3/ 32 A I")
    second = PatentIpcClassification(text="H02J 3/ 46 A I")

    value = metadata(ipc_classifications=(first, second))

    assert value.ipc_classifications == (first, second)


def test_cpc_classification_contract_is_strict_frozen_and_provider_neutral() -> None:
    value = PatentCpcClassification(
        section="H",
        class_number="02",
        subclass="J",
        main_group="3",
        subgroup="32",
    )

    assert value.section == "H"
    assert value.class_number == "02"
    assert value.subclass == "J"
    assert value.main_group == "3"
    assert value.subgroup == "32"

    with pytest.raises(ValidationError, match="section"):
        PatentCpcClassification(
            section="   ",
            class_number="02",
            subclass="J",
            main_group="3",
            subgroup="32",
        )

    with pytest.raises(ValidationError):
        value.section = "G"


def test_metadata_accepts_zero_or_multiple_cpc_classifications_in_order() -> None:
    assert metadata().cpc_classifications == ()

    first = PatentCpcClassification(
        section="H",
        class_number="02",
        subclass="J",
        main_group="3",
        subgroup="32",
    )
    second = PatentCpcClassification(
        section="H",
        class_number="02",
        subclass="J",
        main_group="3",
        subgroup="46",
    )

    value = metadata(cpc_classifications=(first, second))

    assert value.cpc_classifications == (first, second)
