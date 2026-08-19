"""Tests for document-level patent claim decomposition runtime."""

from dataclasses import dataclass

import pytest

from app.research.patent_claim_decomposition_grounding_validator import (
    PatentClaimDecompositionGroundingError,
)
from app.research.patent_claim_decomposition_runtime import (
    PatentClaimDecompositionRuntime,
)
from app.research.patent_claims_runtime import (
    PatentClaimsRuntimeResult,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimElement,
)
from app.schemas.patent_claims import (
    PatentClaim,
    PatentClaimsDocument,
    PatentClaimSet,
)


@dataclass(frozen=True)
class FakeGeneratedResult:
    decomposition: PatentClaimDecomposition


class FakeDecomposer:
    def __init__(self, *, invent_wording: bool = False) -> None:
        self.invent_wording = invent_wording
        self.calls: list[PatentClaim] = []

    def decompose(self, claim: PatentClaim) -> FakeGeneratedResult:
        self.calls.append(claim)
        text = "invented capacitive component" if self.invent_wording else claim.text
        return FakeGeneratedResult(
            decomposition=PatentClaimDecomposition(
                claim_number=claim.claim_number,
                provider_position=claim.provider_position,
                original_claim_text=claim.text,
                elements=(
                    PatentClaimElement(
                        element_number=1,
                        text=text,
                    ),
                ),
            )
        )


def claim(number: int, text: str) -> PatentClaim:
    return PatentClaim(
        claim_number=number,
        provider_position=number,
        text=text,
    )


def document() -> PatentClaimsDocument:
    return PatentClaimsDocument(
        publication_number="EP123456B1",
        publication_docdb="EP.123456.B1",
        source_endpoint="/published-data/publication/docdb/EP.123456.B1/claims",
        claim_sets=(
            PatentClaimSet(
                language="DE",
                claims=(
                    claim(1, "System mit einem Sensor."),
                    claim(2, "System mit einem Controller."),
                ),
            ),
            PatentClaimSet(
                language="EN",
                claims=(
                    claim(1, "A system comprising a sensor."),
                    claim(2, "A system comprising a controller."),
                ),
            ),
        ),
    )


def claims_result(
    documents: tuple[PatentClaimsDocument, ...],
) -> PatentClaimsRuntimeResult:
    return PatentClaimsRuntimeResult(
        execution=None,  # type: ignore[arg-type]
        claim_documents=documents,
    )


def test_runtime_preserves_document_language_and_claim_order() -> None:
    source = claims_result((document(),))
    decomposer = FakeDecomposer()

    result = PatentClaimDecompositionRuntime(
        claim_decomposer=decomposer,
    ).decompose(source)

    assert result.claims_result is source
    assert len(result.decomposition_documents) == 1

    decomposed = result.decomposition_documents[0]
    assert decomposed.publication_number == "EP123456B1"
    assert decomposed.publication_docdb == "EP.123456.B1"
    assert tuple(item.language for item in decomposed.claim_sets) == ("DE", "EN")
    assert tuple(item.claim_number for item in decomposed.claim_sets[0].claims) == (
        1,
        2,
    )
    assert tuple(item.claim_number for item in decomposed.claim_sets[1].claims) == (
        1,
        2,
    )

    assert [(item.claim_number, item.text) for item in decomposer.calls] == [
        (1, "System mit einem Sensor."),
        (2, "System mit einem Controller."),
        (1, "A system comprising a sensor."),
        (2, "A system comprising a controller."),
    ]


def test_runtime_returns_empty_without_decomposer_calls_for_zero_documents() -> None:
    source = claims_result(())
    decomposer = FakeDecomposer()

    result = PatentClaimDecompositionRuntime(
        claim_decomposer=decomposer,
    ).decompose(source)

    assert result.claims_result is source
    assert result.decomposition_documents == ()
    assert decomposer.calls == []


def test_runtime_fails_fast_when_grounding_validation_rejects_output() -> None:
    source = claims_result((document(),))
    decomposer = FakeDecomposer(invent_wording=True)

    with pytest.raises(
        PatentClaimDecompositionGroundingError,
        match="wording or order not grounded",
    ):
        PatentClaimDecompositionRuntime(
            claim_decomposer=decomposer,
        ).decompose(source)

    assert len(decomposer.calls) == 1


def test_runtime_preserves_multiple_document_order() -> None:
    first = document()
    second = first.model_copy(
        update={
            "publication_number": "EP999999A1",
            "publication_docdb": "EP.999999.A1",
            "source_endpoint": (
                "/published-data/publication/docdb/EP.999999.A1/claims"
            ),
        }
    )
    source = claims_result((first, second))

    result = PatentClaimDecompositionRuntime(
        claim_decomposer=FakeDecomposer(),
    ).decompose(source)

    assert tuple(item.publication_docdb for item in result.decomposition_documents) == (
        "EP.123456.B1",
        "EP.999999.A1",
    )
