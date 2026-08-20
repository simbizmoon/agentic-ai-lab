"""Deterministic construction of human-reviewable patent claim charts."""

from __future__ import annotations

from app.schemas.patent_claim_chart import (
    PatentClaimChart,
    PatentClaimChartClaim,
    PatentClaimChartClaimSet,
    PatentClaimChartRow,
)
from app.schemas.patent_prior_art_evidence_mapping import (
    PatentClaimsDocumentEvidenceMapping,
)

PATENT_CLAIM_CHART_SCOPE_NOTICE = (
    "This claim chart is a technical comparison artifact only. "
    "It does not determine novelty, anticipation, obviousness, inventive step, "
    "validity, invalidity, infringement, freedom to operate, legal status, "
    "claim scope, essentiality, or claim dependency."
)


class DeterministicPatentClaimChartBuilder:
    """Build a structured claim chart without adding new technical judgments."""

    def build(
        self,
        mapping: PatentClaimsDocumentEvidenceMapping,
    ) -> PatentClaimChart:
        row_number = 1
        claim_sets: list[PatentClaimChartClaimSet] = []

        for claim_set in mapping.claim_sets:
            claims: list[PatentClaimChartClaim] = []

            for claim in claim_set.claims:
                rows: list[PatentClaimChartRow] = []

                for element in claim.elements:
                    rows.append(
                        PatentClaimChartRow(
                            row_number=row_number,
                            claim_number=claim.claim_number,
                            provider_position=claim.provider_position,
                            element_number=element.element_number,
                            element_text=element.element_text,
                            evaluations=element.evaluations,
                        )
                    )
                    row_number += 1

                claims.append(
                    PatentClaimChartClaim(
                        claim_number=claim.claim_number,
                        provider_position=claim.provider_position,
                        original_claim_text=claim.original_claim_text,
                        rows=tuple(rows),
                    )
                )

            claim_sets.append(
                PatentClaimChartClaimSet(
                    language=claim_set.language,
                    claims=tuple(claims),
                )
            )

        return PatentClaimChart(
            target_publication_number=mapping.publication_number,
            target_publication_docdb=mapping.publication_docdb,
            target_source_endpoint=mapping.source_endpoint,
            claim_sets=tuple(claim_sets),
            scope_notice=PATENT_CLAIM_CHART_SCOPE_NOTICE,
        )
