"""Strict parsing of raw provider patent claim text into bounded claim records."""

from __future__ import annotations

import re

from app.schemas.epo_ops_claims import EpoOpsClaimSet, EpoOpsClaimsRecord
from app.schemas.patent_claims import (
    PatentClaim,
    PatentClaimsDocument,
    PatentClaimSet,
)

_CLAIM_PREFIX_PATTERN = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$", re.DOTALL)


class PatentClaimParseError(RuntimeError):
    """Raw provider claim text did not satisfy the bounded parsing contract."""


def parse_epo_ops_claim_set(claim_set: EpoOpsClaimSet) -> PatentClaimSet:
    """Parse only observed ``N. text`` claim prefixes without dependency inference."""

    parsed: list[PatentClaim] = []

    for raw_claim in claim_set.claims:
        match = _CLAIM_PREFIX_PATTERN.fullmatch(raw_claim.text)
        if match is None:
            raise PatentClaimParseError(
                "EPO OPS claim text did not match the accepted 'N. text' format."
            )

        claim_number = int(match.group(1))
        text = " ".join(match.group(2).split())
        if not text:
            raise PatentClaimParseError(
                "EPO OPS claim text omitted nonblank content after its number."
            )

        if claim_number != raw_claim.position:
            raise PatentClaimParseError(
                "EPO OPS parsed claim number did not match provider position."
            )

        parsed.append(
            PatentClaim(
                claim_number=claim_number,
                provider_position=raw_claim.position,
                text=text,
            )
        )

    return PatentClaimSet(
        language=claim_set.language,
        claims=tuple(parsed),
    )


def parse_epo_ops_claims_record(record: EpoOpsClaimsRecord) -> PatentClaimsDocument:
    """Parse all provider claim sets while preserving exact publication identity."""

    return PatentClaimsDocument(
        publication_number=record.publication_number,
        publication_docdb=record.publication_docdb,
        source_endpoint=record.source_endpoint,
        claim_sets=tuple(
            parse_epo_ops_claim_set(claim_set) for claim_set in record.claim_sets
        ),
    )
