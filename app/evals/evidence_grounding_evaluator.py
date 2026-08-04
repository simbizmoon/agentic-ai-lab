"""Deterministic evidence grounding evaluation."""

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
from app.evals.evidence_grounding_evaluator_error import (
    EvidenceGroundingEvaluatorError,
)
from app.evals.evidence_grounding_snapshot import (
    EvidenceGroundingSnapshot,
    GroundingEvidenceArtifact,
    GroundingSourceArtifact,
)


class EvidenceGroundingEvaluation(BaseModel):
    """Complete deterministic evidence grounding result."""

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
    evidence_count: int = Field(ge=0)
    grounded_evidence_count: int = Field(ge=0)
    partially_grounded_evidence_count: int = Field(ge=0)
    ungrounded_evidence_count: int = Field(ge=0)
    orphan_source_count: int = Field(ge=0)

    @property
    def passed(self) -> bool:
        """Return whether evidence grounding passed."""

        return self.score.passed


class EvidenceGroundingEvaluator:
    """Evaluate whether evidence is grounded in source text."""

    def __init__(
        self,
        *,
        minimum_score: float = 1.0,
        require_valid_location: bool = True,
        detect_orphan_sources: bool = False,
        evaluation_id_factory: Callable[[], str] | None = None,
        finding_id_factory: Callable[[int], str] | None = None,
        violation_id_factory: (
            Callable[[int], str] | None
        ) = None,
        evaluator_name: str = (
            "deterministic-evidence-grounding-evaluator"
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
        self._require_valid_location = (
            require_valid_location
        )
        self._detect_orphan_sources = detect_orphan_sources
        self._evaluation_id_factory = (
            evaluation_id_factory
            or (lambda: f"grounding-evaluation-{uuid4()}")
        )
        self._finding_id_factory = (
            finding_id_factory
            or (
                lambda index: (
                    f"grounding-finding-{index}-{uuid4()}"
                )
            )
        )
        self._violation_id_factory = (
            violation_id_factory
            or (
                lambda index: (
                    f"grounding-violation-{index}-{uuid4()}"
                )
            )
        )
        self._evaluator_name = evaluator_name

    def evaluate(
        self,
        snapshot: EvidenceGroundingSnapshot,
    ) -> EvidenceGroundingEvaluation:
        """Evaluate one evidence grounding snapshot."""

        sources = {
            source.source_id.strip().casefold(): source
            for source in snapshot.sources
        }
        findings: list[EvaluationArtifactFinding] = []
        violations: list[EvaluationViolation] = []

        grounded_count = 0
        partial_count = 0
        ungrounded_count = 0

        for evidence in snapshot.evidence:
            source = sources.get(
                evidence.source_id.strip().casefold()
            )

            if source is None:
                ungrounded_count += 1
                findings.append(
                    self._finding(
                        index=len(findings) + 1,
                        evidence=evidence,
                        status=EvaluationFindingStatus.MISSING,
                        score=0.0,
                        explanation=(
                            "Evidence references an unknown source."
                        ),
                    )
                )
                violations.append(
                    self._violation(
                        index=len(violations) + 1,
                        code="UNKNOWN_EVIDENCE_SOURCE",
                        message=(
                            "Evidence references an unknown source: "
                            f"{evidence.source_id}"
                        ),
                        evidence_id=evidence.evidence_id,
                        blocking=evidence.required,
                    )
                )
                continue

            text_grounded = self._text_is_grounded(
                evidence=evidence,
                source=source,
            )
            location_valid = self._location_is_valid(
                evidence=evidence,
                source=source,
            )

            if text_grounded and location_valid:
                grounded_count += 1
                findings.append(
                    self._finding(
                        index=len(findings) + 1,
                        evidence=evidence,
                        status=EvaluationFindingStatus.MATCHED,
                        score=1.0,
                        explanation=(
                            "Evidence text and location are "
                            "grounded in the source."
                        ),
                    )
                )
                continue

            if text_grounded:
                partial_count += 1
                findings.append(
                    self._finding(
                        index=len(findings) + 1,
                        evidence=evidence,
                        status=(
                            EvaluationFindingStatus.PARTIAL_MATCH
                        ),
                        score=0.5,
                        explanation=(
                            "Evidence text is grounded, but "
                            "the location reference is invalid."
                        ),
                    )
                )
                violations.append(
                    self._violation(
                        index=len(violations) + 1,
                        code="INVALID_EVIDENCE_LOCATION",
                        message=(
                            "Evidence location is not present "
                            f"in source: {evidence.evidence_id}"
                        ),
                        evidence_id=evidence.evidence_id,
                        blocking=(
                            evidence.required
                            and self._require_valid_location
                        ),
                    )
                )
                continue

            ungrounded_count += 1
            findings.append(
                self._finding(
                    index=len(findings) + 1,
                    evidence=evidence,
                    status=EvaluationFindingStatus.MISSING,
                    score=0.0,
                    explanation=(
                        "Evidence text was not found "
                        "in the referenced source."
                    ),
                )
            )
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    code="UNGROUNDED_EVIDENCE_TEXT",
                    message=(
                        "Evidence text is not grounded "
                        f"in source: {evidence.evidence_id}"
                    ),
                    evidence_id=evidence.evidence_id,
                    blocking=evidence.required,
                )
            )

        referenced_source_ids = {
            evidence.source_id.strip().casefold()
            for evidence in snapshot.evidence
        }
        orphan_source_ids = (
            set(sources) - referenced_source_ids
        )
        orphan_source_count = len(orphan_source_ids)

        if self._detect_orphan_sources:
            for source_id in sorted(orphan_source_ids):
                violations.append(
                    EvaluationViolation(
                        violation_id=(
                            self._new_indexed_identifier(
                                self._violation_id_factory,
                                index=len(violations) + 1,
                                field_name="violation_id",
                            )
                        ),
                        code="ORPHAN_SOURCE",
                        severity=(
                            EvaluationViolationSeverity.WARNING
                        ),
                        message=(
                            "Source is not referenced by any "
                            f"evidence: {source_id}"
                        ),
                        blocking=False,
                        dimension=(
                            EvaluationDimension
                            .EVIDENCE_GROUNDING
                        ),
                        artifact_type=(
                            EvaluationArtifactType.SOURCE
                        ),
                        artifact_id=source_id,
                        remediation=(
                            "Remove the unused source or produce "
                            "evidence from it."
                        ),
                    )
                )

        total_evidence = len(snapshot.evidence)
        score_value = (
            (
                grounded_count
                + partial_count * 0.5
            )
            / total_evidence
            if total_evidence
            else 1.0
        )

        return EvidenceGroundingEvaluation(
            evaluation_id=self._new_identifier(
                self._evaluation_id_factory,
                field_name="evaluation_id",
            ),
            execution_id=snapshot.execution_id,
            score=EvaluationDimensionScore(
                dimension=(
                    EvaluationDimension.EVIDENCE_GROUNDING
                ),
                score=score_value,
                threshold=self._minimum_score,
                required=True,
                passed=score_value >= self._minimum_score,
                rationale=(
                    "Grounding score measures source existence, "
                    "exact normalized text containment, and "
                    "location validity."
                ),
                evaluator=self._evaluator_name,
            ),
            findings=findings,
            violations=violations,
            evidence_count=total_evidence,
            grounded_evidence_count=grounded_count,
            partially_grounded_evidence_count=partial_count,
            ungrounded_evidence_count=ungrounded_count,
            orphan_source_count=orphan_source_count,
        )

    def _location_is_valid(
        self,
        *,
        evidence: GroundingEvidenceArtifact,
        source: GroundingSourceArtifact,
    ) -> bool:
        """Return whether an evidence location is valid."""

        if evidence.location_reference is None:
            return True

        if not self._require_valid_location:
            return True

        location_id = (
            evidence.location_reference.strip().casefold()
        )
        source_location_ids = {
            value.strip().casefold()
            for value in source.locations
        }

        return location_id in source_location_ids

    @classmethod
    def _text_is_grounded(
        cls,
        *,
        evidence: GroundingEvidenceArtifact,
        source: GroundingSourceArtifact,
    ) -> bool:
        """Return whether normalized evidence occurs in source text."""

        normalized_evidence = cls._normalize_text(
            evidence.text
        )

        if evidence.location_reference is not None:
            location_text = cls._location_text(
                source=source,
                location_reference=evidence.location_reference,
            )

            if location_text is not None:
                return (
                    normalized_evidence
                    in cls._normalize_text(location_text)
                )

        return (
            normalized_evidence
            in cls._normalize_text(source.text)
        )

    @staticmethod
    def _location_text(
        *,
        source: GroundingSourceArtifact,
        location_reference: str,
    ) -> str | None:
        """Return location text using case-insensitive matching."""

        normalized_reference = (
            location_reference.strip().casefold()
        )

        return next(
            (
                text
                for location_id, text in source.locations.items()
                if location_id.strip().casefold()
                == normalized_reference
            ),
            None,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        """Normalize case and consecutive whitespace."""

        return " ".join(value.split()).casefold()

    def _finding(
        self,
        *,
        index: int,
        evidence: GroundingEvidenceArtifact,
        status: EvaluationFindingStatus,
        score: float,
        explanation: str,
    ) -> EvaluationArtifactFinding:
        """Build one evidence grounding finding."""

        return EvaluationArtifactFinding(
            finding_id=self._new_indexed_identifier(
                self._finding_id_factory,
                index=index,
                field_name="finding_id",
            ),
            artifact_type=EvaluationArtifactType.EVIDENCE,
            expected_artifact_id=evidence.evidence_id,
            actual_artifact_id=(
                evidence.evidence_id
                if status
                in {
                    EvaluationFindingStatus.MATCHED,
                    EvaluationFindingStatus.PARTIAL_MATCH,
                }
                else None
            ),
            status=status,
            score=score,
            explanation=explanation,
        )

    def _violation(
        self,
        *,
        index: int,
        code: str,
        message: str,
        evidence_id: str,
        blocking: bool,
    ) -> EvaluationViolation:
        """Build one evidence grounding violation."""

        return EvaluationViolation(
            violation_id=self._new_indexed_identifier(
                self._violation_id_factory,
                index=index,
                field_name="violation_id",
            ),
            code=code,
            severity=(
                EvaluationViolationSeverity.ERROR
                if blocking
                else EvaluationViolationSeverity.WARNING
            ),
            message=message,
            blocking=blocking,
            dimension=(
                EvaluationDimension.EVIDENCE_GROUNDING
            ),
            artifact_type=EvaluationArtifactType.EVIDENCE,
            artifact_id=evidence_id,
            remediation=(
                "Use evidence text and a location that "
                "exist in the referenced source."
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
            raise EvidenceGroundingEvaluatorError(
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
            raise EvidenceGroundingEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value
