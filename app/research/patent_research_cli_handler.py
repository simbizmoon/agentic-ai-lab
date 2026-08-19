"""CLI adapter for bounded patent technical research."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from app.research.patent_technical_research_report_runtime import (
    PatentTechnicalResearchReportRuntime,
    build_openai_epo_patent_technical_research_report_runtime,
)
from app.schemas.patent_research_request import PatentResearchRequest


class PatentResearchCliHandler:
    """Run bounded patent research and render a human-readable CLI result."""

    def __init__(
        self,
        *,
        runtime_factory: Callable[
            [], PatentTechnicalResearchReportRuntime
        ] = build_openai_epo_patent_technical_research_report_runtime,
        request_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._runtime_factory = runtime_factory
        self._request_id_factory = request_id_factory or (
            lambda: f"patent-cli-{uuid4()}"
        )

    def __call__(self, request: PatentResearchRequest) -> int:
        request_id = self._request_id_factory().strip()
        if not request_id:
            raise ValueError("request_id factory returned blank value")

        result = self._runtime_factory().execute(request, request_id=request_id)
        report = result.synthesis.report
        synthesis = result.synthesis.synthesis.synthesis
        verification = result.verification.verification

        print("AIRA patent technical research")
        print(f"request_id={report.request_id}")
        print(f"report_id={report.report_id}")
        if report.findings:
            print("result_status=findings_available")
            print(f"synthesis_accepted={str(verification.accepted).lower()}")
        else:
            print("result_status=no_relevant_findings")
            print("synthesis_accepted=not_applicable")
        print()

        print("=== VERIFIED METADATA / TECHNICAL RELEVANCE ===")
        if not report.findings:
            print("No semantically evaluated relevant finding was available.")
        for finding in report.findings:
            publication_date = (
                finding.publication_date.isoformat()
                if finding.publication_date is not None
                else "unknown"
            )
            print(f"[{finding.finding_id}]")
            print(f"publication_number={finding.publication_number}")
            print(f"application_number={finding.application_number or 'unknown'}")
            print(f"priority_claim_count={len(finding.priority_claims)}")
            for index, claim in enumerate(finding.priority_claims, start=1):
                priority_date = (
                    claim.priority_date.isoformat()
                    if claim.priority_date is not None
                    else "unknown"
                )
                print(f"priority_claim[{index}].number={claim.priority_number}")
                print(f"priority_claim[{index}].date={priority_date}")
            print(f"ipc_classification_count={len(finding.ipc_classifications)}")
            for index, classification in enumerate(
                finding.ipc_classifications,
                start=1,
            ):
                print(f"ipc_classification[{index}].text={classification.text}")
            print(f"cpc_classification_count={len(finding.cpc_classifications)}")
            for index, classification in enumerate(
                finding.cpc_classifications,
                start=1,
            ):
                print(f"cpc_classification[{index}].section={classification.section}")
                print(
                    f"cpc_classification[{index}].class_number="
                    f"{classification.class_number}"
                )
                print(f"cpc_classification[{index}].subclass={classification.subclass}")
                print(
                    f"cpc_classification[{index}].main_group="
                    f"{classification.main_group}"
                )
                print(f"cpc_classification[{index}].subgroup={classification.subgroup}")
            print(f"applicant_count={len(finding.applicants)}")
            for index, party in enumerate(finding.applicants, start=1):
                print(f"applicant[{index}].name={party.name}")
            print(f"inventor_count={len(finding.inventors)}")
            for index, party in enumerate(finding.inventors, start=1):
                print(f"inventor[{index}].name={party.name}")
            print(f"title={finding.title}")
            print(f"publication_date={publication_date}")
            print(f"source_family={finding.source_family.value}")
            print(
                "metadata_verification_state="
                f"{finding.metadata_verification_state.value}"
            )
            print(f"relevance_level={finding.relevance_level.value}")
            print(f"relevance_score={finding.relevance_score:.3f}")
            print(f"relevance_rationale={finding.relevance_rationale}")
            print(f"source_url={finding.source_url}")
            print()

        print("=== EVIDENCE / PROVENANCE ===")
        for finding in report.findings:
            evidence = finding.evidence
            print(f"[{finding.finding_id}]")
            print(f"evidence_id={evidence.evidence_id}")
            print(f"source_id={evidence.source_id}")
            print(f"document_id={evidence.document_id}")
            print(
                f"character_range={evidence.start_character}:{evidence.end_character}"
            )
            print(f"excerpt={evidence.excerpt}")
            print()

        if report.unevaluated_evidence_ids:
            print(
                "unevaluated_evidence_ids=" + ",".join(report.unevaluated_evidence_ids)
            )
            print()

        print("=== SYNTHESIS ===")
        print(f"overall_summary={synthesis.overall_summary}")
        for item in synthesis.finding_summaries:
            print(f"{item.finding_id}.technical_summary={item.technical_summary}")
        if synthesis.limitations:
            print("limitations:")
            for limitation in synthesis.limitations:
                print(f"- {limitation}")
        print()

        print("=== SUPPORT VERIFICATION ===")
        overall = verification.overall_verification
        if report.findings:
            support_level = (
                overall.support_level.value
                if overall.support_level is not None
                else "not_applicable"
            )
            print(f"overall_decision={overall.decision.value}")
            print(f"overall_support_level={support_level}")
            print(f"overall_entailment_score={overall.entailment_score:.3f}")
        else:
            print("verification_status=not_applicable")
        print(f"overall_rationale={overall.rationale}")

        for item in verification.finding_verifications:
            print(f"{item.finding_id}.decision={item.decision.value}")
            print(f"{item.finding_id}.support_level={item.support_level.value}")
            print(f"{item.finding_id}.entailment_score={item.entailment_score:.3f}")

        print()
        print("=== SCOPE NOTICE ===")
        print(report.scope_notice)
        print(
            "synthesis_accepted describes only whether generated technical "
            "synthesis is fully supported by the supplied evidence."
        )
        return 0
