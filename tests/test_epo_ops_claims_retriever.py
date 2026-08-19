"""Tests for provider-level EPO OPS raw patent-claim retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.research.epo_ops_claims_retriever import (
    EPO_OPS_CLAIMS_ACCEPT,
    EpoOpsClaimsResponseError,
    EpoOpsClaimsRetriever,
    EpoOpsClaimsXmlParseError,
)
from app.research.epo_ops_client import EpoOpsHttpResponse
from app.research.patent_claim_parser import parse_epo_ops_claims_record
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsDocumentIdType,
)
from app.schemas.epo_ops_claims import EpoOpsClaimSet, EpoOpsClaimText

FIXTURES = Path(__file__).parent / "fixtures" / "epo_ops"


class FakeClient:
    def __init__(self, fixture: str) -> None:
        self.body = (FIXTURES / fixture).read_bytes()
        self.calls: list[tuple[str, str]] = []

    def authenticated_get_response(
        self,
        *,
        endpoint: str,
        accept: str,
        extra_headers: dict[str, str] | None = None,
    ) -> EpoOpsHttpResponse:
        assert extra_headers is None
        self.calls.append((endpoint, accept))
        return EpoOpsHttpResponse(
            body=self.body,
            content_type="application/fulltext+xml;charset=utf-8",
        )


def bibliographic(
    *,
    publication_number: str = "EP1000000A1",
    publication_docdb: str = "EP.1000000.A1",
) -> EpoOpsBibliographicRecord:
    return EpoOpsBibliographicRecord(
        publication_number=publication_number,
        publication_docdb=publication_docdb,
        title="Fixture patent",
        publication_date=None,
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
        ),
        document_id_type=EpoOpsDocumentIdType.DOCDB,
    )


def test_retriever_uses_exact_docdb_claims_endpoint_and_accept_contract() -> None:
    client = FakeClient("claims_a1.xml")
    value = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    value.retrieve(bibliographic())

    assert client.calls == [
        (
            (
                "https://ops.epo.org/3.2/rest-services/published-data/"
                "publication/docdb/EP.1000000.A1/claims"
            ),
            EPO_OPS_CLAIMS_ACCEPT,
        )
    ]


def test_retriever_parses_each_claim_text_as_provider_order_not_claim_wrapper() -> None:
    client = FakeClient("claims_a1.xml")
    value = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    record = value.retrieve(bibliographic())

    assert record.publication_number == "EP1000000A1"
    assert record.publication_docdb == "EP.1000000.A1"
    assert record.claim_sets == (
        EpoOpsClaimSet(
            language="EN",
            claims=(
                EpoOpsClaimText(position=1, text="1. First independent claim text."),
                EpoOpsClaimText(position=2, text="2. Claim depending on claim 1."),
                EpoOpsClaimText(
                    position=3,
                    text="3. Claim depending on claim 1 or 2.",
                ),
            ),
        ),
    )


def test_retriever_preserves_multiple_language_claim_sets_in_provider_order() -> None:
    client = FakeClient("claims_b1_multilingual.xml")
    value = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    record = value.retrieve(
        bibliographic(
            publication_number="EP1000000B1",
            publication_docdb="EP.1000000.B1",
        )
    )

    assert [claim_set.language for claim_set in record.claim_sets] == [
        "DE",
        "FR",
        "EN",
    ]
    assert [len(claim_set.claims) for claim_set in record.claim_sets] == [2, 2, 2]
    assert record.claim_sets[2].claims[0].text == "1. English claim one."


def test_retriever_rejects_docdb_identity_mismatch() -> None:
    client = FakeClient("claims_b1_multilingual.xml")
    value = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    with pytest.raises(
        EpoOpsClaimsResponseError,
        match="exactly one matching publication",
    ):
        value.retrieve(bibliographic())


def test_retriever_rejects_blank_claim_text() -> None:
    client = FakeClient("claims_blank_text.xml")
    value = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    with pytest.raises(EpoOpsClaimsResponseError, match="claim-text item was blank"):
        value.retrieve(bibliographic())


def test_retriever_rejects_malformed_xml() -> None:
    client = FakeClient("claims_a1.xml")
    client.body = b"<broken>"
    value = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    with pytest.raises(EpoOpsClaimsXmlParseError, match="malformed or unsafe"):
        value.retrieve(bibliographic())


def test_retriever_rejects_invalid_docdb_before_network_call() -> None:
    client = FakeClient("claims_a1.xml")
    value = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    with pytest.raises(EpoOpsClaimsResponseError, match="invalid DOCDB input"):
        value.retrieve(bibliographic(publication_docdb="EP1000000"))

    assert client.calls == []


def test_provider_claim_schema_is_strict_frozen_and_uses_order_not_legal_number() -> (
    None
):
    claim = EpoOpsClaimText(position=1, text="1. Raw provider claim.")

    assert claim.position == 1
    assert claim.text == "1. Raw provider claim."

    with pytest.raises(ValidationError):
        EpoOpsClaimText(position=0, text="Claim.")
    with pytest.raises(ValidationError):
        EpoOpsClaimText(position=1, text="   ")
    with pytest.raises(ValidationError):
        claim.text = "Changed"


def test_claim_retrieval_and_parsing_integrate_for_exact_docdb_publication() -> None:
    client = FakeClient("claims_b1_multilingual.xml")
    retriever = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    raw = retriever.retrieve(
        bibliographic(
            publication_number="EP1000000B1",
            publication_docdb="EP.1000000.B1",
        )
    )
    parsed = parse_epo_ops_claims_record(raw)

    assert parsed.publication_number == "EP1000000B1"
    assert parsed.publication_docdb == "EP.1000000.B1"
    assert parsed.source_endpoint == (
        "https://ops.epo.org/3.2/rest-services/published-data/"
        "publication/docdb/EP.1000000.B1/claims"
    )
    assert [claim_set.language for claim_set in parsed.claim_sets] == [
        "DE",
        "FR",
        "EN",
    ]
    assert [
        [claim.claim_number for claim in claim_set.claims]
        for claim_set in parsed.claim_sets
    ] == [[1, 2], [1, 2], [1, 2]]
    assert [
        [claim.provider_position for claim in claim_set.claims]
        for claim_set in parsed.claim_sets
    ] == [[1, 2], [1, 2], [1, 2]]
    assert parsed.claim_sets[2].claims[0].text == "English claim one."


def test_claim_retrieval_and_parsing_preserve_identity_boundary_before_parsing() -> (
    None
):
    client = FakeClient("claims_b1_multilingual.xml")
    retriever = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    with pytest.raises(
        EpoOpsClaimsResponseError,
        match="exactly one matching publication",
    ):
        raw = retriever.retrieve(
            bibliographic(
                publication_number="EP1000000A1",
                publication_docdb="EP.1000000.A1",
            )
        )
        parse_epo_ops_claims_record(raw)
