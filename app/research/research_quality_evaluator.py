"""Deterministic quality evaluation for synthesized research."""

from __future__ import annotations

from app.schemas.research_claim import (
    ResearchClaimStatus,
)
from app.schemas.research_evidence import (
    ResearchEvidenceStance,
)
from app.schemas.research_quality import (
    ResearchQualityEvaluation,
    ResearchQualityIssue,
    ResearchQualityIssueCode,
    ResearchQualityIssueSeverity,
)
from app.schemas.research_synthesis import (
    ResearchSynthesisReport,
)
from app.schemas.research_workspace import (
    ResearchWorkspace,
)


class ResearchQualityEvaluator:
    """Evaluate a synthesized report against its workspace."""

    def __init__(
        self,
        *,
        name: str = "deterministic-research-quality",
    ) -> None:
        if not name.strip():
            raise ValueError(
                "name must not be blank"
            )

        self._name = name

    @property
    def name(self) -> str:
        """Return the evaluator name."""

        return self._name

    def evaluate(
        self,
        *,
        workspace: ResearchWorkspace,
        report: ResearchSynthesisReport,
    ) -> ResearchQualityEvaluation:
        """Evaluate one synthesized research report."""

        self._validate_identity(
            workspace=workspace,
            report=report,
        )

        if workspace.claim_set is None:
            raise ValueError(
                "workspace must contain a claim set"
            )

        workspace_claims = workspace.claim_set.claims

        if not workspace_claims:
            raise ValueError(
                "workspace must contain at least one claim"
            )

        report_claim_ids = {
            claim_id.strip().casefold()
            for section in report.sections
            for claim_id in section.claim_ids
        }
        workspace_claim_ids = {
            claim.claim_id.strip().casefold()
            for claim in workspace_claims
        }

        missing_claim_ids = sorted(
            workspace_claim_ids - report_claim_ids
        )

        claim_coverage_score = round(
            len(
                workspace_claim_ids
                & report_claim_ids
            )
            / len(workspace_claim_ids),
            4,
        )

        cited_evidence_ids = {
            citation.evidence_id.strip().casefold()
            for citation in report.citations
        }

        uncited_claim_ids = [
            claim.claim_id
            for claim in workspace_claims
            if not any(
                citation.evidence_id.strip().casefold()
                in cited_evidence_ids
                for citation in claim.citations
            )
        ]

        citation_coverage_score = round(
            (
                len(workspace_claims)
                - len(uncited_claim_ids)
            )
            / len(workspace_claims),
            4,
        )

        source_diversity_score = self._source_diversity_score(
            source_count=report.source_count,
            claim_count=len(workspace_claims),
        )

        source_quality_score = self._source_quality_score(
            workspace
        )

        unhandled_claim_ids = (
            self._unhandled_contradictions(
                workspace
            )
        )

        contradiction_handling_score = round(
            (
                len(workspace_claims)
                - len(unhandled_claim_ids)
            )
            / len(workspace_claims),
            4,
        )

        overall_score = round(
            (
                claim_coverage_score * 0.30
                + citation_coverage_score * 0.25
                + source_diversity_score * 0.15
                + source_quality_score * 0.20
                + contradiction_handling_score * 0.10
            ),
            4,
        )

        issues = self._issues(
            missing_claim_ids=missing_claim_ids,
            uncited_claim_ids=uncited_claim_ids,
            source_diversity_score=source_diversity_score,
            source_quality_score=source_quality_score,
            unhandled_claim_ids=unhandled_claim_ids,
        )

        return ResearchQualityEvaluation(
            report=report,
            evaluator=self.name,
            claim_coverage_score=claim_coverage_score,
            citation_coverage_score=(
                citation_coverage_score
            ),
            source_diversity_score=(
                source_diversity_score
            ),
            source_quality_score=source_quality_score,
            contradiction_handling_score=(
                contradiction_handling_score
            ),
            overall_score=overall_score,
            quality_level=(
                ResearchQualityEvaluation
                .level_for_score(overall_score)
            ),
            issues=issues,
            metadata={
                "method": "weighted-deterministic",
                "workspace_id": workspace.workspace_id,
            },
        )

    @staticmethod
    def _validate_identity(
        *,
        workspace: ResearchWorkspace,
        report: ResearchSynthesisReport,
    ) -> None:
        """Validate report and workspace identity."""

        if report.workspace_id != workspace.workspace_id:
            raise ValueError(
                "report workspace_id must match workspace"
            )

        if (
            report.request_id
            != workspace.request.request_id
        ):
            raise ValueError(
                "report request_id must match workspace"
            )

    @staticmethod
    def _source_diversity_score(
        *,
        source_count: int,
        claim_count: int,
    ) -> float:
        """Score source diversity relative to claim count."""

        required_sources = max(
            1,
            min(claim_count, 3),
        )

        return round(
            min(
                source_count / required_sources,
                1.0,
            ),
            4,
        )

    @staticmethod
    def _source_quality_score(
        workspace: ResearchWorkspace,
    ) -> float:
        """Return average source quality score."""

        evaluations = (
            workspace.source_quality_evaluations
        )

        if not evaluations:
            return 0.5

        return round(
            sum(
                evaluation.overall_score
                for evaluation in evaluations
            )
            / len(evaluations),
            4,
        )

    @staticmethod
    def _unhandled_contradictions(
        workspace: ResearchWorkspace,
    ) -> list[str]:
        """Return claims that fail to acknowledge contradictions."""

        if (
            workspace.claim_set is None
            or workspace.evidence_set is None
        ):
            return []

        evidence_by_id = {
            evidence.evidence_id.strip().casefold():
            evidence
            for evidence
            in workspace.evidence_set.evidence
        }

        unhandled: list[str] = []

        for claim in workspace.claim_set.claims:
            cited_evidence = [
                evidence_by_id.get(
                    citation.evidence_id
                    .strip()
                    .casefold()
                )
                for citation in claim.citations
            ]

            has_contradiction = any(
                evidence is not None
                and evidence.stance
                is ResearchEvidenceStance.CONTRADICTS
                for evidence in cited_evidence
            )

            if (
                has_contradiction
                and claim.status
                is not ResearchClaimStatus.CONTESTED
            ):
                unhandled.append(claim.claim_id)

        return unhandled

    @staticmethod
    def _issues(
        *,
        missing_claim_ids: list[str],
        uncited_claim_ids: list[str],
        source_diversity_score: float,
        source_quality_score: float,
        unhandled_claim_ids: list[str],
    ) -> list[ResearchQualityIssue]:
        """Build deterministic quality issues."""

        issues: list[ResearchQualityIssue] = []

        if missing_claim_ids:
            issues.append(
                ResearchQualityIssue(
                    code=(
                        ResearchQualityIssueCode
                        .MISSING_CLAIMS
                    ),
                    severity=(
                        ResearchQualityIssueSeverity.ERROR
                    ),
                    message=(
                        "Some workspace claims are missing "
                        "from the synthesized report."
                    ),
                    related_ids=missing_claim_ids,
                )
            )

        if uncited_claim_ids:
            issues.append(
                ResearchQualityIssue(
                    code=(
                        ResearchQualityIssueCode
                        .UNCITED_CLAIMS
                    ),
                    severity=(
                        ResearchQualityIssueSeverity.ERROR
                    ),
                    message=(
                        "Some claims do not have report citations."
                    ),
                    related_ids=uncited_claim_ids,
                )
            )

        if source_diversity_score < 0.67:
            issues.append(
                ResearchQualityIssue(
                    code=(
                        ResearchQualityIssueCode
                        .LOW_SOURCE_DIVERSITY
                    ),
                    severity=(
                        ResearchQualityIssueSeverity.WARNING
                    ),
                    message=(
                        "The report relies on too few "
                        "independent sources."
                    ),
                )
            )

        if source_quality_score < 0.60:
            issues.append(
                ResearchQualityIssue(
                    code=(
                        ResearchQualityIssueCode
                        .LOW_SOURCE_QUALITY
                    ),
                    severity=(
                        ResearchQualityIssueSeverity.WARNING
                    ),
                    message=(
                        "Average source quality is below "
                        "the preferred threshold."
                    ),
                )
            )

        if unhandled_claim_ids:
            issues.append(
                ResearchQualityIssue(
                    code=(
                        ResearchQualityIssueCode
                        .UNHANDLED_CONTRADICTIONS
                    ),
                    severity=(
                        ResearchQualityIssueSeverity.ERROR
                    ),
                    message=(
                        "Some claims do not acknowledge "
                        "contradicting evidence."
                    ),
                    related_ids=unhandled_claim_ids,
                )
            )

        return issues
