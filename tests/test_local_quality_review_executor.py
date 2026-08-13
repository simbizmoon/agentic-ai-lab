"""Tests for the bounded Ollama-backed multi-agent quality reviewer."""

from __future__ import annotations

import json

from app.research.local_quality_review_executor import (
    InMemoryResearchReportRegistry,
    LocalResearchQualityReviewExecutor,
)
from app.research.quality_reviewer_agent import QualityReviewerAgent
from app.research.research_quality_review_executor import (
    ResearchQualityDecision,
)
from app.research.research_synthesis_executor import (
    ResearchSynthesizedReport,
    ResearchSynthesizedSection,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentInput,
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)
from app.schemas.research_agent_result import ResearchAgentResultStatus
from app.services.ollama_client import OllamaGenerateResponse


class FakeOllamaClient:
    """Return one deterministic structured quality judgment."""

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> OllamaGenerateResponse:
        self.calls.append(kwargs)
        return OllamaGenerateResponse(
            model="qwen3.5:4b",
            response=json.dumps(self.response),
            thinking="",
            done=True,
            done_reason="stop",
            total_duration_ns=10_000_000,
            load_duration_ns=1_000_000,
            prompt_eval_count=120,
            prompt_eval_duration_ns=2_000_000,
            eval_count=48,
            eval_duration_ns=7_000_000,
        )


def test_local_quality_executor_maps_structured_revision_review() -> None:
    registry = InMemoryResearchReportRegistry()
    registry.register(
        reference_id="report-output-001",
        report=_report(),
    )
    client = FakeOllamaClient(
        {
            "decision": "revision_required",
            "completeness": 0.7,
            "evidence_coverage": 0.6,
            "citation_quality": 0.5,
            "source_quality": 0.5,
            "logical_consistency": 0.9,
            "clarity": 0.9,
            "summary": "The report is clear but evidence traceability is thin.",
            "strengths": ["Clear organization"],
            "revision_requests": [
                {
                    "target_type": "report",
                    "target_id": "report-001",
                    "issue": "Evidence traceability is insufficient.",
                    "required_action": (
                        "Add explicit evidence and citation traceability."
                    ),
                    "severity": "major",
                    "required": True,
                }
            ],
            "rejection_reason": None,
        }
    )

    executor = LocalResearchQualityReviewExecutor(
        client=client,
        model="qwen3.5:4b",
        report_registry=registry,
        review_id_factory=lambda: "review-local-001",
    )

    result = executor.execute(_assignment())

    assert result.review is not None
    assert result.review.decision is ResearchQualityDecision.REVISION_REQUIRED
    assert result.review.report_id == "report-001"
    assert result.review.metadata["provider"] == "ollama-local"
    assert result.review.metadata["authoritative"] == "false"
    assert len(result.review.revision_requests) == 1
    assert result.input_token_count == 120
    assert result.output_token_count == 48
    assert result.tool_call_count == 1
    assert client.calls[0]["think"] is False
    assert client.calls[0]["response_format"]



def test_revision_required_without_revision_is_repaired() -> None:
    registry = InMemoryResearchReportRegistry()
    registry.register(
        reference_id="report-output-001",
        report=_report(),
    )
    client = FakeOllamaClient(
        {
            "decision": "revision_required",
            "completeness": 0.7,
            "evidence_coverage": 0.5,
            "citation_quality": 0.4,
            "source_quality": 0.5,
            "logical_consistency": 0.8,
            "clarity": 0.8,
            "summary": (
                "The report needs stronger evidence traceability."
            ),
            "strengths": ["Clear organization"],
            "revision_requests": [],
            "rejection_reason": None,
        }
    )
    executor = LocalResearchQualityReviewExecutor(
        client=client,
        model="qwen3.5:4b",
        report_registry=registry,
        review_id_factory=lambda: "review-local-repair-001",
    )

    result = executor.execute(_assignment())

    assert result.review is not None
    assert result.review.decision is ResearchQualityDecision.REVISION_REQUIRED
    assert len(result.review.revision_requests) == 1
    assert result.review.revision_requests[0].required is True
    assert result.review.metadata["semantic_repair"] == "true"

