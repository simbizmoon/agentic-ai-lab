"""Runtime for deterministic patent claim-chart generation."""

from __future__ import annotations

from dataclasses import dataclass

from app.research.patent_claim_chart_builder import (
    DeterministicPatentClaimChartBuilder,
)
from app.research.patent_prior_art_evidence_mapping_runtime import (
    PatentPriorArtEvidenceMappingRuntimeResult,
)
from app.schemas.patent_claim_chart import PatentClaimChart


@dataclass(frozen=True)
class PatentClaimChartRuntimeResult:
    """Input mapping result plus deterministic claim-chart artifacts."""

    mapping_result: PatentPriorArtEvidenceMappingRuntimeResult
    charts: tuple[PatentClaimChart, ...]


class PatentClaimChartRuntime:
    """Build one claim chart for every mapped target patent document."""

    def __init__(
        self,
        *,
        builder: DeterministicPatentClaimChartBuilder | None = None,
    ) -> None:
        self._builder = builder or DeterministicPatentClaimChartBuilder()

    def build(
        self,
        mapping_result: PatentPriorArtEvidenceMappingRuntimeResult,
    ) -> PatentClaimChartRuntimeResult:
        charts = tuple(
            self._builder.build(mapping) for mapping in mapping_result.mapping_documents
        )

        return PatentClaimChartRuntimeResult(
            mapping_result=mapping_result,
            charts=charts,
        )
