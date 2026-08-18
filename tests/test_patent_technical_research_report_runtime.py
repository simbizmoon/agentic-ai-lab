"""Tests for the top-level patent technical research report runtime."""

from types import SimpleNamespace

import pytest

from app.research.patent_technical_research_report_runtime import (
    PatentTechnicalResearchReportRuntime,
)
from app.schemas.patent_research_request import PatentResearchRequest


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="How is seat occupancy detected?",
        objective="Find technically relevant patent publications.",
        maximum_search_results=1,
        maximum_sources=1,
    )


class FakeRelevanceRuntime:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        request: object,
        **kwargs: object,
    ) -> object:
        self.calls.append(
            {
                "request": request,
                **kwargs,
            }
        )
        return self.result


class FakeSynthesisRuntime:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def synthesize(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        return self.result


class FakeVerificationRuntime:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[object] = []

    def verify(self, synthesis_result: object) -> object:
        self.calls.append(synthesis_result)
        return self.result


def test_runtime_executes_complete_slice_in_order() -> None:
    relevance = SimpleNamespace(name="relevance")
    report = SimpleNamespace(
        request_id="request-001",
        task_id="patent-technical-relevance",
        report_id="report-001",
    )
    synthesis = SimpleNamespace(
        report=report,
        synthesis=SimpleNamespace(synthesis=SimpleNamespace()),
    )
    verification = SimpleNamespace(
        synthesis_result=synthesis,
        verification=SimpleNamespace(
            request_id="request-001",
            report_id="report-001",
            accepted=True,
        ),
    )

    relevance_runtime = FakeRelevanceRuntime(relevance)
    synthesis_runtime = FakeSynthesisRuntime(synthesis)
    verification_runtime = FakeVerificationRuntime(verification)

    value = PatentTechnicalResearchReportRuntime(
        relevance_runtime=relevance_runtime,  # type: ignore[arg-type]
        synthesis_runtime=synthesis_runtime,  # type: ignore[arg-type]
        verification_runtime=verification_runtime,  # type: ignore[arg-type]
    ).execute(
        request(),
        request_id="request-001",
    )

    assert value.relevance is relevance
    assert value.synthesis is synthesis
    assert value.verification is verification
    assert value.accepted is True

    assert relevance_runtime.calls[0]["request_id"] == "request-001"
    assert synthesis_runtime.calls[0]["relevance_result"] is relevance
    assert verification_runtime.calls == [synthesis]


def test_runtime_rejects_blank_request_id_before_execution() -> None:
    runtime = PatentTechnicalResearchReportRuntime(
        relevance_runtime=FakeRelevanceRuntime(object()),  # type: ignore[arg-type]
        synthesis_runtime=FakeSynthesisRuntime(object()),  # type: ignore[arg-type]
        verification_runtime=FakeVerificationRuntime(object()),  # type: ignore[arg-type]
    )

    with pytest.raises(
        ValueError,
        match="request_id must not be blank",
    ):
        runtime.execute(
            request(),
            request_id=" ",
        )


def test_runtime_rejects_report_request_binding_drift() -> None:
    relevance = SimpleNamespace(name="relevance")
    synthesis = SimpleNamespace(
        report=SimpleNamespace(
            request_id="wrong-request",
            task_id="patent-technical-relevance",
            report_id="report-001",
        )
    )

    runtime = PatentTechnicalResearchReportRuntime(
        relevance_runtime=FakeRelevanceRuntime(relevance),  # type: ignore[arg-type]
        synthesis_runtime=FakeSynthesisRuntime(synthesis),  # type: ignore[arg-type]
        verification_runtime=FakeVerificationRuntime(object()),  # type: ignore[arg-type]
    )

    with pytest.raises(
        RuntimeError,
        match="report request_id drifted",
    ):
        runtime.execute(
            request(),
            request_id="request-001",
        )


def test_runtime_rejects_verification_binding_drift() -> None:
    relevance = SimpleNamespace(name="relevance")
    report = SimpleNamespace(
        request_id="request-001",
        task_id="patent-technical-relevance",
        report_id="report-001",
    )
    synthesis = SimpleNamespace(report=report)
    verification = SimpleNamespace(
        synthesis_result=synthesis,
        verification=SimpleNamespace(
            request_id="request-001",
            report_id="wrong-report",
            accepted=False,
        ),
    )

    runtime = PatentTechnicalResearchReportRuntime(
        relevance_runtime=FakeRelevanceRuntime(relevance),  # type: ignore[arg-type]
        synthesis_runtime=FakeSynthesisRuntime(synthesis),  # type: ignore[arg-type]
        verification_runtime=FakeVerificationRuntime(verification),  # type: ignore[arg-type]
    )

    with pytest.raises(
        RuntimeError,
        match="verification report_id drifted",
    ):
        runtime.execute(
            request(),
            request_id="request-001",
        )
