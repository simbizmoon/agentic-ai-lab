"""Offline tests for exact Stage 9 development case persistence."""

from __future__ import annotations

import hashlib
import json
import stat
from decimal import Decimal
from pathlib import Path

import pytest

from app.evals.stage9_development_case_artifact_writer import (
    ARTIFACT_VERSION,
    Stage9DevelopmentCaseArtifact,
    Stage9DevelopmentCaseArtifactError,
    Stage9DevelopmentCaseArtifactWriter,
    _case_status,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopBudget,
    BoundedResearchAgentLoopRequest,
    BoundedResearchAgentLoopResult,
    ResearchAgentLoopDecision,
    ResearchAgentLoopRound,
    ResearchAgentLoopUsage,
    ResearchAgentObservation,
    ResearchAgentObservationFailure,
    ResearchAgentObservationStatus,
    ResearchAgentRoundUsage,
    ResearchAgentTerminationReason,
)
from app.schemas.stage9_development_baseline_run import (
    Stage9DevelopmentCaseStatus,
)

MANIFEST_SHA = "60179543f5290136d434d4f4c72598af8f74eb569a1d06b43c7490320d81e191"
REVIEW_SHA = "f36c0b7bee7cc9548f2f3a36946e4b49293883b69349b4499f2c80d27190cae7"


def _failed_loop_result() -> BoundedResearchAgentLoopResult:
    observation = ResearchAgentObservation(
        observation_id="observation-failed",
        tool_name="bounded_grounded_answer",
        status=ResearchAgentObservationStatus.TOOL_FAILED,
        failure=ResearchAgentObservationFailure(
            code="controlled_failure",
            safe_message="Controlled offline failure.",
            retryable=False,
        ),
    )
    round_usage = ResearchAgentRoundUsage(
        tool_calls=1,
        provider_calls=1,
        recorded_tokens=7,
        elapsed_seconds=0.25,
        external_requests=1,
    )
    round_item = ResearchAgentLoopRound(
        round_number=1,
        plan_id="plan-stage9-001",
        observations=[observation],
        decision=ResearchAgentLoopDecision.TERMINAL_FAILURE,
        rationale="Controlled terminal failure.",
        usage=round_usage,
    )
    request = BoundedResearchAgentLoopRequest(
        goal="Answer the locked development question",
        constraints=["Preserve exact provenance"],
        allowed_tools=["bounded_grounded_answer"],
        budget=BoundedResearchAgentLoopBudget(
            maximum_rounds=1,
            maximum_tool_calls=1,
            maximum_provider_calls=1,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
            maximum_external_requests=1,
        ),
    )
    return BoundedResearchAgentLoopResult(
        request=request,
        rounds=[round_item],
        final_decision=ResearchAgentLoopDecision.TERMINAL_FAILURE,
        termination_reason=ResearchAgentTerminationReason.TERMINAL_FAILURE,
        usage=ResearchAgentLoopUsage(
            rounds=1,
            tool_calls=1,
            provider_calls=1,
            recorded_tokens=7,
            elapsed_seconds=0.25,
            external_requests=1,
        ),
        trace_id="trace-stage9-001",
    )


def _write(tmp_path: Path):
    return Stage9DevelopmentCaseArtifactWriter(tmp_path).write(
        case_id="tech-01",
        execution_id="execution-001",
        manifest_sha256=MANIFEST_SHA,
        review_sha256=REVIEW_SHA,
        response_model_ids=("gpt-5.6-terra",),
        estimated_cost=Decimal("0.12"),
        loop_result=_failed_loop_result(),
    )


def test_writer_persists_canonical_typed_payload_and_checksum(tmp_path: Path) -> None:
    record = _write(tmp_path)
    artifact_path = Path(record.workflow_artifact_path)
    payload = artifact_path.read_bytes()
    loaded = Stage9DevelopmentCaseArtifact.model_validate_json(payload)

    assert loaded.artifact_version == ARTIFACT_VERSION
    assert loaded.loop_result.trace_id == "trace-stage9-001"
    assert loaded.manifest_sha256 == MANIFEST_SHA
    assert record.workflow_artifact_sha256 == hashlib.sha256(payload).hexdigest()
    assert json.loads(payload)["estimated_cost"] == "0.12"
    assert record.status is Stage9DevelopmentCaseStatus.FAILED
    assert record.usage.provider_requests == 1
    assert record.usage.recorded_tokens == 7
    assert (
        (artifact_path.parent / "workflow.json.sha256")
        .read_text()
        .startswith(record.workflow_artifact_sha256)
    )


def test_writer_uses_private_permissions(tmp_path: Path) -> None:
    record = _write(tmp_path)
    artifact_path = Path(record.workflow_artifact_path)

    assert stat.S_IMODE(artifact_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(artifact_path.stat().st_mode) == 0o600
    assert (
        stat.S_IMODE((artifact_path.parent / "workflow.json.sha256").stat().st_mode)
        == 0o600
    )


def test_writer_refuses_overwrite_and_holdout(tmp_path: Path) -> None:
    _write(tmp_path)
    with pytest.raises(Stage9DevelopmentCaseArtifactError, match="already exists"):
        _write(tmp_path)
    with pytest.raises(ValueError, match="development partition"):
        Stage9DevelopmentCaseArtifactWriter(tmp_path).write(
            case_id="tech-02",
            execution_id="execution-002",
            manifest_sha256=MANIFEST_SHA,
            review_sha256=REVIEW_SHA,
            response_model_ids=("gpt-5.6-terra",),
            estimated_cost=Decimal("0.12"),
            loop_result=_failed_loop_result(),
        )


def test_writer_refuses_symbolic_link_case_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "tech-01").symlink_to(outside, target_is_directory=True)

    with pytest.raises(Stage9DevelopmentCaseArtifactError, match="symbolic link"):
        _write(tmp_path)


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (
            ResearchAgentLoopDecision.GOAL_ACHIEVED,
            Stage9DevelopmentCaseStatus.ANSWER_AVAILABLE,
        ),
        (ResearchAgentLoopDecision.ABSTAIN, Stage9DevelopmentCaseStatus.ABSTAINED),
        (
            ResearchAgentLoopDecision.BUDGET_EXHAUSTED,
            Stage9DevelopmentCaseStatus.INCOMPLETE,
        ),
        (ResearchAgentLoopDecision.REPLAN, Stage9DevelopmentCaseStatus.INCOMPLETE),
        (ResearchAgentLoopDecision.HUMAN_REVIEW, Stage9DevelopmentCaseStatus.FAILED),
        (
            ResearchAgentLoopDecision.TERMINAL_FAILURE,
            Stage9DevelopmentCaseStatus.FAILED,
        ),
    ],
)
def test_terminal_decision_maps_to_case_status(
    decision: ResearchAgentLoopDecision,
    expected: Stage9DevelopmentCaseStatus,
) -> None:
    assert _case_status(decision) is expected


@pytest.mark.parametrize("execution_id", ("../escape", "bad/path", " spaced "))
def test_writer_rejects_unsafe_execution_identity(
    tmp_path: Path, execution_id: str
) -> None:
    with pytest.raises(ValueError, match="filesystem-safe"):
        Stage9DevelopmentCaseArtifactWriter(tmp_path).write(
            case_id="tech-01",
            execution_id=execution_id,
            manifest_sha256=MANIFEST_SHA,
            review_sha256=REVIEW_SHA,
            response_model_ids=("gpt-5.6-terra",),
            estimated_cost=Decimal("0.12"),
            loop_result=_failed_loop_result(),
        )
