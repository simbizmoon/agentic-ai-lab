"""Deterministic grounding checks for patent claim-element decompositions."""

from __future__ import annotations

import re

from app.schemas.patent_claim_decomposition import PatentClaimDecomposition
from app.schemas.patent_claims import PatentClaim

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


class PatentClaimDecompositionGroundingError(RuntimeError):
    """A decomposition violated deterministic source-grounding invariants."""


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).casefold() for match in _TOKEN_PATTERN.finditer(text))


def _is_ordered_subsequence(
    candidate: tuple[str, ...],
    source: tuple[str, ...],
) -> bool:
    if not candidate:
        return False

    source_index = 0
    for token in candidate:
        while source_index < len(source) and token not in source[source_index]:
            source_index += 1
        if source_index >= len(source):
            return False
        source_index += 1
    return True


class PatentClaimDecompositionGroundingValidator:
    """Validate only deterministic identity and lexical-grounding properties."""

    def validate(
        self,
        *,
        claim: PatentClaim,
        decomposition: PatentClaimDecomposition,
    ) -> PatentClaimDecomposition:
        """Return decomposition when it remains deterministically grounded."""

        if decomposition.claim_number != claim.claim_number:
            raise PatentClaimDecompositionGroundingError(
                "claim number drifted from source patent claim"
            )

        if decomposition.provider_position != claim.provider_position:
            raise PatentClaimDecompositionGroundingError(
                "provider position drifted from source patent claim"
            )

        if decomposition.original_claim_text != claim.text:
            raise PatentClaimDecompositionGroundingError(
                "original claim text drifted from source patent claim"
            )

        source_tokens = _tokens(claim.text)
        if not source_tokens:
            raise PatentClaimDecompositionGroundingError(
                "source patent claim did not contain lexical tokens"
            )

        for element in decomposition.elements:
            element_tokens = _tokens(element.text)
            if not element_tokens:
                raise PatentClaimDecompositionGroundingError(
                    "claim element did not contain lexical tokens"
                )

            if not _is_ordered_subsequence(element_tokens, source_tokens):
                raise PatentClaimDecompositionGroundingError(
                    "claim element introduced wording or order not grounded "
                    "in the source patent claim"
                )

        return decomposition
