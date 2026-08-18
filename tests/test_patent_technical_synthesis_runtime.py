"""Tests for patent technical synthesis runtime composition."""

from types import SimpleNamespace

from app.research.openai_patent_technical_synthesizer import (
    PatentTechnicalSynthesisGenerationResult,
)
from app.research.patent_technical_synthesis_runtime import (
    PatentTechnicalSynthesisRuntime,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_technical_synthesis import PatentTechnicalSynthesis


class FakeReportBuilder:
    def __init__(self, report: object) -> None:
        self.report = report
        self.calls: list[dict[str, object]] = []

    def build(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        return self.report


class FakeSynthesizer:
    def __init__(
        self,
        result: PatentTechnicalSynthesisGenerationResult,
    ) -> None:
        self.result = result
        self.calls: list[object] = []

    def synthesize(self, report: object) -> object:
        self.calls.append(report)
        return self.result


def test_runtime_preserves_relevance_binding() -> None:
    request = PatentResearchRequest(
        question="How is seat occupancy detected?",
        objective="Find technically relevant patent publications.",
        maximum_search_results=1,
        maximum_sources=1,
    )
    execution = SimpleNamespace(collection=SimpleNamespace(request=request))
    relevance_result = SimpleNamespace(
        research=SimpleNamespace(execution=execution),
        relevance=SimpleNamespace(execution=execution),
    )
    report = SimpleNamespace(request_id="request-001")
    synthesis = PatentTechnicalSynthesisGenerationResult(
        synthesis=PatentTechnicalSynthesis(
            overall_summary="Summary.",
            finding_summaries=[],
        ),
        response_id="resp-001",
        request_id="req-001",
        usage=None,
        elapsed_seconds=0.1,
    )

    builder = FakeReportBuilder(report)
    synthesizer = FakeSynthesizer(synthesis)

    value = PatentTechnicalSynthesisRuntime(
        report_builder=builder,  # type: ignore[arg-type]
        synthesizer=synthesizer,  # type: ignore[arg-type]
    ).synthesize(
        request=request,
        relevance_result=relevance_result,  # type: ignore[arg-type]
        request_id="request-001",
    )

    assert value.report is report
    assert value.synthesis is synthesis
    assert synthesizer.calls == [report]
