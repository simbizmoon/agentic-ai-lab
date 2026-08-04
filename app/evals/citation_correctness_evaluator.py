"""Deterministic citation correctness evaluation."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

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
from app.evals.evaluation_result import (
    EvaluationArtifactFinding,
    EvaluationArtifactType,
    EvaluationDimensionScore,
    EvaluationFindingStatus,
    EvaluationViolation,
    EvaluationViolationSeverity,
)


class CitationCorrectnessEvaluation(BaseModel):
    """Complete deterministic citation correctness result."""

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
    citation_count: int = Field(ge=0)
    valid_citation_count: int = Field(ge=0)
    invalid_citation_count: int = Field(ge=0)
    uncited_claim_count: int = Field(ge=0)
    orphan_citation_count: int = Field(ge=0)

    @property
    def passed(self) -> bool:
        """Return whether citation correctness passed."""

        return self.score.passed


class CitationCorrectnessEvaluator:
    """Evaluate citation reference integrity deterministically."""

    def __init__(
        self,
        *,
        minimum_score: float = 1.0,
        require_citation_per_claim: bool = True,
        evaluation_id_factory: Callable[[], str] | None = None,
        finding_id_factory: Callable[[int], str] | None = None,
        violation_id_factory: (
            Callable[[int], str] | None
        ) = None,
        evaluator_name: str = (
            "deterministic-citation-correctness-evaluator"
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
        self._require_citation_per_claim = (
            require_citation_per_claim
        )
        self._evaluation_id_factory = (
            evaluation_id_factory
            or (lambda: f"citation-evaluation-{uuid4()}")
        )
        self._finding_id_factory = (
            finding_id_factory
            or (
                lambda index: (
                    f"citation-finding-{index}-{uuid4()}"
                )
            )
        )
        self._violation_id_factory = (
            violation_id_factory
            or (
                lambda index: (
                    f"citation-violation-{index}-{uuid4()}"
                )
            )
        )
        self._evaluator_name = evaluator_name

    def evaluate(
        self,
        snapshot: CitationEvaluationSnapshot,
    ) -> CitationCorrectnessEvaluation:
        """Evaluate one citation snapshot."""

        source_ids = {
            source_id.strip().casefold()
            for source_id in snapshot.source_ids
        }
        evidence_source_map = {
            evidence_id.strip().casefold(): (
                source_id.strip().casefold()
            )
            for evidence_id, source_id
            in snapshot.evidence_source_map.items()
        }
        claim_citation_map = {
            claim_id.strip().casefold(): {
                citation_id.strip().casefold()
                for citation_id in citation_ids
            }
            for claim_id, citation_ids
            in snapshot.claim_citation_map.items()
        }
        citations = {
            citation.citation_id.strip().casefold(): citation
            for citation in snapshot.citations
        }

        findings: list[EvaluationArtifactFinding] = []
        violations: list[EvaluationViolation] = []
        valid_citation_count = 0
        invalid_citation_count = 0

        for citation in snapshot.citations:
            errors = self._citation_errors(
                citation=citation,
                source_ids=source_ids,
                evidence_source_map=evidence_source_map,
                claim_citation_map=claim_citation_map,
            )
            valid = not errors

            findings.append(
                EvaluationArtifactFinding(
                    finding_id=self._new_indexed_identifier(
                        self._finding_id_factory,
                        index=len(findings) + 1,
                        field_name="finding_id",
                    ),
                    artifact_type=(
                        EvaluationArtifactType.CITATION
                    ),
                    expected_artifact_id=(
                        citation.citation_id
                    ),
                    actual_artifact_id=(
                        citation.citation_id
                    ),
                    status=(
                        EvaluationFindingStatus.MATCHED
                        if valid
                        else EvaluationFindingStatus.PARTIAL_MATCH
                    ),
                    score=1.0 if valid else 0.0,
                    explanation=(
                        "Citation references are valid."
                        if valid
                        else "; ".join(
                            message
                            for _, message in errors
                        )
                    ),
                )
            )

            if valid:
                valid_citation_count += 1
                continue

            invalid_citation_count += 1

            for code, message in errors:
                violations.append(
                    self._violation(
                        index=len(violations) + 1,
                        code=code,
                        message=message,
                        artifact_id=citation.citation_id,
                    )
                )

        uncited_claim_count = 0

        if self._require_citation_per_claim:
            for claim_id, citation_ids in (
                snapshot.claim_citation_map.items()
            ):
                if citation_ids:
                    continue

                uncited_claim_count += 1
                violations.append(
                    self._violation(
                        index=len(violations) + 1,
                        code="UNCITED_CLAIM",
                        message=(
                            "Claim has no citation: "
                            f"{claim_id}"
                        ),
                        artifact_id=claim_id,
                    )
                )

        referenced_citation_ids = {
            citation_id
            for citation_ids in claim_citation_map.values()
            for citation_id in citation_ids
        }
        orphan_citation_ids = (
            set(citations) - referenced_citation_ids
        )
        orphan_citation_count = len(orphan_citation_ids)

        for citation_id in sorted(orphan_citation_ids):
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    code="ORPHAN_CITATION",
                    message=(
                        "Citation is not referenced by any "
                        f"claim: {citation_id}"
                    ),
                    artifact_id=citation_id,
                )
            )

        total_checks = (
            len(snapshot.citations)
            + (
                len(snapshot.claim_citation_map)
                if self._require_citation_per_claim
                else 0
            )
        )
        successful_claim_checks = (
            len(snapshot.claim_citation_map)
            - uncited_claim_count
            if self._require_citation_per_claim
            else 0
        )
        successful_checks = (
            valid_citation_count
            + successful_claim_checks
        )
        score_value = (
            successful_checks / total_checks
            if total_checks
            else 1.0
        )

        return CitationCorrectnessEvaluation(
            evaluation_id=self._new_identifier(
                self._evaluation_id_factory,
                field_name="evaluation_id",
            ),
            execution_id=snapshot.execution_id,
            score=EvaluationDimensionScore(
                dimension=(
                    EvaluationDimension.CITATION_CORRECTNESS
                ),
                score=score_value,
                threshold=self._minimum_score,
                required=True,
                passed=score_value >= self._minimum_score,
                rationale=(
                    "Citation score measures valid citation "
                    "references and cited claims."
                ),
                evaluator=self._evaluator_name,
            ),
            findings=findings,
            violations=violations,
            citation_count=len(snapshot.citations),
            valid_citation_count=valid_citation_count,
            invalid_citation_count=invalid_citation_count,
            uncited_claim_count=uncited_claim_count,
            orphan_citation_count=orphan_citation_count,
        )

    @staticmethod
    def _citation_errors(
        *,
        citation: ActualCitationArtifact,
        source_ids: set[str],
        evidence_source_map: dict[str, str],
        claim_citation_map: dict[str, set[str]],
    ) -> list[tuple[str, str]]:
        """Return reference-integrity errors for one citation."""

        errors: list[tuple[str, str]] = []
        citation_id = (
            citation.citation_id.strip().casefold()
        )
        claim_id = citation.claim_id.strip().casefold()
        evidence_id = (
            citation.evidence_id.strip().casefold()
        )
        source_id = citation.source_id.strip().casefold()

        if source_id not in source_ids:
            errors.append(
                (
                    "UNKNOWN_CITATION_SOURCE",
                    (
                        "Citation references an unknown source: "
                        f"{citation.source_id}"
                    ),
                )
            )

        evidence_source_id = evidence_source_map.get(
            evidence_id
        )

        if evidence_source_id is None:
            errors.append(
                (
                    "UNKNOWN_CITATION_EVIDENCE",
                    (
                        "Citation references unknown evidence: "
                        f"{citation.evidence_id}"
                    ),
                )
            )
        elif evidence_source_id != source_id:
            errors.append(
                (
                    "CITATION_SOURCE_MISMATCH",
                    (
                        "Citation source does not match "
                        "the evidence source."
                    ),
                )
            )

        claim_citation_ids = claim_citation_map.get(claim_id)

        if claim_citation_ids is None:
            errors.append(
                (
                    "UNKNOWN_CITATION_CLAIM",
                    (
                        "Citation references an unknown claim: "
                        f"{citation.claim_id}"
                    ),
                )
            )
        elif citation_id not in claim_citation_ids:
            errors.append(
                (
                    "CLAIM_CITATION_LINK_MISSING",
                    (
                        "Claim does not reference "
                        "the citation."
                    ),
                )
            )

        return errors

    def _violation(
        self,
        *,
        index: int,
        code: str,
        message: str,
        artifact_id: str,
    ) -> EvaluationViolation:
        """Build one blocking citation violation."""

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
            dimension=(
                EvaluationDimension.CITATION_CORRECTNESS
            ),
            artifact_type=EvaluationArtifactType.CITATION,
            artifact_id=artifact_id,
            remediation=(
                "Repair the claim, citation, evidence, "
                "and source references."
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
            raise CitationCorrectnessEvaluatorError(
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
            raise CitationCorrectnessEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value
