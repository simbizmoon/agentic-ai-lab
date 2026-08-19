"""Tests for strict provider-neutral patent claim parsing."""

from __future__ import annotations

import pytest

from app.research.patent_claim_parser import (
    PatentClaimParseError,
    parse_epo_ops_claim_set,
    parse_epo_ops_claims_record,
)
from app.schemas.epo_ops_claims import (
    EpoOpsClaimSet,
    EpoOpsClaimsRecord,
    EpoOpsClaimText,
)
from app.schemas.patent_claims import (
    PatentClaim,
    PatentClaimSet,
)


def raw_claim_set(
    *,
    language: str = "EN",
    texts: tuple[str, ...] = (
        "1. First independent claim text.",
        "2. Claim depending on claim 1.",
        "3. Claim depending on claim 1 or 2.",
    ),
) -> EpoOpsClaimSet:
    return EpoOpsClaimSet(
        language=language,
        claims=tuple(
            EpoOpsClaimText(position=index, text=text)
            for index, text in enumerate(texts, start=1)
        ),
    )


def test_parser_extracts_claim_number_text_and_provider_position() -> None:
    value = parse_epo_ops_claim_set(raw_claim_set())

    assert value == PatentClaimSet(
        language="EN",
        claims=(
            PatentClaim(
                claim_number=1,
                provider_position=1,
                text="First independent claim text.",
            ),
            PatentClaim(
                claim_number=2,
                provider_position=2,
                text="Claim depending on claim 1.",
            ),
            PatentClaim(
                claim_number=3,
                provider_position=3,
                text="Claim depending on claim 1 or 2.",
            ),
        ),
    )


@pytest.mark.parametrize("language", ["EN", "DE", "FR"])
def test_parser_preserves_language_without_language_specific_dependency_logic(
    language: str,
) -> None:
    value = parse_epo_ops_claim_set(
        raw_claim_set(
            language=language,
            texts=("1. Raw claim one.", "2. Raw claim two."),
        )
    )

    assert value.language == language
    assert [claim.claim_number for claim in value.claims] == [1, 2]


def test_parser_normalizes_body_whitespace_only_after_number_prefix() -> None:
    value = parse_epo_ops_claim_set(
        raw_claim_set(
            texts=(
                "1.   First   claim\nwith provider whitespace.  ",
                "2. Second claim.",
            )
        )
    )

    assert value.claims[0].text == "First claim with provider whitespace."


@pytest.mark.parametrize(
    "text",
    [
        "Claim text without a number.",
        "1) Unsupported delimiter.",
        "1 Claim text without a period.",
        ". Claim text without a number.",
    ],
)
def test_parser_rejects_unobserved_numbering_shapes(text: str) -> None:
    claim_set = EpoOpsClaimSet(
        language="EN",
        claims=(EpoOpsClaimText(position=1, text=text),),
    )

    with pytest.raises(PatentClaimParseError, match="accepted 'N. text' format"):
        parse_epo_ops_claim_set(claim_set)


def test_parser_rejects_number_that_does_not_match_provider_position() -> None:
    claim_set = EpoOpsClaimSet(
        language="EN",
        claims=(
            EpoOpsClaimText(position=1, text="1. First claim."),
            EpoOpsClaimText(position=2, text="3. Provider position mismatch."),
        ),
    )

    with pytest.raises(PatentClaimParseError, match="provider position"):
        parse_epo_ops_claim_set(claim_set)


def test_parser_does_not_extract_dependency_semantics() -> None:
    value = parse_epo_ops_claim_set(
        raw_claim_set(texts=("1. Base claim.", "2. Claim depending on claim 1."))
    )

    dumped = value.model_dump()
    assert dumped["claims"][1] == {
        "claim_number": 2,
        "provider_position": 2,
        "text": "Claim depending on claim 1.",
    }
    assert "depends_on" not in dumped["claims"][1]
    assert "dependency" not in dumped["claims"][1]


def test_record_parser_preserves_publication_identity_and_multilingual_claim_sets() -> (
    None
):
    record = EpoOpsClaimsRecord(
        publication_number="EP1000000B1",
        publication_docdb="EP.1000000.B1",
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/"
            "publication/docdb/EP.1000000.B1/claims"
        ),
        claim_sets=(
            raw_claim_set(
                language="DE",
                texts=("1. Deutscher Anspruch eins.", "2. Deutscher Anspruch zwei."),
            ),
            raw_claim_set(
                language="FR",
                texts=(
                    "1. Revendication française un.",
                    "2. Revendication française deux.",
                ),
            ),
            raw_claim_set(
                language="EN",
                texts=("1. English claim one.", "2. English claim two."),
            ),
        ),
    )

    value = parse_epo_ops_claims_record(record)

    assert value.publication_number == "EP1000000B1"
    assert value.publication_docdb == "EP.1000000.B1"
    assert value.source_endpoint == record.source_endpoint
    assert [claim_set.language for claim_set in value.claim_sets] == ["DE", "FR", "EN"]
    assert [
        [claim.claim_number for claim in claim_set.claims]
        for claim_set in value.claim_sets
    ] == [[1, 2], [1, 2], [1, 2]]
    assert value.claim_sets[2].claims[0].text == "English claim one."


def test_record_parser_reuses_strict_claim_number_contract_for_every_language() -> None:
    record = EpoOpsClaimsRecord(
        publication_number="EP1000000B1",
        publication_docdb="EP.1000000.B1",
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/"
            "publication/docdb/EP.1000000.B1/claims"
        ),
        claim_sets=(
            raw_claim_set(language="DE", texts=("1. Deutscher Anspruch.",)),
            raw_claim_set(language="EN", texts=("2. Wrong provider number.",)),
        ),
    )

    with pytest.raises(PatentClaimParseError, match="provider position"):
        parse_epo_ops_claims_record(record)


def test_claims_document_does_not_add_dependency_or_legal_semantics() -> None:
    record = EpoOpsClaimsRecord(
        publication_number="EP1000000A1",
        publication_docdb="EP.1000000.A1",
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/"
            "publication/docdb/EP.1000000.A1/claims"
        ),
        claim_sets=(
            raw_claim_set(
                texts=("1. Base claim.", "2. Claim depending on claim 1."),
            ),
        ),
    )

    dumped = parse_epo_ops_claims_record(record).model_dump()
    claim = dumped["claim_sets"][0]["claims"][1]

    assert "depends_on" not in claim
    assert "dependency" not in claim
    assert "independent" not in claim
    assert "dependent" not in claim
