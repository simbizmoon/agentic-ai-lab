"""Tests for deterministic claim support evaluation."""

import pytest
from pydantic import ValidationError

from app.evals.claim_support_evaluator import (
    ClaimSupportEvaluator,
)
from app.evals.claim_support_evaluator_error import (
    ClaimSupportEvaluatorError,
)
from app.evals.claim_support_snapshot import (
    ClaimSupportClaimArtifact,
    ClaimSupportEvidenceArtifact,
    ClaimSupportSnapshot,
    EvidenceGroundingStatus,
)
from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)
from app.evals.evaluation_result import (
    EvaluationFindingStatus,
)


def evidence(
    *,
    evidence_id: str,
    source_id: str,
    grounding_status: EvidenceGroundingStatus = (
        EvidenceGroundingStatus.GROUNDED
    ),
) -> ClaimSupportEvidenceArtifact:
    """Return one claim-support evidence item."""

    return ClaimSupportEvidenceArtifact(
        evidence_id=evidence_id,
        source_id=source_id,
        grounding_status=grounding_status,
    )


def claim(
    *,
    supporting_evidence_ids: list[str] | None = None,
    required_evidence_ids: list[str] | None = None,
    minimum_support_count: int = 1,
    minimum_source_count: int = 1,
    required: bool = True,
) -> ClaimSupportClaimArtifact:
    """Return one claim with support requirements."""

    return ClaimSupportClaimArtifact(
        claim_id="claim-001",
        text="Structured evaluation improves reliability.",
        supporting_evidence_ids=(
            supporting_evidence_ids
            if supporting_evidence_ids is not None
            else ["evidence-001"]
        ),
        required_evidence_ids=(
            required_evidence_ids
            if required_evidence_ids is not None
            else []
        ),
        minimum_support_count=minimum_support_count,
        minimum_source_count=minimum_source_count,
        required=required,
    )


def valid_snapshot() -> ClaimSupportSnapshot:
    """Return one fully supported claim snapshot."""

    return ClaimSupportSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        evidence=[
            evidence(
                evidence_id="evidence-001",
                source_id="source-001",
            )
        ],
        claims=[claim()],
    )


def evaluator(
    *,
    minimum_score: float = 1.0,
    allow_partial_grounding: bool = False,
) -> ClaimSupportEvaluator:
    """Return one deterministic evaluator."""

    return ClaimSupportEvaluator(
        minimum_score=minimum_score,
        allow_partial_grounding=(
            allow_partial_grounding
        ),
        evaluation_id_factory=(
            lambda: "claim-support-evaluation-001"
        ),
        finding_id_factory=(
            lambda index: f"finding-{index:03d}"
        ),
        violation_id_factory=(
            lambda index: f"violation-{index:03d}"
        ),
    )


def test_supported_claim_passes() -> None:
    value = evaluator().evaluate(valid_snapshot())

    assert value.passed is True
    assert value.score.dimension is (
        EvaluationDimension.CLAIM_SUPPORT
    )
    assert value.score.score == pytest.approx(1.0)
    assert value.claim_count == 1
    assert value.supported_claim_count == 1
    assert value.partially_supported_claim_count == 0
    assert value.unsupported_claim_count == 0
    assert value.violations == []


def test_unknown_evidence_fails() -> None:
    snapshot = ClaimSupportSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        claims=[
            claim(
                supporting_evidence_ids=[
                    "evidence-missing"
                ]
            )
        ],
    )

    value = evaluator().evaluate(snapshot)

    assert value.passed is False
    assert value.unsupported_claim_count == 1
    assert any(
        violation.code
        == "UNKNOWN_SUPPORTING_EVIDENCE"
        for violation in value.violations
    )


def test_missing_required_evidence_fails() -> None:
    snapshot = ClaimSupportSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        evidence=[
            evidence(
                evidence_id="evidence-001",
                source_id="source-001",
            ),
            evidence(
                evidence_id="evidence-002",
                source_id="source-002",
            ),
        ],
        claims=[
            claim(
                supporting_evidence_ids=[
                    "evidence-001",
                    "evidence-002",
                ],
                required_evidence_ids=[
                    "evidence-002",
                ],
            )
        ],
    )
    values = snapshot.model_dump(mode="python")
    values["evidence"] = [values["evidence"][0]]
    snapshot = ClaimSupportSnapshot.model_validate(values)

    value = evaluator().evaluate(snapshot)

    assert any(
        violation.code
        == "UNKNOWN_SUPPORTING_EVIDENCE"
        for violation in value.violations
    )
    assert any(
        violation.code
        == "MISSING_REQUIRED_CLAIM_EVIDENCE"
        for violation in value.violations
    )


