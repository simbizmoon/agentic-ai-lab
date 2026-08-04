"""Deterministic evaluation runner for normalized research artifacts."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from app.evals.deterministic_evaluation_runner_error import (
    DeterministicEvaluationRunnerError,
)
from app.evals.evaluation_case_definition import (
    EvaluationCaseDefinition,
)
from app.evals.evaluation_execution_snapshot import (
    EvaluationExecutionSnapshot,
)
from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)
from app.evals.evaluation_result import (
    EvaluationArtifactFinding,
    EvaluationArtifactType,
    EvaluationCaseResult,
    EvaluationDimensionScore,
    EvaluationExecutionMetrics,
    EvaluationFindingStatus,
    EvaluationResultStatus,
    EvaluationViolation,
    EvaluationViolationSeverity,
)


class DeterministicEvaluationRunner:
    """Evaluate expected artifacts using exact deterministic rules."""

    def __init__(
        self,
        *,
        result_id_factory: Callable[[], str] | None = None,
        finding_id_factory: Callable[[int], str] | None = None,
        violation_id_factory: (
            Callable[[int], str] | None
        ) = None,
        evaluator_name: str = (
            "deterministic-evaluation-runner"
        ),
    ) -> None:
        if not evaluator_name.strip():
            raise ValueError(
                "evaluator_name must not be blank"
            )

        self._result_id_factory = (
            result_id_factory
            or (lambda: f"evaluation-result-{uuid4()}")
        )
        self._finding_id_factory = (
            finding_id_factory
            or (
                lambda index: (
                    f"evaluation-finding-{index}-{uuid4()}"
                )
            )
        )
        self._violation_id_factory = (
            violation_id_factory
            or (
                lambda index: (
                    f"evaluation-violation-{index}-{uuid4()}"
                )
            )
        )
        self._evaluator_name = evaluator_name

    def evaluate(
        self,
        *,
        run_id: str,
        dataset_id: str,
        dataset_version: str,
        case: EvaluationCaseDefinition,
        snapshot: EvaluationExecutionSnapshot,
    ) -> EvaluationCaseResult:
        """Evaluate one execution snapshot against one case."""

        self._validate_execution_context(
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            snapshot=snapshot,
        )

        expected = case.expected_outcome
        findings: list[EvaluationArtifactFinding] = []
        violations: list[EvaluationViolation] = []

        source_score = self._evaluate_sources(
            case=case,
            snapshot=snapshot,
            findings=findings,
            violations=violations,
        )
        evidence_score = self._evaluate_evidence(
            case=case,
            snapshot=snapshot,
            findings=findings,
            violations=violations,
        )
        claim_score = self._evaluate_claims(
            case=case,
            snapshot=snapshot,
            findings=findings,
            violations=violations,
        )
        report_score = self._evaluate_report(
            case=case,
            snapshot=snapshot,
            findings=findings,
            violations=violations,
        )

        dimension_scores = self._dimension_scores(
            source_score=source_score,
            evidence_score=evidence_score,
            claim_score=claim_score,
            report_score=report_score,
            case=case,
        )

        scored_dimensions = [
            score.score
            for score in dimension_scores
        ]
        overall_score = (
            sum(scored_dimensions) / len(scored_dimensions)
            if scored_dimensions
            else 1.0
        )

        blocking = any(
            violation.blocking
            for violation in violations
        )
        failed_required_dimension = any(
            score.required and not score.passed
            for score in dimension_scores
        )

        if blocking or failed_required_dimension:
            status = EvaluationResultStatus.FAILED
        elif overall_score >= expected.minimum_overall_score:
            status = EvaluationResultStatus.PASSED
        elif expected.allow_partial_result:
            status = EvaluationResultStatus.PARTIAL
        else:
            status = EvaluationResultStatus.FAILED

        return EvaluationCaseResult(
            result_id=self._new_identifier(
                self._result_id_factory,
                field_name="result_id",
            ),
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            case_id=case.case_id,
            request_id=snapshot.request_id,
            workspace_id=snapshot.workspace_id,
            execution_id=snapshot.execution_id,
            status=status,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            findings=findings,
            violations=violations,
            metrics=EvaluationExecutionMetrics(
                evaluator_call_count=1,
                tool_call_count=snapshot.tool_call_count,
                input_token_count=(
                    snapshot.input_token_count
                ),
                output_token_count=(
                    snapshot.output_token_count
                ),
                source_count=len(snapshot.sources),
                evidence_count=len(snapshot.evidence),
                claim_count=len(snapshot.claims),
                citation_count=sum(
                    len(claim.citation_ids)
                    for claim in snapshot.claims
                ),
                revision_round_count=(
                    snapshot.revision_round_count
                ),
            ),
            summary=self._summary(
                status=status,
                overall_score=overall_score,
                violation_count=len(violations),
            ),
            metadata={
                "evaluator": self._evaluator_name,
                "outcome_id": expected.outcome_id,
            },
        )

    def _evaluate_sources(
        self,
        *,
        case: EvaluationCaseDefinition,
        snapshot: EvaluationExecutionSnapshot,
        findings: list[EvaluationArtifactFinding],
        violations: list[EvaluationViolation],
    ) -> float | None:
        """Evaluate expected source IDs."""

        expected_sources = (
            case.expected_outcome.expected_sources
        )

        if not expected_sources:
            return None

        actual_ids = {
            source.source_id.strip().casefold()
            for source in snapshot.sources
        }
        matched = 0

        for expected_source in expected_sources:
            found = (
                expected_source.source_id
                .strip()
                .casefold()
                in actual_ids
            )

            findings.append(
                EvaluationArtifactFinding(
                    finding_id=self._new_indexed_identifier(
                        self._finding_id_factory,
                        index=len(findings) + 1,
                        field_name="finding_id",
                    ),
                    artifact_type=(
                        EvaluationArtifactType.SOURCE
                    ),
                    expected_artifact_id=(
                        expected_source.source_id
                    ),
                    actual_artifact_id=(
                        expected_source.source_id
                        if found
                        else None
                    ),
                    status=(
                        EvaluationFindingStatus.MATCHED
                        if found
                        else EvaluationFindingStatus.MISSING
                    ),
                    score=1.0 if found else 0.0,
                    explanation=(
                        "Expected source ID was found."
                        if found
                        else "Expected source ID was missing."
                    ),
                )
            )

            if found:
                matched += 1
            elif expected_source.required:
                violations.append(
                    self._missing_violation(
                        index=len(violations) + 1,
                        code="MISSING_REQUIRED_SOURCE",
                        message=(
                            "Required source is missing: "
                            f"{expected_source.source_id}"
                        ),
                        artifact_type=(
                            EvaluationArtifactType.SOURCE
                        ),
                        artifact_id=(
                            expected_source.source_id
                        ),
                        dimension=(
                            EvaluationDimension.SOURCE_QUALITY
                        ),
                    )
                )

        return matched / len(expected_sources)

    def _evaluate_evidence(
        self,
        *,
        case: EvaluationCaseDefinition,
        snapshot: EvaluationExecutionSnapshot,
        findings: list[EvaluationArtifactFinding],
        violations: list[EvaluationViolation],
    ) -> float | None:
        """Evaluate expected evidence IDs."""

        expected_evidence = (
            case.expected_outcome.expected_evidence
        )

        if not expected_evidence:
            return None

        actual_ids = {
            evidence.evidence_id.strip().casefold()
            for evidence in snapshot.evidence
        }
        matched = 0

        for expected_item in expected_evidence:
            found = (
                expected_item.evidence_id
                .strip()
                .casefold()
                in actual_ids
            )

            findings.append(
                EvaluationArtifactFinding(
                    finding_id=self._new_indexed_identifier(
                        self._finding_id_factory,
                        index=len(findings) + 1,
                        field_name="finding_id",
                    ),
                    artifact_type=(
                        EvaluationArtifactType.EVIDENCE
                    ),
                    expected_artifact_id=(
                        expected_item.evidence_id
                    ),
                    actual_artifact_id=(
                        expected_item.evidence_id
                        if found
                        else None
                    ),
                    status=(
                        EvaluationFindingStatus.MATCHED
                        if found
                        else EvaluationFindingStatus.MISSING
                    ),
                    score=1.0 if found else 0.0,
                    explanation=(
                        "Expected evidence ID was found."
                        if found
                        else "Expected evidence ID was missing."
                    ),
                )
            )

            if found:
                matched += 1
            elif expected_item.required:
                violations.append(
                    self._missing_violation(
                        index=len(violations) + 1,
                        code="MISSING_REQUIRED_EVIDENCE",
                        message=(
                            "Required evidence is missing: "
                            f"{expected_item.evidence_id}"
                        ),
                        artifact_type=(
                            EvaluationArtifactType.EVIDENCE
                        ),
                        artifact_id=(
                            expected_item.evidence_id
                        ),
                        dimension=(
                            EvaluationDimension
                            .EVIDENCE_GROUNDING
                        ),
                    )
                )

        return matched / len(expected_evidence)

    def _evaluate_claims(
        self,
        *,
        case: EvaluationCaseDefinition,
        snapshot: EvaluationExecutionSnapshot,
        findings: list[EvaluationArtifactFinding],
        violations: list[EvaluationViolation],
    ) -> float | None:
        """Evaluate expected claim IDs."""

        expected_claims = (
            case.expected_outcome.expected_claims
        )

        if not expected_claims:
            return None

        actual_ids = {
            claim.claim_id.strip().casefold()
            for claim in snapshot.claims
        }
        matched = 0

        for expected_claim in expected_claims:
            found = (
                expected_claim.claim_id
                .strip()
                .casefold()
                in actual_ids
            )

            findings.append(
                EvaluationArtifactFinding(
                    finding_id=self._new_indexed_identifier(
                        self._finding_id_factory,
                        index=len(findings) + 1,
                        field_name="finding_id",
                    ),
                    artifact_type=(
                        EvaluationArtifactType.CLAIM
                    ),
                    expected_artifact_id=(
                        expected_claim.claim_id
                    ),
                    actual_artifact_id=(
                        expected_claim.claim_id
                        if found
                        else None
                    ),
                    status=(
                        EvaluationFindingStatus.MATCHED
                        if found
                        else EvaluationFindingStatus.MISSING
                    ),
                    score=1.0 if found else 0.0,
                    explanation=(
                        "Expected claim ID was found."
                        if found
                        else "Expected claim ID was missing."
                    ),
                )
            )

            if found:
                matched += 1
            elif expected_claim.required:
                violations.append(
                    self._missing_violation(
                        index=len(violations) + 1,
                        code="MISSING_REQUIRED_CLAIM",
                        message=(
                            "Required claim is missing: "
                            f"{expected_claim.claim_id}"
                        ),
                        artifact_type=(
                            EvaluationArtifactType.CLAIM
                        ),
                        artifact_id=expected_claim.claim_id,
                        dimension=(
                            EvaluationDimension.CLAIM_SUPPORT
                        ),
                    )
                )

        return matched / len(expected_claims)

    def _evaluate_report(
        self,
        *,
        case: EvaluationCaseDefinition,
        snapshot: EvaluationExecutionSnapshot,
        findings: list[EvaluationArtifactFinding],
        violations: list[EvaluationViolation],
    ) -> float | None:
        """Evaluate deterministic report text requirements."""

        expected = case.expected_outcome
        required = expected.required_report_elements
        forbidden = expected.forbidden_report_elements

        if not required and not forbidden:
            return None

        normalized_report = (
            snapshot.report_text.strip().casefold()
        )
        matched_requirements = 0

        for element in required:
            found = element.strip().casefold() in normalized_report

            findings.append(
                EvaluationArtifactFinding(
                    finding_id=self._new_indexed_identifier(
                        self._finding_id_factory,
                        index=len(findings) + 1,
                        field_name="finding_id",
                    ),
                    artifact_type=(
                        EvaluationArtifactType.REPORT_ELEMENT
                    ),
                    expected_artifact_id=element,
                    actual_artifact_id=element if found else None,
                    status=(
                        EvaluationFindingStatus.MATCHED
                        if found
                        else EvaluationFindingStatus.MISSING
                    ),
                    score=1.0 if found else 0.0,
                    explanation=(
                        "Required report element was found."
                        if found
                        else "Required report element was missing."
                    ),
                )
            )

            if found:
                matched_requirements += 1
            else:
                violations.append(
                    self._missing_violation(
                        index=len(violations) + 1,
                        code="MISSING_REQUIRED_REPORT_ELEMENT",
                        message=(
                            "Required report element is missing: "
                            f"{element}"
                        ),
                        artifact_type=(
                            EvaluationArtifactType.REPORT_ELEMENT
                        ),
                        artifact_id=element,
                        dimension=(
                            EvaluationDimension.COMPLETENESS
                        ),
                    )
                )

        forbidden_found = 0

        for element in forbidden:
            found = element.strip().casefold() in normalized_report

            if not found:
                continue

            forbidden_found += 1
            findings.append(
                EvaluationArtifactFinding(
                    finding_id=self._new_indexed_identifier(
                        self._finding_id_factory,
                        index=len(findings) + 1,
                        field_name="finding_id",
                    ),
                    artifact_type=(
                        EvaluationArtifactType.REPORT_ELEMENT
                    ),
                    actual_artifact_id=element,
                    status=(
                        EvaluationFindingStatus.UNEXPECTED
                    ),
                    score=0.0,
                    explanation=(
                        "Forbidden report element was found."
                    ),
                )
            )
            violations.append(
                EvaluationViolation(
                    violation_id=(
                        self._new_indexed_identifier(
                            self._violation_id_factory,
                            index=len(violations) + 1,
                            field_name="violation_id",
                        )
                    ),
                    code="FORBIDDEN_REPORT_ELEMENT",
                    severity=(
                        EvaluationViolationSeverity.ERROR
                    ),
                    message=(
                        "Forbidden report element was found: "
                        f"{element}"
                    ),
                    blocking=True,
                    dimension=(
                        EvaluationDimension.CORRECTNESS
                    ),
                    artifact_type=(
                        EvaluationArtifactType.REPORT_ELEMENT
                    ),
                    artifact_id=element,
                    remediation=(
                        "Remove the forbidden report content."
                    ),
                )
            )

        total_checks = len(required) + len(forbidden)

        if total_checks == 0:
            return None

        successful_checks = (
            matched_requirements
            + len(forbidden)
            - forbidden_found
        )

        return successful_checks / total_checks

    def _dimension_scores(
        self,
        *,
        source_score: float | None,
        evidence_score: float | None,
        claim_score: float | None,
        report_score: float | None,
        case: EvaluationCaseDefinition,
    ) -> list[EvaluationDimensionScore]:
        """Build deterministic dimension scores."""

        thresholds = {
            threshold.dimension: threshold
            for threshold in (
                case.expected_outcome.score_thresholds
            )
        }
        expected = case.expected_outcome
        values = [
            (
                EvaluationDimension.SOURCE_QUALITY,
                source_score,
                any(
                    source.required
                    for source in expected.expected_sources
                ),
            ),
            (
                EvaluationDimension.EVIDENCE_GROUNDING,
                evidence_score,
                any(
                    evidence.required
                    for evidence in expected.expected_evidence
                ),
            ),
            (
                EvaluationDimension.CLAIM_SUPPORT,
                claim_score,
                any(
                    claim.required
                    for claim in expected.expected_claims
                ),
            ),
            (
                EvaluationDimension.COMPLETENESS,
                report_score,
                bool(
                    expected.required_report_elements
                    or expected.forbidden_report_elements
                ),
            ),
        ]
        scores: list[EvaluationDimensionScore] = []

        for dimension, value, default_required in values:
            if value is None:
                continue

            threshold_config = thresholds.get(dimension)
            threshold = (
                threshold_config.minimum_score
                if threshold_config is not None
                else case.expected_outcome.minimum_overall_score
            )
            required = (
                threshold_config.required
                if threshold_config is not None
                else default_required
            )

            scores.append(
                EvaluationDimensionScore(
                    dimension=dimension,
                    score=value,
                    threshold=threshold,
                    required=required,
                    passed=value >= threshold,
                    rationale=(
                        "Deterministic exact-match score "
                        "for expected artifacts."
                    ),
                    evaluator=self._evaluator_name,
                )
            )

        return scores

    def _missing_violation(
        self,
        *,
        index: int,
        code: str,
        message: str,
        artifact_type: EvaluationArtifactType,
        artifact_id: str,
        dimension: EvaluationDimension,
    ) -> EvaluationViolation:
        """Build one blocking missing-artifact violation."""

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
            dimension=dimension,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            remediation=(
                "Produce the required evaluation artifact."
            ),
        )

    @staticmethod
    def _validate_execution_context(
        *,
        run_id: str,
        dataset_id: str,
        dataset_version: str,
        snapshot: EvaluationExecutionSnapshot,
    ) -> None:
        """Validate required evaluation execution identifiers."""

        values = {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "request_id": snapshot.request_id,
            "workspace_id": snapshot.workspace_id,
            "execution_id": snapshot.execution_id,
        }

        for field_name, value in values.items():
            if not value.strip():
                raise DeterministicEvaluationRunnerError(
                    f"{field_name} must not be blank"
                )

    @staticmethod
    def _summary(
        *,
        status: EvaluationResultStatus,
        overall_score: float,
        violation_count: int,
    ) -> str:
        """Return deterministic evaluation summary."""

        return (
            "Deterministic evaluation completed with "
            f"status {status.value}, overall score "
            f"{overall_score:.4f}, and "
            f"{violation_count} violations."
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
            raise DeterministicEvaluationRunnerError(
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
            raise DeterministicEvaluationRunnerError(
                f"{field_name} factory returned blank value"
            )

        return value