def test_existing_quality_reviewer_agent_runs_local_executor() -> None:
    registry = InMemoryResearchReportRegistry()
    registry.register(
        reference_id="report-output-001",
        report=_report(),
    )
    client = FakeOllamaClient(
        {
            "decision": "approved",
            "completeness": 0.8,
            "evidence_coverage": 0.7,
            "citation_quality": 0.7,
            "source_quality": 0.6,
            "logical_consistency": 0.9,
            "clarity": 0.9,
            "summary": "The report is acceptable for bounded advisory review.",
            "strengths": ["Clear synthesis"],
            "revision_requests": [],
            "rejection_reason": None,
        }
    )
    executor = LocalResearchQualityReviewExecutor(
        client=client,
        model="qwen3.5:4b",
        report_registry=registry,
        review_id_factory=lambda: "review-local-002",
    )
    reviewer = QualityReviewerAgent(
        profile=_reviewer_profile(),
        executor=executor,
        result_id_factory=lambda: "result-quality-local-001",
        output_reference_id_factory=lambda: "quality-review-output-001",
    )

    result = reviewer.execute(_assignment())

    assert result.status is ResearchAgentResultStatus.SUCCEEDED
    assert result.payload["review"]["decision"] == "approved"
    assert result.metadata["provider"] == "ollama-local"
    assert result.metadata["authoritative"] == "false"


def test_report_registry_resolves_reference_case_insensitively() -> None:
    registry = InMemoryResearchReportRegistry()
    report = _report()
    registry.register(
        reference_id="Report-Output-001",
        report=report,
    )

    assert registry.resolve(" report-output-001 ") is report


def _report() -> ResearchSynthesizedReport:
    return ResearchSynthesizedReport(
        report_id="report-001",
        title="Multi-Agent Research",
        executive_summary=(
            "Structured specialist collaboration improves traceability."
        ),
        sections=[
            ResearchSynthesizedSection(
                section_id="section-001",
                heading="Findings",
                content=(
                    "Specialist stages exchange referenced research artifacts."
                ),
                claim_ids=["claim-001"],
                order=1,
            )
        ],
        limitations=[
            "The current test uses a deterministic fixture report.",
        ],
    )


def _identity(
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentIdentity:
    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=role.value,
        role=role,
        description=f"{role.value} agent.",
    )


def _reviewer_profile() -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id="profile-quality-reviewer",
        agent=_identity(
            "agent-quality-001",
            ResearchAgentRole.QUALITY_REVIEWER,
        ),
        capabilities=[
            ResearchAgentCapability.EVALUATE_REPORT,
            ResearchAgentCapability.REQUEST_REVISION,
            ResearchAgentCapability.APPROVE_RESULT,
        ],
    )


def _manager_profile() -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-quality",
        agent=_identity(
            "agent-manager-001",
            ResearchAgentRole.MANAGER,
        ),
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.QUALITY_REVIEWER,
        ],
    )


def _assignment() -> ResearchAgentTaskAssignment:
    return ResearchAgentTaskAssignment(
        assignment_id="assignment-quality-001",
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=_manager_profile(),
        assignee=_identity(
            "agent-quality-001",
            ResearchAgentRole.QUALITY_REVIEWER,
        ),
        required_role=ResearchAgentRole.QUALITY_REVIEWER,
        required_capabilities=[
            ResearchAgentCapability.EVALUATE_REPORT,
        ],
        title="Review research report",
        objective="Evaluate the synthesized research report.",
        instructions=[
            "Review the supplied report conservatively.",
        ],
        inputs=[
            ResearchAgentAssignmentInput(
                name="report-round-1",
                reference_type="research_report",
                reference_id="report-output-001",
            )
        ],
        expected_output_type="research_quality_review",
        acceptance_criteria=[
            "Return one structured quality review.",
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )
