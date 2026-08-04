"""Tests for deterministic citation correctness evaluation."""

import pytest
from pydantic import ValidationError

from app.evals.citation_correctness_evaluator import (
    CitationCorrectnessEvaluator,
)
from app.evals.citation_correctness_evaluator_error import (
    CitationCorrectnessEvaluatorError,
)
from app.evals.citation_evaluation_snapshot import (
    ActualCitationArtifact,
    CitationEvaluationSnapshot,
)
from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)


def valid_snapshot() -> CitationEvaluationSnapshot:
    """Return one fully connected citation snapshot."""

    return CitationEvaluationSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        source_ids=["source-001"],
        evidence_source_map={
            "evidence-001": "source-001",
        },
        claim_citation_map={
            "claim-001": ["citation-001"],
        },
        citations=[
            ActualCitationArtifact(
                citation_id="citation-001",
                claim_id="claim-001",
                evidence_id="evidence-001",
                source_id="source-001",
                locator="Section 2",
            )
        ],
    )


def evaluator(
    *,
    minimum_score: float = 1.0,
    require_citation_per_claim: bool = True,
) -> CitationCorrectnessEvaluator:
    """Return one deterministic citation evaluator."""

    return CitationCorrectnessEvaluator(
        minimum_score=minimum_score,
        require_citation_per_claim=(
            require_citation_per_claim
        ),
        evaluation_id_factory=(
            lambda: "citation-evaluation-001"
        ),
        finding_id_factory=(
            lambda index: f"finding-{index:03d}"
        ),
        violation_id_factory=(
            lambda index: f"violation-{index:03d}"
        ),
    )


def test_valid_citation_passes() -> None:
    value = evaluator().evaluate(valid_snapshot())

    assert value.passed is True
    assert value.score.score == pytest.approx(1.0)
    assert value.score.dimension is (
        EvaluationDimension.CITATION_CORRECTNESS
    )
    assert value.citation_count == 1
    assert value.valid_citation_count == 1
    assert value.invalid_citation_count == 0
    assert value.uncited_claim_count == 0
    assert value.orphan_citation_count == 0
    assert value.violations == []


def test_unknown_source_fails() -> None:
    values = valid_snapshot().model_dump(mode="python")
    values["citations"][0]["source_id"] = "source-missing"
    snapshot = CitationEvaluationSnapshot.model_validate(
        values
    )

    value = evaluator().evaluate(snapshot)

    assert value.passed is False
    assert value.invalid_citation_count == 1
    assert any(
        violation.code == "UNKNOWN_CITATION_SOURCE"
        for violation in value.violations
    )


def test_unknown_evidence_fails() -> None:
    values = valid_snapshot().model_dump(mode="python")
    values["citations"][0]["evidence_id"] = (
        "evidence-missing"
    )
    snapshot = CitationEvaluationSnapshot.model_validate(
        values
    )

    value = evaluator().evaluate(snapshot)

    assert any(
        violation.code == "UNKNOWN_CITATION_EVIDENCE"
        for violation in value.violations
    )


def test_source_mismatch_fails() -> None:
    snapshot = CitationEvaluationSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        source_ids=[
            "source-001",
            "source-002",
        ],
        evidence_source_map={
            "evidence-001": "source-001",
        },
        claim_citation_map={
            "claim-001": ["citation-001"],
        },
        citations=[
            ActualCitationArtifact(
                citation_id="citation-001",
                claim_id="claim-001",
                evidence_id="evidence-001",
                source_id="source-002",
            )
        ],
    )

    value = evaluator().evaluate(snapshot)

    assert any(
        violation.code == "CITATION_SOURCE_MISMATCH"
        for violation in value.violations
    )


def test_unknown_claim_fails() -> None:
    values = valid_snapshot().model_dump(mode="python")
    values["citations"][0]["claim_id"] = "claim-missing"
    snapshot = CitationEvaluationSnapshot.model_validate(
        values
    )

    value = evaluator().evaluate(snapshot)

    assert any(
        violation.code == "UNKNOWN_CITATION_CLAIM"
        for violation in value.violations
    )


def test_missing_claim_citation_link_fails() -> None:
    snapshot = CitationEvaluationSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        source_ids=["source-001"],
        evidence_source_map={
            "evidence-001": "source-001",
        },
        claim_citation_map={
            "claim-001": ["citation-other"],
        },
        citations=[
            ActualCitationArtifact(
                citation_id="citation-001",
                claim_id="claim-001",
                evidence_id="evidence-001",
                source_id="source-001",
            )
        ],
    )

    value = evaluator().evaluate(snapshot)

    assert any(
        violation.code == "CLAIM_CITATION_LINK_MISSING"
        for violation in value.violations
    )


def test_uncited_claim_fails() -> None:
    snapshot = CitationEvaluationSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        claim_citation_map={
            "claim-001": [],
        },
    )

    value = evaluator().evaluate(snapshot)

    assert value.uncited_claim_count == 1
    assert any(
        violation.code == "UNCITED_CLAIM"
        for violation in value.violations
    )


def test_uncited_claim_can_be_allowed() -> None:
    snapshot = CitationEvaluationSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        claim_citation_map={
            "claim-001": [],
        },
    )

    value = evaluator(
        require_citation_per_claim=False
    ).evaluate(snapshot)

    assert value.passed is True
    assert value.uncited_claim_count == 0


def test_orphan_citation_is_detected() -> None:
    snapshot = CitationEvaluationSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        source_ids=["source-001"],
        evidence_source_map={
            "evidence-001": "source-001",
        },
        claim_citation_map={
            "claim-001": [],
        },
        citations=[
            ActualCitationArtifact(
                citation_id="citation-001",
                claim_id="claim-001",
                evidence_id="evidence-001",
                source_id="source-001",
            )
        ],
    )

    value = evaluator().evaluate(snapshot)

    assert value.orphan_citation_count == 1
    assert any(
        violation.code == "ORPHAN_CITATION"
        for violation in value.violations
    )


def test_snapshot_rejects_duplicate_citation_ids() -> None:
    citation = ActualCitationArtifact(
        citation_id="citation-001",
        claim_id="claim-001",
        evidence_id="evidence-001",
        source_id="source-001",
    )

    with pytest.raises(
        ValidationError,
        match="citation IDs must not contain duplicates",
    ):
        CitationEvaluationSnapshot(
            execution_id="execution-001",
            request_id="research-001",
            workspace_id="workspace-001",
            citations=[
                citation,
                citation,
            ],
        )


def test_evaluator_rejects_invalid_minimum_score() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "minimum_score must be between 0 and 1"
        ),
    ):
        CitationCorrectnessEvaluator(
            minimum_score=1.1
        )


def test_evaluator_rejects_blank_evaluation_id() -> None:
    value = CitationCorrectnessEvaluator(
        evaluation_id_factory=lambda: " ",
    )

    with pytest.raises(
        CitationCorrectnessEvaluatorError,
        match=(
            "evaluation_id factory returned blank value"
        ),
    ):
        value.evaluate(valid_snapshot())
