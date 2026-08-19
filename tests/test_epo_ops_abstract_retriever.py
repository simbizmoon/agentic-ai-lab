"""Tests for EPO OPS abstract retrieval and verified source mapping."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.research.epo_ops_abstract_retriever import (
    EPO_OPS_ABSTRACT_ACCEPT,
    EpoOpsAbstractResponseError,
    EpoOpsAbstractRetriever,
    EpoOpsAbstractXmlParseError,
)
from app.research.epo_ops_client import EpoOpsHttpResponse
from app.research.epo_ops_patent_source_adapter import (
    EpoOpsPatentSourceMappingError,
    build_verified_epo_patent_record,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsCpcClassification,
    EpoOpsDocumentIdType,
    EpoOpsIpcClassification,
    EpoOpsPartyRepresentation,
    EpoOpsPriorityClaim,
)
from app.schemas.patent_source_metadata import (
    PatentCpcClassification,
    PatentIpcClassification,
    PatentMetadataVerificationState,
    PatentParty,
    PatentPriorityClaim,
    PatentSourceFamily,
)

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "epo_ops"


def fixture(name: str) -> bytes:
    return (FIXTURE_DIRECTORY / name).read_bytes()


def bibliographic(**overrides: object) -> EpoOpsBibliographicRecord:
    values: dict[str, object] = {
        "publication_number": "EPTEST0001A1",
        "publication_docdb": "EP.TEST0001.A1",
        "title": "Test optical apparatus",
        "publication_date": date(2024, 1, 31),
        "source_endpoint": (
            "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
            "?q=ti%3D%22optical%20sensor%22"
        ),
        "document_id_type": EpoOpsDocumentIdType.DOCDB,
        "application_number": "EPTESTAPP0001",
        "title_language": "en",
    }
    values.update(overrides)
    return EpoOpsBibliographicRecord.model_validate(values)


class FakeEpoOpsClient:
    def __init__(
        self,
        *,
        body: bytes,
        content_type: str = EPO_OPS_ABSTRACT_ACCEPT,
    ) -> None:
        self.body = body
        self.content_type = content_type
        self.calls: list[tuple[str, str]] = []

    def authenticated_get_response(
        self,
        *,
        endpoint: str,
        accept: str,
    ) -> EpoOpsHttpResponse:
        self.calls.append((endpoint, accept))
        return EpoOpsHttpResponse(body=self.body, content_type=self.content_type)


def retriever(
    name: str = "abstract_valid.xml",
    *,
    content_type: str = EPO_OPS_ABSTRACT_ACCEPT,
) -> tuple[EpoOpsAbstractRetriever, FakeEpoOpsClient]:
    client = FakeEpoOpsClient(body=fixture(name), content_type=content_type)
    return EpoOpsAbstractRetriever(client=client), client  # type: ignore[arg-type]


def test_retrieval_uses_exact_docdb_abstract_endpoint() -> None:
    value, client = retriever()

    result = value.retrieve(bibliographic())

    assert result.publication_number == "EPTEST0001A1"
    assert result.publication_docdb == "EP.TEST0001.A1"
    assert result.abstract_text == (
        "Test optical apparatus with a bounded sensing mechanism."
    )
    assert result.abstract_language == "en"
    assert client.calls == [
        (
            (
                "https://ops.epo.org/3.2/rest-services/published-data/"
                "publication/docdb/EP.TEST0001.A1/abstract"
            ),
            "application/exchange+xml",
        )
    ]


def test_abstract_prefers_english_then_falls_back_to_first_nonblank() -> None:
    value, _ = retriever("abstract_fallback.xml")

    result = value.retrieve(bibliographic())

    assert result.abstract_text == "Erste technische Zusammenfassung."
    assert result.abstract_language == "de"


@pytest.mark.parametrize(
    "content_type",
    ["text/html", "application/json", "application/ops+xml", ""],
)
def test_abstract_rejects_wrong_mime(content_type: str) -> None:
    value, _ = retriever(content_type=content_type)

    with pytest.raises(EpoOpsAbstractResponseError):
        value.retrieve(bibliographic())


def test_abstract_accepts_utf8_charset_parameter() -> None:
    value, _ = retriever(content_type="Application/Exchange+XML; charset=UTF-8")

    assert value.retrieve(bibliographic()).abstract_language == "en"


def test_abstract_rejects_missing_abstract() -> None:
    value, _ = retriever("abstract_missing.xml")

    with pytest.raises(EpoOpsAbstractResponseError, match="nonblank abstract"):
        value.retrieve(bibliographic())


def test_abstract_rejects_identity_mismatch() -> None:
    value, _ = retriever("abstract_mismatch.xml")

    with pytest.raises(EpoOpsAbstractResponseError, match="exactly one matching"):
        value.retrieve(bibliographic())


def test_abstract_rejects_unsafe_xml_without_payload_leak() -> None:
    value, _ = retriever("abstract_unsafe_entity.xml")

    with pytest.raises(EpoOpsAbstractXmlParseError) as captured:
        value.retrieve(bibliographic())

    rendered = str(captured.value) + repr(captured.value)
    assert "file:///etc/passwd" not in rendered


def test_verified_mapping_requires_exact_identity_and_exposes_abstract() -> None:
    value, _ = retriever()
    abstract = value.retrieve(bibliographic())

    verified = build_verified_epo_patent_record(
        bibliographic=bibliographic(),
        abstract=abstract,
    )

    assert verified.metadata.source_family is PatentSourceFamily.EPO_OPS
    assert verified.metadata.metadata_verification_state is (
        PatentMetadataVerificationState.VERIFIED
    )
    assert verified.metadata.publication_number == "EPTEST0001A1"
    assert verified.metadata.publication_date == date(2024, 1, 31)
    assert verified.metadata.application_number == "EPTESTAPP0001"
    assert verified.metadata.source_url.endswith(
        "/publication/docdb/EP.TEST0001.A1/abstract"
    )
    assert verified.abstract_text == abstract.abstract_text


def test_verified_mapping_rejects_mismatched_publication() -> None:
    value, _ = retriever()
    abstract = value.retrieve(bibliographic())

    with pytest.raises(EpoOpsPatentSourceMappingError):
        build_verified_epo_patent_record(
            bibliographic=bibliographic(publication_number="EPOTHER0001A1"),
            abstract=abstract,
        )


def test_verified_record_schema_rejects_non_epo_or_unverified_metadata() -> None:
    from app.schemas.epo_ops_abstract import EpoOpsVerifiedPatentRecord
    from app.schemas.patent_source_metadata import PatentSourceMetadata

    with pytest.raises(ValidationError, match="EPO OPS source family"):
        EpoOpsVerifiedPatentRecord(
            metadata=PatentSourceMetadata(
                source_family=PatentSourceFamily.WIPO_PATENTSCOPE,
                publication_number="EPTEST0001A1",
                title="Test optical apparatus",
                source_url="https://patentscope.wipo.int/search/en/detail.jsf",
                metadata_verification_state=PatentMetadataVerificationState.VERIFIED,
                publication_date=date(2024, 1, 31),
            ),
            abstract_text="Technical abstract.",
            abstract_language="en",
        )

    with pytest.raises(ValidationError, match="VERIFIED metadata"):
        EpoOpsVerifiedPatentRecord(
            metadata=PatentSourceMetadata(
                source_family=PatentSourceFamily.EPO_OPS,
                publication_number="EPTEST0001A1",
                title="Test optical apparatus",
                source_url=(
                    "https://ops.epo.org/3.2/rest-services/published-data/"
                    "publication/docdb/EP.TEST0001.A1/abstract"
                ),
                metadata_verification_state=PatentMetadataVerificationState.UNVERIFIED,
                publication_date=date(2024, 1, 31),
            ),
            abstract_text="Technical abstract.",
            abstract_language="en",
        )


def test_verified_mapping_allows_missing_application_number() -> None:
    value, _ = retriever()
    source = bibliographic(application_number=None)
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.application_number is None


def test_verified_mapping_promotes_priority_claims_without_provider_specific_fields() -> (
    None
):
    value, _ = retriever()
    source = bibliographic(
        priority_claims=(
            EpoOpsPriorityClaim(
                priority_number="KR20250015704",
                priority_date=date(2025, 2, 7),
                sequence="1",
                claim_kind="national",
                original_number="10-2025-0015704",
            ),
            EpoOpsPriorityClaim(
                priority_number="US202563756683P",
                priority_date=date(2025, 2, 10),
                sequence="2",
                claim_kind="national",
                original_number="63756683",
            ),
        )
    )
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.priority_claims == (
        PatentPriorityClaim(
            priority_number="KR20250015704",
            priority_date=date(2025, 2, 7),
        ),
        PatentPriorityClaim(
            priority_number="US202563756683P",
            priority_date=date(2025, 2, 10),
        ),
    )


def test_verified_mapping_preserves_empty_priority_claims() -> None:
    value, _ = retriever()
    source = bibliographic(priority_claims=())
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.priority_claims == ()


def test_verified_mapping_selects_original_party_name_per_sequence() -> None:
    value, _ = retriever()
    source = bibliographic(
        applicants=(
            EpoOpsPartyRepresentation(
                name="ELECTRONICS AND TELECOMMUNICATIONS RESEARCH INST [KR]",
                sequence="1",
                data_format="epodoc",
            ),
            EpoOpsPartyRepresentation(
                name="ELECTRONICS AND TELECOMMUNICATIONS RESEARCH INSTITUTE",
                sequence="1",
                data_format="original",
            ),
        ),
        inventors=(
            EpoOpsPartyRepresentation(
                name="HEO SEWAN [KR]",
                sequence="1",
                data_format="epodoc",
            ),
            EpoOpsPartyRepresentation(
                name="KU TAI-YEON [KR]",
                sequence="2",
                data_format="epodoc",
            ),
            EpoOpsPartyRepresentation(
                name="HEO, Sewan",
                sequence="1",
                data_format="original",
            ),
            EpoOpsPartyRepresentation(
                name="KU, Tai-yeon",
                sequence="2",
                data_format="original",
            ),
        ),
    )
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.applicants == (
        PatentParty(name="ELECTRONICS AND TELECOMMUNICATIONS RESEARCH INSTITUTE"),
    )
    assert verified.metadata.inventors == (
        PatentParty(name="HEO, Sewan"),
        PatentParty(name="KU, Tai-yeon"),
    )


def test_verified_mapping_falls_back_to_epodoc_and_keeps_unsequenced_parties_independent() -> (
    None
):
    value, _ = retriever()
    source = bibliographic(
        applicants=(
            EpoOpsPartyRepresentation(
                name="EPODOC ONLY APPLICANT [US]",
                sequence="1",
                data_format="epodoc",
            ),
        ),
        inventors=(
            EpoOpsPartyRepresentation(
                name="First Unsequenced",
                sequence=None,
                data_format="original",
            ),
            EpoOpsPartyRepresentation(
                name="Second Unsequenced",
                sequence=None,
                data_format="epodoc",
            ),
        ),
    )
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.applicants == (
        PatentParty(name="EPODOC ONLY APPLICANT [US]"),
    )
    assert verified.metadata.inventors == (
        PatentParty(name="First Unsequenced"),
        PatentParty(name="Second Unsequenced"),
    )


def test_verified_mapping_preserves_empty_party_collections() -> None:
    value, _ = retriever()
    source = bibliographic(applicants=(), inventors=())
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.applicants == ()
    assert verified.metadata.inventors == ()


def test_verified_mapping_falls_back_to_first_available_other_data_format() -> None:
    value, _ = retriever()
    source = bibliographic(
        applicants=(
            EpoOpsPartyRepresentation(
                name="DOCDB ONLY APPLICANT",
                sequence="1",
                data_format="docdb",
            ),
            EpoOpsPartyRepresentation(
                name="SECOND DOCDB REPRESENTATION",
                sequence="1",
                data_format="docdba",
            ),
        ),
    )
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.applicants == (PatentParty(name="DOCDB ONLY APPLICANT"),)


def test_verified_mapping_promotes_ipc_text_without_provider_sequence() -> None:
    value, _ = retriever()
    source = bibliographic(
        ipc_classifications=(
            EpoOpsIpcClassification(
                text="H02J 3/ 32 A I",
                sequence="1",
            ),
            EpoOpsIpcClassification(
                text="H02J 3/ 46 A I",
                sequence="2",
            ),
        )
    )
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.ipc_classifications == (
        PatentIpcClassification(text="H02J 3/ 32 A I"),
        PatentIpcClassification(text="H02J 3/ 46 A I"),
    )
    dumped = verified.metadata.model_dump()
    assert "sequence" not in dumped["ipc_classifications"][0]


def test_verified_mapping_preserves_empty_ipc_classifications() -> None:
    value, _ = retriever()
    source = bibliographic(ipc_classifications=())
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.ipc_classifications == ()


def test_verified_mapping_promotes_cpc_components_without_provider_provenance() -> None:
    value, _ = retriever()
    source = bibliographic(
        cpc_classifications=(
            EpoOpsCpcClassification(
                section="H",
                class_number="02",
                subclass="J",
                main_group="3",
                subgroup="32",
                sequence="1",
                classification_value="I",
                scheme_office="EP",
                generating_office="US",
            ),
            EpoOpsCpcClassification(
                section="H",
                class_number="02",
                subclass="J",
                main_group="3",
                subgroup="46",
                sequence="2",
                classification_value="I",
                scheme_office="EP",
                generating_office="US",
            ),
        )
    )
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.cpc_classifications == (
        PatentCpcClassification(
            section="H",
            class_number="02",
            subclass="J",
            main_group="3",
            subgroup="32",
        ),
        PatentCpcClassification(
            section="H",
            class_number="02",
            subclass="J",
            main_group="3",
            subgroup="46",
        ),
    )

    dumped = verified.metadata.model_dump()
    cpc = dumped["cpc_classifications"][0]
    assert "sequence" not in cpc
    assert "classification_value" not in cpc
    assert "scheme_office" not in cpc
    assert "generating_office" not in cpc


def test_verified_mapping_preserves_empty_cpc_classifications() -> None:
    value, _ = retriever()
    source = bibliographic(cpc_classifications=())
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    assert verified.metadata.cpc_classifications == ()


def test_verified_mapping_preserves_all_product_metadata_and_keeps_family_id_provider_only() -> (
    None
):
    value, _ = retriever()
    source = bibliographic(
        family_id="100819551",
        priority_claims=(
            EpoOpsPriorityClaim(
                priority_number="KR20250015704",
                priority_date=date(2025, 2, 7),
                sequence="1",
                claim_kind="national",
                original_number="10-2025-0015704",
            ),
            EpoOpsPriorityClaim(
                priority_number="US202563756683P",
                priority_date=date(2025, 2, 10),
                sequence="2",
                claim_kind="national",
                original_number="63756683",
            ),
        ),
        ipc_classifications=(
            EpoOpsIpcClassification(text="H02J 3/ 32 A I", sequence="1"),
            EpoOpsIpcClassification(text="H02J 3/ 46 A I", sequence="2"),
        ),
        cpc_classifications=(
            EpoOpsCpcClassification(
                section="H",
                class_number="02",
                subclass="J",
                main_group="3",
                subgroup="32",
                sequence="1",
                classification_value="I",
                scheme_office="EP",
                generating_office="US",
            ),
            EpoOpsCpcClassification(
                section="H",
                class_number="02",
                subclass="J",
                main_group="3",
                subgroup="46",
                sequence="2",
                classification_value="I",
                scheme_office="EP",
                generating_office="US",
            ),
        ),
        applicants=(
            EpoOpsPartyRepresentation(
                name="SEAT RESEARCH INST [KR]",
                sequence="1",
                data_format="epodoc",
            ),
            EpoOpsPartyRepresentation(
                name="Seat Research Institute",
                sequence="1",
                data_format="original",
            ),
        ),
        inventors=(
            EpoOpsPartyRepresentation(
                name="HEO SEWAN [KR]",
                sequence="1",
                data_format="epodoc",
            ),
            EpoOpsPartyRepresentation(
                name="HEO, Sewan",
                sequence="1",
                data_format="original",
            ),
            EpoOpsPartyRepresentation(
                name="KU TAI-YEON [KR]",
                sequence="2",
                data_format="epodoc",
            ),
            EpoOpsPartyRepresentation(
                name="KU, Tai-yeon",
                sequence="2",
                data_format="original",
            ),
        ),
    )
    abstract = value.retrieve(source)

    verified = build_verified_epo_patent_record(
        bibliographic=source,
        abstract=abstract,
    )

    metadata = verified.metadata
    assert metadata.application_number == "EPTESTAPP0001"
    assert metadata.priority_claims == (
        PatentPriorityClaim(
            priority_number="KR20250015704",
            priority_date=date(2025, 2, 7),
        ),
        PatentPriorityClaim(
            priority_number="US202563756683P",
            priority_date=date(2025, 2, 10),
        ),
    )
    assert metadata.ipc_classifications == (
        PatentIpcClassification(text="H02J 3/ 32 A I"),
        PatentIpcClassification(text="H02J 3/ 46 A I"),
    )
    assert metadata.cpc_classifications == (
        PatentCpcClassification(
            section="H",
            class_number="02",
            subclass="J",
            main_group="3",
            subgroup="32",
        ),
        PatentCpcClassification(
            section="H",
            class_number="02",
            subclass="J",
            main_group="3",
            subgroup="46",
        ),
    )
    assert metadata.applicants == (PatentParty(name="Seat Research Institute"),)
    assert metadata.inventors == (
        PatentParty(name="HEO, Sewan"),
        PatentParty(name="KU, Tai-yeon"),
    )

    dumped = metadata.model_dump()
    assert "family_id" not in dumped
    assert "sequence" not in dumped["priority_claims"][0]
    assert "sequence" not in dumped["ipc_classifications"][0]
    assert "sequence" not in dumped["cpc_classifications"][0]
    assert "classification_value" not in dumped["cpc_classifications"][0]
    assert "scheme_office" not in dumped["cpc_classifications"][0]
    assert "generating_office" not in dumped["cpc_classifications"][0]
