"""Run one live Phase 8B local quality-review vertical slice."""

from __future__ import annotations

import json

from app.research.local_quality_review_executor import (
    InMemoryResearchReportRegistry,
    LocalResearchQualityReviewExecutor,
)
from app.research.research_synthesis_executor import (
    ResearchSynthesizedReport,
    ResearchSynthesizedSection,
)
from app.schemas.research_agent import ResearchAgentIdentity, ResearchAgentRole
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentInput,
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)
from app.services.ollama_client import OllamaClient


def identity(agent_id: str, role: ResearchAgentRole) -> ResearchAgentIdentity:
    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=role.value,
        role=role,
        description=f"{role.value} agent.",
    )


def main() -> int:
    report = ResearchSynthesizedReport(
        report_id="phase8b-report-001",
        title="Bounded Local Multi-Agent Review",
        executive_summary=(
            "A deterministic multi-agent pipeline can pass traceable artifacts "
            "between bounded specialist stages."
        ),
        sections=[
            ResearchSynthesizedSection(
                section_id="section-001",
                heading="Finding",
                content=(
                    "The current runtime bridge connects search, source reading, "
                    "evidence extraction, and claim construction through a shared "
                    "ResearchWorkspace."
                ),
                claim_ids=["claim-001"],
                order=1,
            )
        ],
        limitations=[
            "This fixture does not expose full source-quality or citation details.",
            "The local reviewer is advisory and non-authoritative.",
        ],
        follow_up_questions=[
            "How should production synthesis register reports for review?",
        ],
    )

    registry = InMemoryResearchReportRegistry()
    registry.register(
        reference_id="phase8b-report-output-001",
        report=report,
    )

    manager = ResearchAgentCapabilityProfile(
        profile_id="profile-manager-quality",
        agent=identity("agent-manager-001", ResearchAgentRole.MANAGER),
        capabilities=[ResearchAgentCapability.MANAGE_RESEARCH],
        can_delegate=True,
        delegatable_roles=[ResearchAgentRole.QUALITY_REVIEWER],
    )
    assignment = ResearchAgentTaskAssignment(
        assignment_id="assignment-quality-phase8b-001",
        request_id="research-phase8b-001",
        workspace_id="workspace-phase8b-001",
        assigner_profile=manager,
        assignee=identity(
            "agent-quality-001",
            ResearchAgentRole.QUALITY_REVIEWER,
        ),
        required_role=ResearchAgentRole.QUALITY_REVIEWER,
        required_capabilities=[ResearchAgentCapability.EVALUATE_REPORT],
        title="Run bounded local report review",
        objective=(
            "Evaluate report quality conservatively without claiming "
            "authoritative factual verification."
        ),
        instructions=[
            "Treat missing evidence or source details conservatively.",
        ],
        inputs=[
            ResearchAgentAssignmentInput(
                name="report-round-1",
                reference_type="research_report",
                reference_id="phase8b-report-output-001",
            )
        ],
        expected_output_type="research_quality_review",
        acceptance_criteria=[
            "Return a structured advisory quality review.",
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )

    executor = LocalResearchQualityReviewExecutor(
        client=OllamaClient(timeout_seconds=120.0),
        model="qwen3.5:4b",
        report_registry=registry,
    )
    result = executor.execute(assignment)

    print(
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
