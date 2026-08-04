"""Deterministic evaluation of multi-agent workflow integrity."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)
from app.evals.evaluation_result import (
    EvaluationArtifactFinding,
    EvaluationArtifactType,
    EvaluationDimensionScore,
    EvaluationFindingStatus,
    EvaluationViolation,
    EvaluationViolationSeverity,
)
from app.evals.multi_agent_workflow_evaluator_error import (
    MultiAgentWorkflowEvaluatorError,
)
from app.research.multi_agent_research_orchestrator import (
    MultiAgentResearchStage,
    MultiAgentResearchStatus,
    MultiAgentResearchWorkflowResult,
)
from app.research.review_revision_loop import (
    ReviewRevisionLoopStatus,
)
from app.schemas.research_agent_result import (
    ResearchAgentResultStatus,
)


class MultiAgentWorkflowEvaluation(BaseModel):
    """Complete deterministic workflow-integrity evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evaluation_id: str
    request_id: str
    workspace_id: str
    score: EvaluationDimensionScore
    findings: list[EvaluationArtifactFinding] = Field(
        default_factory=list
    )
    violations: list[EvaluationViolation] = Field(
        default_factory=list
    )
    expected_stage_count: int = Field(ge=0)
    actual_stage_count: int = Field(ge=0)
    valid_stage_count: int = Field(ge=0)
    valid_transition_count: int = Field(ge=0)
    review_round_count: int = Field(ge=0)

    @property
    def passed(self) -> bool:
        """Return whether workflow integrity passed."""

        return self.score.passed


