"""Runtime for decomposing all parsed claims while preserving document identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.research.patent_claim_decomposition_grounding_validator import (
    PatentClaimDecompositionGroundingValidator,
)
from app.research.patent_claims_runtime import PatentClaimsRuntimeResult
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimsDocumentDecomposition,
    PatentClaimSetDecomposition,
)
from app.schemas.patent_claims import PatentClaim


class PatentClaimElementDecompositionResultProtocol(Protocol):
    """Minimal result contract required from one claim decomposer."""

    decomposition: PatentClaimDecomposition


class PatentClaimElementDecomposerProtocol(Protocol):
    """Decompose one parsed patent claim."""

    def decompose(
        self,
        claim: PatentClaim,
    ) -> PatentClaimElementDecompositionResultProtocol: ...


@dataclass(frozen=True)
class PatentClaimDecompositionRuntimeResult:
    """Original claims runtime result plus separate decomposition documents."""

    claims_result: PatentClaimsRuntimeResult
    decomposition_documents: tuple[PatentClaimsDocumentDecomposition, ...]


class PatentClaimDecompositionRuntime:
    """Decompose every acquired claim without changing acquisition semantics."""

    def __init__(
        self,
        *,
        claim_decomposer: PatentClaimElementDecomposerProtocol,
        grounding_validator: PatentClaimDecompositionGroundingValidator | None = None,
    ) -> None:
        self._claim_decomposer = claim_decomposer
        self._grounding_validator = (
            grounding_validator or PatentClaimDecompositionGroundingValidator()
        )

    def decompose(
        self,
        claims_result: PatentClaimsRuntimeResult,
    ) -> PatentClaimDecompositionRuntimeResult:
        """Return ordered grounded decompositions for every parsed claim."""

        if not claims_result.claim_documents:
            return PatentClaimDecompositionRuntimeResult(
                claims_result=claims_result,
                decomposition_documents=(),
            )

        documents: list[PatentClaimsDocumentDecomposition] = []

        for document in claims_result.claim_documents:
            decomposed_sets: list[PatentClaimSetDecomposition] = []

            for claim_set in document.claim_sets:
                decomposed_claims: list[PatentClaimDecomposition] = []

                for claim in claim_set.claims:
                    generated = self._claim_decomposer.decompose(claim)
                    decomposition = self._grounding_validator.validate(
                        claim=claim,
                        decomposition=generated.decomposition,
                    )
                    decomposed_claims.append(decomposition)

                decomposed_sets.append(
                    PatentClaimSetDecomposition(
                        language=claim_set.language,
                        claims=tuple(decomposed_claims),
                    )
                )

            documents.append(
                PatentClaimsDocumentDecomposition(
                    publication_number=document.publication_number,
                    publication_docdb=document.publication_docdb,
                    source_endpoint=document.source_endpoint,
                    claim_sets=tuple(decomposed_sets),
                )
            )

        return PatentClaimDecompositionRuntimeResult(
            claims_result=claims_result,
            decomposition_documents=tuple(documents),
        )
