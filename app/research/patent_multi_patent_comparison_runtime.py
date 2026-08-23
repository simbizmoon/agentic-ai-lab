"""Runtime for deterministic multi-patent technical comparison generation."""

from __future__ import annotations

from dataclasses import dataclass

from app.research.patent_claim_chart_runtime import PatentClaimChartRuntimeResult
from app.research.patent_multi_patent_comparison_builder import (
    DeterministicPatentMultiPatentComparisonBuilder,
)
from app.schemas.patent_multi_patent_comparison import PatentMultiPatentComparison


@dataclass(frozen=True)
class PatentMultiPatentComparisonRuntimeResult:
    """Input claim-chart result plus deterministic comparison artifacts."""

    chart_result: PatentClaimChartRuntimeResult
    comparisons: tuple[PatentMultiPatentComparison, ...]


class PatentMultiPatentComparisonRuntime:
    """Build one technical comparison for every target claim chart."""

    def __init__(
        self,
        *,
        builder: DeterministicPatentMultiPatentComparisonBuilder | None = None,
    ) -> None:
        self._builder = builder or DeterministicPatentMultiPatentComparisonBuilder()

    def build(
        self,
        chart_result: PatentClaimChartRuntimeResult,
    ) -> PatentMultiPatentComparisonRuntimeResult:
        comparisons = tuple(self._builder.build(chart) for chart in chart_result.charts)

        return PatentMultiPatentComparisonRuntimeResult(
            chart_result=chart_result,
            comparisons=comparisons,
        )
