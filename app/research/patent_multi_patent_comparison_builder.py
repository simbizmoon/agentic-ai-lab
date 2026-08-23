"""Deterministic construction of multi-patent technical comparisons."""

from __future__ import annotations

from app.schemas.patent_claim_chart import PatentClaimChart
from app.schemas.patent_multi_patent_comparison import (
    PatentMultiPatentComparison,
    PatentMultiPatentComparisonClaim,
    PatentMultiPatentComparisonClaimSet,
    PatentMultiPatentComparisonRow,
    PatentPriorArtPublicationComparison,
)
from app.schemas.patent_prior_art_evidence_mapping import (
    PatentPriorArtEvidenceEvaluation,
)

PATENT_MULTI_PATENT_COMPARISON_SCOPE_NOTICE = (
    "This is a technical multi-patent comparison only. "
    "It does not determine novelty, anticipation, obviousness, inventive step, "
    "validity, invalidity, infringement, freedom to operate, legal status, "
    "claim scope, essentiality, or claim dependency."
)


class DeterministicPatentMultiPatentComparisonBuilder:
    """Group existing chart evaluations by prior-art publication."""

    def build(
        self,
        chart: PatentClaimChart,
    ) -> PatentMultiPatentComparison:
        publication_axis: list[str] = []
        claim_sets: list[PatentMultiPatentComparisonClaimSet] = []

        for claim_set in chart.claim_sets:
            claims: list[PatentMultiPatentComparisonClaim] = []

            for claim in claim_set.claims:
                rows: list[PatentMultiPatentComparisonRow] = []

                for row in claim.rows:
                    grouped: dict[str, list[PatentPriorArtEvidenceEvaluation]] = {}

                    for evaluation in row.evaluations:
                        publication_number = evaluation.publication_number
                        if publication_number not in publication_axis:
                            publication_axis.append(publication_number)
                        grouped.setdefault(publication_number, []).append(evaluation)

                    publications = tuple(
                        PatentPriorArtPublicationComparison(
                            publication_number=publication_number,
                            evaluations=tuple(grouped[publication_number]),
                        )
                        for publication_number in publication_axis
                        if publication_number in grouped
                    )

                    rows.append(
                        PatentMultiPatentComparisonRow(
                            row_number=row.row_number,
                            claim_number=row.claim_number,
                            provider_position=row.provider_position,
                            element_number=row.element_number,
                            element_text=row.element_text,
                            publications=publications,
                        )
                    )

                claims.append(
                    PatentMultiPatentComparisonClaim(
                        claim_number=claim.claim_number,
                        provider_position=claim.provider_position,
                        original_claim_text=claim.original_claim_text,
                        rows=tuple(rows),
                    )
                )

            claim_sets.append(
                PatentMultiPatentComparisonClaimSet(
                    language=claim_set.language,
                    claims=tuple(claims),
                )
            )

        return PatentMultiPatentComparison(
            target_publication_number=chart.target_publication_number,
            target_publication_docdb=chart.target_publication_docdb,
            target_source_endpoint=chart.target_source_endpoint,
            prior_art_publications=tuple(publication_axis),
            claim_sets=tuple(claim_sets),
            scope_notice=PATENT_MULTI_PATENT_COMPARISON_SCOPE_NOTICE,
        )