def test_insufficient_support_count_fails() -> None:
    snapshot = ClaimSupportSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        evidence=[
            evidence(
                evidence_id="evidence-001",
                source_id="source-001",
            )
        ],
        claims=[
            claim(
                minimum_support_count=2,
            )
        ],
    )

    value = evaluator(
        minimum_score=0.5
    ).evaluate(snapshot)

    assert value.score.score == pytest.approx(0.75)
    assert value.partially_supported_claim_count == 1
    assert any(
        violation.code
        == "INSUFFICIENT_CLAIM_SUPPORT"
        for violation in value.violations
    )


def test_insufficient_source_diversity_fails() -> None:
    snapshot = ClaimSupportSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        evidence=[
            evidence(
                evidence_id="evidence-001",
                source_id="source-001",
            ),
            evidence(
                evidence_id="evidence-002",
                source_id="source-001",
            ),
        ],
        claims=[
            claim(
                supporting_evidence_ids=[
                    "evidence-001",
                    "evidence-002",
                ],
                minimum_support_count=2,
                minimum_source_count=2,
            )
        ],
    )

    value = evaluator(
        minimum_score=0.7
    ).evaluate(snapshot)

    assert value.score.score == pytest.approx(0.75)
    assert value.partially_supported_claim_count == 1
    assert any(
        violation.code
        == "INSUFFICIENT_SOURCE_DIVERSITY"
        for violation in value.violations
    )


def test_ungrounded_evidence_fails() -> None:
    snapshot = ClaimSupportSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        evidence=[
            evidence(
                evidence_id="evidence-001",
                source_id="source-001",
                grounding_status=(
                    EvidenceGroundingStatus.UNGROUNDED
                ),
            )
        ],
        claims=[claim()],
    )

    value = evaluator().evaluate(snapshot)

    assert value.unsupported_claim_count == 1
    assert any(
        violation.code
        == "UNGROUNDED_CLAIM_EVIDENCE"
        for violation in value.violations
    )


def test_partial_grounding_can_be_allowed() -> None:
    snapshot = ClaimSupportSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        evidence=[
            evidence(
                evidence_id="evidence-001",
                source_id="source-001",
                grounding_status=(
                    EvidenceGroundingStatus.PARTIAL
                ),
            )
        ],
        claims=[claim()],
    )

    denied = evaluator().evaluate(snapshot)
    allowed = evaluator(
        allow_partial_grounding=True
    ).evaluate(snapshot)

    assert denied.passed is False
    assert allowed.passed is True


def test_optional_claim_violation_is_nonblocking() -> None:
    snapshot = ClaimSupportSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        claims=[
            claim(
                supporting_evidence_ids=[],
                required=False,
            )
        ],
    )

    value = evaluator(
        minimum_score=0.0
    ).evaluate(snapshot)

    assert value.passed is True
    assert value.violations
    assert all(
        violation.blocking is False
        for violation in value.violations
    )


def test_empty_claim_set_scores_one() -> None:
    snapshot = ClaimSupportSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
    )

    value = evaluator().evaluate(snapshot)

    assert value.score.score == pytest.approx(1.0)
    assert value.passed is True
    assert value.claim_count == 0


def test_required_evidence_must_be_supporting_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "required_evidence_ids must be included "
            "in supporting_evidence_ids"
        ),
    ):
        claim(
            supporting_evidence_ids=["evidence-001"],
            required_evidence_ids=["evidence-002"],
        )


def test_snapshot_rejects_duplicate_claim_ids() -> None:
    duplicate = claim()

    with pytest.raises(
        ValidationError,
        match="claim IDs must not contain duplicates",
    ):
        ClaimSupportSnapshot(
            execution_id="execution-001",
            request_id="research-001",
            workspace_id="workspace-001",
            claims=[
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
        ClaimSupportEvaluator(
            minimum_score=1.1
        )


def test_evaluator_rejects_blank_evaluation_id() -> None:
    value = ClaimSupportEvaluator(
        evaluation_id_factory=lambda: " ",
    )

    with pytest.raises(
        ClaimSupportEvaluatorError,
        match=(
            "evaluation_id factory returned blank value"
        ),
    ):
        value.evaluate(valid_snapshot())


def test_supported_finding_is_matched() -> None:
    value = evaluator().evaluate(valid_snapshot())

    assert value.findings[0].status is (
        EvaluationFindingStatus.MATCHED
    )
