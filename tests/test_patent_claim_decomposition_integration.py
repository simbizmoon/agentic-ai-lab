"""Offline integration tests for patent claim acquisition through decomposition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.research.epo_ops_claims_retriever import EpoOpsClaimsRetriever
from app.research.epo_ops_client import EpoOpsHttpResponse
from app.research.patent_claim_decomposition_runtime import (
    PatentClaimDecompositionRuntime,
)
from app.research.patent_claim_parser import parse_epo_ops_claims_record
from app.research.patent_claims_runtime import PatentClaimsRuntimeResult
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsDocumentIdType,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimElement,
)
from app.schemas.patent_claims import PatentClaim

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


@dataclass(frozen=True)
class FakeGeneratedResult:
    decomposition: PatentClaimDecomposition


class EchoClaimDecomposer:
    """Deterministic offline double preserving each parsed claim verbatim."""

    def __init__(self) -> None:
        self.calls: list[PatentClaim] = []

    def decompose(self, claim: PatentClaim) -> FakeGeneratedResult:
        self.calls.append(claim)
        return FakeGeneratedResult(
            decomposition=PatentClaimDecomposition(
                claim_number=claim.claim_number,
                provider_position=claim.provider_position,
                original_claim_text=claim.text,
                elements=(
                    PatentClaimElement(
                        element_number=1,
                        text=claim.text,
                    ),
                ),
            )
        )


def bibliographic_b1() -> EpoOpsBibliographicRecord:
    return EpoOpsBibliographicRecord(
        publication_number="EP1000000B1",
        publication_docdb="EP.1000000.B1",
        title="Fixture patent",
        publication_date=None,
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
        ),
        document_id_type=EpoOpsDocumentIdType.DOCDB,
    )


def test_b1_multilingual_fixture_integrates_through_decomposition_runtime() -> None:
    client = FakeClient("claims_b1_multilingual.xml")
    retriever = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    raw = retriever.retrieve(bibliographic_b1())
    parsed = parse_epo_ops_claims_record(raw)

    claims_result = PatentClaimsRuntimeResult(
        execution=None,  # type: ignore[arg-type]
        claim_documents=(parsed,),
    )
    decomposer = EchoClaimDecomposer()

    result = PatentClaimDecompositionRuntime(
        claim_decomposer=decomposer,
    ).decompose(claims_result)

    assert len(result.decomposition_documents) == 1
    document = result.decomposition_documents[0]

    assert document.publication_number == "EP1000000B1"
    assert document.publication_docdb == "EP.1000000.B1"
    assert document.source_endpoint.endswith(
        "/published-data/publication/docdb/EP.1000000.B1/claims"
    )

    assert tuple(claim_set.language for claim_set in document.claim_sets) == (
        "DE",
        "FR",
        "EN",
    )
    assert tuple(len(claim_set.claims) for claim_set in document.claim_sets) == (
        2,
        2,
        2,
    )
    assert tuple(
        tuple(claim.claim_number for claim in claim_set.claims)
        for claim_set in document.claim_sets
    ) == (
        (1, 2),
        (1, 2),
        (1, 2),
    )
    assert tuple(
        tuple(claim.provider_position for claim in claim_set.claims)
        for claim_set in document.claim_sets
    ) == (
        (1, 2),
        (1, 2),
        (1, 2),
    )

    assert document.claim_sets[0].claims[0].original_claim_text == (
        "Deutscher Anspruch eins."
    )
    assert document.claim_sets[1].claims[0].original_claim_text == (
        "Revendication française un."
    )
    assert document.claim_sets[2].claims[0].original_claim_text == (
        "English claim one."
    )

    assert tuple(claim.text for claim in decomposer.calls) == (
        "Deutscher Anspruch eins.",
        "Deutscher Anspruch zwei.",
        "Revendication française un.",
        "Revendication française deux.",
        "English claim one.",
        "English claim two.",
    )


def test_a1_fixture_integrates_without_dependency_semantics() -> None:
    client = FakeClient("claims_a1.xml")
    retriever = EpoOpsClaimsRetriever(client=client)  # type: ignore[arg-type]

    raw = retriever.retrieve(
        EpoOpsBibliographicRecord(
            publication_number="EP1000000A1",
            publication_docdb="EP.1000000.A1",
            title="Fixture patent",
            publication_date=None,
            source_endpoint=(
                "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
            ),
            document_id_type=EpoOpsDocumentIdType.DOCDB,
        )
    )
    parsed = parse_epo_ops_claims_record(raw)

    claims_result = PatentClaimsRuntimeResult(
        execution=None,  # type: ignore[arg-type]
        claim_documents=(parsed,),
    )

    result = PatentClaimDecompositionRuntime(
        claim_decomposer=EchoClaimDecomposer(),
    ).decompose(claims_result)

    document = result.decomposition_documents[0]
    assert tuple(claim.claim_number for claim in document.claim_sets[0].claims) == (
        1,
        2,
        3,
    )

    dumped = document.model_dump()
    second = dumped["claim_sets"][0]["claims"][1]
    assert "dependency" not in second
    assert "depends_on" not in second
    assert "independent" not in second
    assert "dependent" not in second
