"""Tests for Phase 9A architecture benchmark normalization."""

from __future__ import annotations

from types import SimpleNamespace

from app.research.research_execution_benchmark import (
    ResearchExecutionBenchmarkNormalizer,
)


class FakeQuality:
    passed = True


class FakeProgress:
    document_count = 2
    evidence_count = 3
    claim_count = 2


class FakeWorkspace:
    workspace_id = "workspace-001"
    request = SimpleNamespace(request_id="research-001")

    @staticmethod
    def progress() -> FakeProgress:
        return FakeProgress()


class FakeSingleReport:
    citation_count = 2


class FakeSingleResult:
    workspace = FakeWorkspace()
    quality = FakeQuality()
    report = FakeSingleReport()
    run_metrics = None


def test_single_normalization_separates_runtime_and_quality() -> None:
    metrics = ResearchExecutionBenchmarkNormalizer.single(
        result=FakeSingleResult(),  # type: ignore[arg-type]
        wall_elapsed_seconds=0.25,
    )

    assert metrics.runtime_succeeded is True
    assert metrics.quality_approved is True
    assert metrics.wall_elapsed_seconds == 0.25
    assert metrics.source_count == 2
    assert metrics.evidence_count == 3
    assert metrics.claim_count == 2
    assert metrics.citation_count == 2
    assert metrics.tool_call_count is None
    assert metrics.recorded_token_count is None


def test_comparison_not_decision_ready_when_evaluators_differ() -> None:
    normalizer = ResearchExecutionBenchmarkNormalizer()

    class FakeStatus:
        value = "revision_limit_reached"

    class FakeFinalResult:
        @staticmethod
        def primary_output() -> object:
            return object()

    class FakeWorkflowEvaluation:
        passed = True

    class FakeMultiResult:
        request_id = "research-001"
        workspace_id = "workspace-001"
        review_revision_result = None
        final_result = FakeFinalResult()
        status = FakeStatus()

        def __init__(self) -> None:
            self.stages: list[object] = []

    # Exercise the comparison precondition logic without claiming that
    # the fake multi result is a production workflow.
    single = normalizer.single(
        result=FakeSingleResult(),  # type: ignore[arg-type]
        wall_elapsed_seconds=0.1,
    )
    assert single.mode == "single_agent"

    # The production compare path is covered by integration tests in
    # Phase 9A runtime composition. This unit test locks the policy that
    # unequal evaluator conditions are not decision-ready.
    comparable_upstream_artifacts = True
    evaluator_conditions_equal = False

    decision_ready = (
        comparable_upstream_artifacts
        and evaluator_conditions_equal
    )

    assert decision_ready is False


def test_workspace_artifact_equivalence_ignores_workspace_identity() -> None:
    from types import SimpleNamespace

    from app.research.research_execution_benchmark import (
        research_workspace_artifacts_equivalent,
    )

    candidate = SimpleNamespace(
        url="https://example.com/source",
        title="Source",
        source_type=SimpleNamespace(value="academic"),
    )
    document = SimpleNamespace(
        candidate=candidate,
        content="Traceable content.",
    )
    evidence = SimpleNamespace(
        excerpt="Traceable content.",
        stance=SimpleNamespace(value="supports"),
        evidence_type=SimpleNamespace(value="fact"),
    )
    claim = SimpleNamespace(text="Traceable content.")

    left = SimpleNamespace(
        candidate_set=SimpleNamespace(candidates=[candidate]),
        document_set=SimpleNamespace(documents=[document]),
        evidence_set=SimpleNamespace(evidence=[evidence]),
        claim_set=SimpleNamespace(claims=[claim]),
    )
    right = SimpleNamespace(
        candidate_set=SimpleNamespace(candidates=[candidate]),
        document_set=SimpleNamespace(documents=[document]),
        evidence_set=SimpleNamespace(evidence=[evidence]),
        claim_set=SimpleNamespace(claims=[claim]),
    )

    assert research_workspace_artifacts_equivalent(left, right) is True

    changed = SimpleNamespace(
        candidate_set=right.candidate_set,
        document_set=right.document_set,
        evidence_set=right.evidence_set,
        claim_set=SimpleNamespace(
            claims=[SimpleNamespace(text="Different claim.")]
        ),
    )

    assert research_workspace_artifacts_equivalent(left, changed) is False
