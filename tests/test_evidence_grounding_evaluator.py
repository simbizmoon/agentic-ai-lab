"""Tests for deterministic evidence grounding evaluation."""

import pytest
from pydantic import ValidationError

from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)
from app.evals.evidence_grounding_evaluator import (
    EvidenceGroundingEvaluator,
)
from app.evals.evidence_grounding_evaluator_error import (
    EvidenceGroundingEvaluatorError,
)
from app.evals.evidence_grounding_snapshot import (
    EvidenceGroundingSnapshot,
    GroundingEvidenceArtifact,
    GroundingSourceArtifact,
)


def source(
    *,
    source_id: str = "source-001",
) -> GroundingSourceArtifact:
    """Return one source document."""

    return GroundingSourceArtifact(
        source_id=source_id,
        title="Grounding source",
        text=(
            "The study found that structured evaluation "
            "improves research reliability. "
            "Independent review reduces unsupported claims."
        ),
        locations={
            "section-1": (
                "The study found that structured evaluation "
                "improves research reliability."
            ),
            "section-2": (
                "Independent review reduces "
                "unsupported claims."
            ),
        },
    )


def evidence(
    *,
    evidence_id: str = "evidence-001",
    source_id: str = "source-001",
    text: str = (
        "Structured evaluation improves research reliability."
    ),
    location_reference: str | None = "section-1",
    required: bool = True,
) -> GroundingEvidenceArtifact:
    """Return one evidence artifact."""

    return GroundingEvidenceArtifact(
        evidence_id=evidence_id,
        source_id=source_id,
        text=text,
        location_reference=location_reference,
        required=required,
    )


def valid_snapshot() -> EvidenceGroundingSnapshot:
    """Return one fully grounded snapshot."""

    return EvidenceGroundingSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[source()],
        evidence=[evidence()],
    )


def evaluator(
    *,
    minimum_score: float = 1.0,
    require_valid_location: bool = True,
    detect_orphan_sources: bool = False,
) -> EvidenceGroundingEvaluator:
    """Return one deterministic grounding evaluator."""

    return EvidenceGroundingEvaluator(
        minimum_score=minimum_score,
        require_valid_location=require_valid_location,
        detect_orphan_sources=detect_orphan_sources,
        evaluation_id_factory=(
            lambda: "grounding-evaluation-001"
        ),
        finding_id_factory=(
            lambda index: f"finding-{index:03d}"
        ),
        violation_id_factory=(
            lambda index: f"violation-{index:03d}"
        ),
    )


def test_grounded_evidence_passes() -> None:
    value = evaluator().evaluate(valid_snapshot())

    assert value.passed is True
    assert value.score.dimension is (
        EvaluationDimension.EVIDENCE_GROUNDING
    )
    assert value.score.score == pytest.approx(1.0)
    assert value.evidence_count == 1
    assert value.grounded_evidence_count == 1
    assert value.partially_grounded_evidence_count == 0
    assert value.ungrounded_evidence_count == 0
    assert value.violations == []


def test_text_normalization_ignores_case_and_whitespace() -> None:
    snapshot = EvidenceGroundingSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[source()],
        evidence=[
            evidence(
                text=(
                    "STRUCTURED   EVALUATION improves "
                    "research reliability."
                )
            )
        ],
    )

    value = evaluator().evaluate(snapshot)

    assert value.passed is True
    assert value.grounded_evidence_count == 1


def test_unknown_source_fails() -> None:
    snapshot = EvidenceGroundingSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[source()],
        evidence=[
            evidence(source_id="source-missing")
        ],
    )

    value = evaluator().evaluate(snapshot)

    assert value.passed is False
    assert value.ungrounded_evidence_count == 1
    assert any(
        violation.code == "UNKNOWN_EVIDENCE_SOURCE"
        for violation in value.violations
    )
    assert value.violations[0].blocking is True


def test_ungrounded_text_fails() -> None:
    snapshot = EvidenceGroundingSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[source()],
        evidence=[
            evidence(
                text="A completely unsupported statement."
            )
        ],
    )

    value = evaluator().evaluate(snapshot)

    assert value.passed is False
    assert value.ungrounded_evidence_count == 1
    assert any(
        violation.code == "UNGROUNDED_EVIDENCE_TEXT"
        for violation in value.violations
    )


def test_invalid_location_is_partial() -> None:
    snapshot = EvidenceGroundingSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[source()],
        evidence=[
            evidence(
                location_reference="section-missing"
            )
        ],
    )

    value = evaluator(
        minimum_score=0.5
    ).evaluate(snapshot)

    assert value.passed is True
    assert value.score.score == pytest.approx(0.5)
    assert value.partially_grounded_evidence_count == 1
    assert any(
        violation.code == "INVALID_EVIDENCE_LOCATION"
        for violation in value.violations
    )


def test_location_validation_can_be_disabled() -> None:
    snapshot = EvidenceGroundingSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[source()],
        evidence=[
            evidence(
                location_reference="section-missing"
            )
        ],
    )

    value = evaluator(
        require_valid_location=False
    ).evaluate(snapshot)

    assert value.passed is True
    assert value.grounded_evidence_count == 1
    assert value.violations == []


def test_optional_ungrounded_evidence_is_nonblocking() -> None:
    snapshot = EvidenceGroundingSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[source()],
        evidence=[
            evidence(
                text="Unsupported optional evidence.",
                required=False,
            )
        ],
    )

    value = evaluator(
        minimum_score=0.0
    ).evaluate(snapshot)

    assert value.passed is True
    assert len(value.violations) == 1
    assert value.violations[0].blocking is False


def test_orphan_source_can_be_detected() -> None:
    snapshot = EvidenceGroundingSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[
            source(source_id="source-001"),
            source(source_id="source-002"),
        ],
        evidence=[evidence()],
    )

    value = evaluator(
        detect_orphan_sources=True
    ).evaluate(snapshot)

    assert value.orphan_source_count == 1
    assert any(
        violation.code == "ORPHAN_SOURCE"
        for violation in value.violations
    )
    assert next(
        violation
        for violation in value.violations
        if violation.code == "ORPHAN_SOURCE"
    ).blocking is False


def test_empty_evidence_set_scores_one() -> None:
    snapshot = EvidenceGroundingSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[source()],
        evidence=[],
    )

    value = evaluator().evaluate(snapshot)

    assert value.score.score == pytest.approx(1.0)
    assert value.passed is True
    assert value.evidence_count == 0


def test_snapshot_rejects_duplicate_evidence_ids() -> None:
    duplicate = evidence()

    with pytest.raises(
        ValidationError,
        match="evidence IDs must not contain duplicates",
    ):
        EvidenceGroundingSnapshot(
            execution_id="execution-001",
            request_id="research-001",
            workspace_id="workspace-001",
            sources=[source()],
            evidence=[
                duplicate,
                duplicate,
            ],
        )


def test_evaluator_rejects_invalid_minimum_score() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "minimum_score must be between 0 and 1"
        ),
    ):
        EvidenceGroundingEvaluator(
            minimum_score=-0.1
        )


def test_evaluator_rejects_blank_evaluation_id() -> None:
    value = EvidenceGroundingEvaluator(
        evaluation_id_factory=lambda: " ",
    )

    with pytest.raises(
        EvidenceGroundingEvaluatorError,
        match=(
            "evaluation_id factory returned blank value"
        ),
    ):
        value.evaluate(valid_snapshot())
