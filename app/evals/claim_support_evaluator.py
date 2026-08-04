"""Deterministic claim support evaluation."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

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
    EvaluationArtifactFinding,
    EvaluationArtifactType,
    EvaluationDimensionScore,
    EvaluationFindingStatus,
    EvaluationViolation,
    EvaluationViolationSeverity,
)


class ClaimSupportFindingResult(BaseModel):
    """Internal normalized result for one claim."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    score: float = Field(ge=0, le=1)
    status: EvaluationFindingStatus
    errors: list[tuple[str, str]] = Field(
        default_factory=list
    )


class ClaimSupportEvaluation(BaseModel):
    """Complete deterministic claim support result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evaluation_id: str
    execution_id: str
    score: EvaluationDimensionScore
    findings: list[EvaluationArtifactFinding] = Field(
        default_factory=list
    )
    violations: list[EvaluationViolation] = Field(
        default_factory=list
    )
    claim_count: int = Field(ge=0)
    supported_claim_count: int = Field(ge=0)
    partially_supported_claim_count: int = Field(ge=0)
    unsupported_claim_count: int = Field(ge=0)

    @property
    def passed(self) -> bool:
        """Return whether claim support passed."""

        return self.score.passed


class ClaimSupportEvaluator:
    """Evaluate claim-to-evidence support deterministically."""

    def __init__(
        self,
        *,
        minimum_score: float = 1.0,
        allow_partial_grounding: bool = False,
        evaluation_id_factory: Callable[[], str] | None = None,
        finding_id_factory: Callable[[int], str] | None = None,
        violation_id_factory: (
            Callable[[int], str] | None
        ) = None,
        evaluator_name: str = (
            "deterministic-claim-support-evaluator"
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
        self._allow_partial_grounding = (
            allow_partial_grounding
        )
        self._evaluation_id_factory = (
            evaluation_id_factory
            or (lambda: f"claim-support-{uuid4()}")
        )
        self._finding_id_factory = (
            finding_id_factory
            or (
                lambda index: (
                    f"claim-support-finding-{index}-{uuid4()}"
                )
            )
        )
        self._violation_id_factory = (
            violation_id_factory
            or (
                lambda index: (
                    f"claim-support-violation-{index}-{uuid4()}"
                )
            )
        )
        self._evaluator_name = evaluator_name

    def evaluate(
        self,
        snapshot: ClaimSupportSnapshot,
    ) -> ClaimSupportEvaluation:
        """Evaluate one claim support snapshot."""

        evidence_by_id = {
            evidence.evidence_id.strip().casefold(): evidence
            for evidence in snapshot.evidence
        }
        findings: list[EvaluationArtifactFinding] = []
        violations: list[EvaluationViolation] = []

        supported_count = 0
        partial_count = 0
        unsupported_count = 0
        accumulated_score = 0.0

        for claim in snapshot.claims:
            claim_result = self._evaluate_claim(
                claim=claim,
                evidence_by_id=evidence_by_id,
            )
            score_value = claim_result.score
            status = claim_result.status
            errors = claim_result.errors

            accumulated_score += score_value

            if status is EvaluationFindingStatus.MATCHED:
                supported_count += 1
            elif (
                status
                is EvaluationFindingStatus.PARTIAL_MATCH
            ):
                partial_count += 1
            else:
                unsupported_count += 1

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
                    expected_artifact_id=claim.claim_id,
                    actual_artifact_id=(
                        claim.claim_id
                        if status
                        in {
                            EvaluationFindingStatus.MATCHED,
                            EvaluationFindingStatus.PARTIAL_MATCH,
                        }
                        else None
                    ),
                    status=status,
                    score=score_value,
                    explanation=(
                        "Claim has sufficient grounded support."
                        if not errors
                        else "; ".join(
                            message
                            for _, message in errors
                        )
                    ),
                )
            )

            for code, message in errors:
                violations.append(
                    self._violation(
                        index=len(violations) + 1,
                        code=code,
                        message=message,
                        claim=claim,
                    )
                )

        claim_count = len(snapshot.claims)
        overall_score = (
            accumulated_score / claim_count
            if claim_count
            else 1.0
        )

        return ClaimSupportEvaluation(
            evaluation_id=self._new_identifier(
                self._evaluation_id_factory,
                field_name="evaluation_id",
            ),
            execution_id=snapshot.execution_id,
            score=EvaluationDimensionScore(
                dimension=EvaluationDimension.CLAIM_SUPPORT,
                score=overall_score,
                threshold=self._minimum_score,
                required=True,
                passed=overall_score >= self._minimum_score,
                rationale=(
                    "Claim support score measures evidence "
                    "existence, grounding, required support, "
                    "support count, and source diversity."
                ),
                evaluator=self._evaluator_name,
            ),
            findings=findings,
            violations=violations,
            claim_count=claim_count,
            supported_claim_count=supported_count,
            partially_supported_claim_count=partial_count,
            unsupported_claim_count=unsupported_count,
        )

    def _evaluate_claim(
        self,
        *,
        claim: ClaimSupportClaimArtifact,
        evidence_by_id: dict[
            str,
            ClaimSupportEvidenceArtifact,
        ],
    ) -> ClaimSupportFindingResult:
        """Evaluate one claim and return normalized findings."""

        errors: list[tuple[str, str]] = []
        resolved_evidence: list[
            ClaimSupportEvidenceArtifact
        ] = []

        for evidence_id in claim.supporting_evidence_ids:
            evidence = evidence_by_id.get(
                evidence_id.strip().casefold()
            )

            if evidence is None:
                errors.append(
                    (
                        "UNKNOWN_SUPPORTING_EVIDENCE",
                        (
                            "Claim references unknown evidence: "
                            f"{evidence_id}"
                        ),
                    )
                )
                continue

            resolved_evidence.append(evidence)

        resolved_ids = {
            evidence.evidence_id.strip().casefold()
            for evidence in resolved_evidence
        }

        for required_evidence_id in (
            claim.required_evidence_ids
        ):
            if (
                required_evidence_id.strip().casefold()
                not in resolved_ids
            ):
                errors.append(
                    (
                        "MISSING_REQUIRED_CLAIM_EVIDENCE",
                        (
                            "Claim is missing required evidence: "
                            f"{required_evidence_id}"
                        ),
                    )
                )

        acceptable_evidence = [
            evidence
            for evidence in resolved_evidence
            if self._evidence_is_acceptable(evidence)
        ]

        if (
            len(acceptable_evidence)
            < claim.minimum_support_count
        ):
            errors.append(
                (
                    "INSUFFICIENT_CLAIM_SUPPORT",
                    (
                        "Claim has fewer acceptable evidence "
                        "items than minimum_support_count."
                    ),
                )
            )

        distinct_sources = {
            evidence.source_id.strip().casefold()
            for evidence in acceptable_evidence
        }

        if len(distinct_sources) < claim.minimum_source_count:
            errors.append(
                (
                    "INSUFFICIENT_SOURCE_DIVERSITY",
                    (
                        "Claim has fewer distinct sources "
                        "than minimum_source_count."
                    ),
                )
            )

        ungrounded_evidence = [
            evidence
            for evidence in resolved_evidence
            if evidence.grounding_status
            is EvidenceGroundingStatus.UNGROUNDED
        ]

        if ungrounded_evidence:
            errors.append(
                (
                    "UNGROUNDED_CLAIM_EVIDENCE",
                    (
                        "Claim references one or more "
                        "ungrounded evidence items."
                    ),
                )
            )

        if not errors:
            return ClaimSupportFindingResult(
                score=1.0,
                status=EvaluationFindingStatus.MATCHED,
                errors=errors,
            )

        support_ratio = min(
            len(acceptable_evidence)
            / claim.minimum_support_count,
            1.0,
        )
        source_ratio = min(
            len(distinct_sources)
            / claim.minimum_source_count,
            1.0,
        )
        score = (support_ratio + source_ratio) / 2

        if (
            score > 0
            and not any(
                code
                in {
                    "UNKNOWN_SUPPORTING_EVIDENCE",
                    "MISSING_REQUIRED_CLAIM_EVIDENCE",
                    "UNGROUNDED_CLAIM_EVIDENCE",
                }
                for code, _ in errors
            )
        ):
            status = EvaluationFindingStatus.PARTIAL_MATCH
        else:
            status = EvaluationFindingStatus.MISSING

        return ClaimSupportFindingResult(
            score=score,
            status=status,
            errors=errors,
        )

    def _evidence_is_acceptable(
        self,
        evidence: ClaimSupportEvidenceArtifact,
    ) -> bool:
        """Return whether evidence can support a claim."""

        if (
            evidence.grounding_status
            is EvidenceGroundingStatus.GROUNDED
        ):
            return True

        return (
            self._allow_partial_grounding
            and evidence.grounding_status
            is EvidenceGroundingStatus.PARTIAL
        )

    def _violation(
        self,
        *,
        index: int,
        code: str,
        message: str,
        claim: ClaimSupportClaimArtifact,
    ) -> EvaluationViolation:
        """Build one claim support violation."""

        return EvaluationViolation(
            violation_id=self._new_indexed_identifier(
                self._violation_id_factory,
                index=index,
                field_name="violation_id",
            ),
            code=code,
            severity=(
                EvaluationViolationSeverity.ERROR
                if claim.required
                else EvaluationViolationSeverity.WARNING
            ),
            message=message,
            blocking=claim.required,
            dimension=EvaluationDimension.CLAIM_SUPPORT,
            artifact_type=EvaluationArtifactType.CLAIM,
            artifact_id=claim.claim_id,
            remediation=(
                "Add sufficient grounded evidence from "
                "the required number of sources."
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
            raise ClaimSupportEvaluatorError(
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
            raise ClaimSupportEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value