class MultiAgentWorkflowEvaluator:
    """Evaluate stage order, artifact flow, and termination rules."""

    _EXPECTED_STAGES = (
        MultiAgentResearchStage.SEARCH,
        MultiAgentResearchStage.SOURCE_READING,
        MultiAgentResearchStage.EVIDENCE_EXTRACTION,
        MultiAgentResearchStage.CLAIM_CONSTRUCTION,
    )

    def __init__(
        self,
        *,
        minimum_score: float = 1.0,
        evaluation_id_factory: Callable[[], str] | None = None,
        finding_id_factory: Callable[[int], str] | None = None,
        violation_id_factory: Callable[[int], str] | None = None,
        evaluator_name: str = (
            "deterministic-multi-agent-workflow-evaluator"
        ),
    ) -> None:
        if not 0 <= minimum_score <= 1:
            raise ValueError(
                "minimum_score must be between 0 and 1"
            )

        if not evaluator_name.strip():
            raise ValueError(
                "evaluator_name must not be blank"
            )

        self._minimum_score = minimum_score
        self._evaluation_id_factory = (
            evaluation_id_factory
            or (lambda: f"workflow-evaluation-{uuid4()}")
        )
        self._finding_id_factory = (
            finding_id_factory
            or (
                lambda index: (
                    f"workflow-finding-{index}-{uuid4()}"
                )
            )
        )
        self._violation_id_factory = (
            violation_id_factory
            or (
                lambda index: (
                    f"workflow-violation-{index}-{uuid4()}"
                )
            )
        )
        self._evaluator_name = evaluator_name

    def evaluate(
        self,
        workflow: MultiAgentResearchWorkflowResult,
    ) -> MultiAgentWorkflowEvaluation:
        """Evaluate one multi-agent workflow result."""

        findings: list[EvaluationArtifactFinding] = []
        violations: list[EvaluationViolation] = []
        successful_checks = 0
        total_checks = 0

        actual_stages = [
            stage.stage
            for stage in workflow.stages
        ]

        valid_stage_count = 0

        for index, stage_result in enumerate(workflow.stages):
            total_checks += 1
            expected_stage = self._EXPECTED_STAGES[index]

            valid = stage_result.stage is expected_stage

            findings.append(
                self._finding(
                    index=len(findings) + 1,
                    artifact_id=stage_result.stage.value,
                    valid=valid,
                    explanation=(
                        "Workflow stage appears in the expected order."
                        if valid
                        else "Workflow stage is out of order."
                    ),
                )
            )

            if valid:
                valid_stage_count += 1
                successful_checks += 1
            else:
                violations.append(
                    self._violation(
                        index=len(violations) + 1,
                        code="WORKFLOW_STAGE_ORDER_INVALID",
                        message=(
                            "Workflow stage order is invalid at "
                            f"position {index + 1}."
                        ),
                        artifact_id=stage_result.stage.value,
                    )
                )

        valid_transition_count = 0

        for previous, current in zip(
            workflow.stages,
            workflow.stages[1:],
            strict=False,
        ):
            total_checks += 1
            valid_parent = (
                current.assignment.parent_assignment_id
                == previous.assignment.assignment_id
            )

            if valid_parent:
                valid_transition_count += 1
                successful_checks += 1
            else:
                violations.append(
                    self._violation(
                        index=len(violations) + 1,
                        code="WORKFLOW_PARENT_LINK_INVALID",
                        message=(
                            "A stage assignment does not reference "
                            "the previous assignment as parent."
                        ),
                        artifact_id=(
                            current.assignment.assignment_id
                        ),
                    )
                )

        total_checks += 1

        termination_valid = self._termination_is_valid(
            workflow
        )

        if termination_valid:
            successful_checks += 1
        else:
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    code="WORKFLOW_TERMINATION_INVALID",
                    message=(
                        "Workflow status does not match "
                        "the actual stage or loop result."
                    ),
                    artifact_id=workflow.status.value,
                )
            )

        review_round_count = 0

        if workflow.review_revision_result is not None:
            loop_result = workflow.review_revision_result
            review_round_count = len(loop_result.rounds)

            for expected_round_number, loop_round in enumerate(
                loop_result.rounds,
                start=1,
            ):
                total_checks += 1
                valid_round = (
                    loop_round.round_number
                    == expected_round_number
                )

                if valid_round:
                    successful_checks += 1
                else:
                    violations.append(
                        self._violation(
                            index=len(violations) + 1,
                            code=(
                                "REVIEW_ROUND_SEQUENCE_INVALID"
                            ),
                            message=(
                                "Review round numbers must be "
                                "continuous and start at one."
                            ),
                            artifact_id=str(
                                loop_round.round_number
                            ),
                        )
                    )

                if loop_round.review_assignment is not None:
                    total_checks += 1
                    valid_review_parent = (
                        loop_round.review_assignment
                        .parent_assignment_id
                        == loop_round.synthesis_assignment
                        .assignment_id
                    )

                    if valid_review_parent:
                        successful_checks += 1
                    else:
                        violations.append(
                            self._violation(
                                index=len(violations) + 1,
                                code=(
                                    "REVIEW_PARENT_LINK_INVALID"
                                ),
                                message=(
                                    "Review assignment must reference "
                                    "its synthesis assignment."
                                ),
                                artifact_id=(
                                    loop_round.review_assignment
                                    .assignment_id
                                ),
                            )
                        )

        score_value = (
            successful_checks / total_checks
            if total_checks
            else 1.0
        )

        return MultiAgentWorkflowEvaluation(
            evaluation_id=self._new_identifier(
                self._evaluation_id_factory,
                field_name="evaluation_id",
            ),
            request_id=workflow.request_id,
            workspace_id=workflow.workspace_id,
            score=EvaluationDimensionScore(
                dimension=(
                    EvaluationDimension.LOGICAL_CONSISTENCY
                ),
                score=score_value,
                threshold=self._minimum_score,
                required=True,
                passed=score_value >= self._minimum_score,
                rationale=(
                    "Workflow score measures stage order, "
                    "parent links, review-round sequence, "
                    "and termination consistency."
                ),
                evaluator=self._evaluator_name,
            ),
            findings=findings,
            violations=violations,
            expected_stage_count=len(self._EXPECTED_STAGES),
            actual_stage_count=len(actual_stages),
            valid_stage_count=valid_stage_count,
            valid_transition_count=valid_transition_count,
            review_round_count=review_round_count,
        )

    @staticmethod
    def _termination_is_valid(
        workflow: MultiAgentResearchWorkflowResult,
    ) -> bool:
        """Return whether workflow status matches execution results."""

        failed_stages = [
            stage
            for stage in workflow.stages
            if stage.result.status
            is ResearchAgentResultStatus.FAILED
        ]

        early_failure_statuses = {
            MultiAgentResearchStatus.SEARCH_FAILED,
            MultiAgentResearchStatus.SOURCE_READING_FAILED,
            MultiAgentResearchStatus.EVIDENCE_FAILED,
            MultiAgentResearchStatus.CLAIM_FAILED,
        }

        if workflow.status in early_failure_statuses:
            return len(failed_stages) == 1

        if failed_stages:
            return False

        loop_result = workflow.review_revision_result

        if loop_result is None:
            return False

        mapping = {
            MultiAgentResearchStatus.COMPLETED: (
                ReviewRevisionLoopStatus.APPROVED
            ),
            MultiAgentResearchStatus.REPORT_REJECTED: (
                ReviewRevisionLoopStatus.REJECTED
            ),
            MultiAgentResearchStatus.REVISION_LIMIT_REACHED: (
                ReviewRevisionLoopStatus.REVISION_LIMIT_REACHED
            ),
            MultiAgentResearchStatus.SYNTHESIS_FAILED: (
                ReviewRevisionLoopStatus.SYNTHESIS_FAILED
            ),
            MultiAgentResearchStatus.REVIEW_FAILED: (
                ReviewRevisionLoopStatus.REVIEW_FAILED
            ),
        }

        expected_loop_status = mapping.get(workflow.status)

        return (
            expected_loop_status is not None
            and loop_result.status is expected_loop_status
        )

    def _finding(
        self,
        *,
        index: int,
        artifact_id: str,
        valid: bool,
        explanation: str,
    ) -> EvaluationArtifactFinding:
        """Build one workflow-stage finding."""

        return EvaluationArtifactFinding(
            finding_id=self._new_indexed_identifier(
                self._finding_id_factory,
                index=index,
                field_name="finding_id",
            ),
            artifact_type=EvaluationArtifactType.WORKFLOW,
            expected_artifact_id=artifact_id,
            actual_artifact_id=artifact_id if valid else None,
            status=(
                EvaluationFindingStatus.MATCHED
                if valid
                else EvaluationFindingStatus.MISSING
            ),
            score=1.0 if valid else 0.0,
            explanation=explanation,
        )

    def _violation(
        self,
        *,
        index: int,
        code: str,
        message: str,
        artifact_id: str,
    ) -> EvaluationViolation:
        """Build one blocking workflow violation."""

        return EvaluationViolation(
            violation_id=self._new_indexed_identifier(
                self._violation_id_factory,
                index=index,
                field_name="violation_id",
            ),
            code=code,
            severity=EvaluationViolationSeverity.ERROR,
            message=message,
            blocking=True,
            dimension=EvaluationDimension.LOGICAL_CONSISTENCY,
            artifact_type=EvaluationArtifactType.WORKFLOW,
            artifact_id=artifact_id,
            remediation=(
                "Repair workflow stage order, assignment links, "
                "or termination state."
            ),
        )

    @staticmethod
    def _new_identifier(
        factory: Callable[[], str],
        *,
        field_name: str,
    ) -> str:
        """Generate one nonblank identifier."""

        value = factory()

        if not value.strip():
            raise MultiAgentWorkflowEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value

    @staticmethod
    def _new_indexed_identifier(
        factory: Callable[[int], str],
        *,
        index: int,
        field_name: str,
    ) -> str:
        """Generate one nonblank indexed identifier."""

        value = factory(index)

        if not value.strip():
            raise MultiAgentWorkflowEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value
