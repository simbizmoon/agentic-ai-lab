"""Run Phase 8C full local multi-agent minimum smoke."""

from __future__ import annotations

import json

from app.research.claim_analyst_agent import ClaimAnalystAgent
from app.research.evidence_analyst_agent import EvidenceAnalystAgent
from app.research.in_memory_research_source_reader import (
    InMemoryResearchSourceReader,
)
from app.research.in_memory_research_source_search_tool import (
    InMemoryResearchSourceSearchTool,
)
from app.research.local_quality_review_executor import (
    InMemoryResearchReportRegistry,
    LocalResearchQualityReviewExecutor,
)
from app.research.local_runtime import WholeDocumentEvidenceExtractor
from app.research.multi_agent_pipeline_executors import (
    MultiAgentResearchRuntimeContext,
    PipelineResearchClaimExecutor,
    PipelineResearchEvidenceExecutor,
    PipelineResearchSearchExecutor,
    PipelineResearchSourceReaderExecutor,
)
from app.research.multi_agent_research_orchestrator import (
    MultiAgentResearchOrchestrator,
)
from app.research.multi_agent_synthesis_runtime import (
    RegisteredWorkspaceSynthesisExecutor,
)
from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
    PipelineEvidenceExtractorAdapter,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceReaderAdapter,
    PipelineSourceSearchAdapter,
)
from app.research.quality_reviewer_agent import QualityReviewerAgent
from app.research.review_revision_loop import ReviewRevisionLoop
from app.research.search_specialist_agent import SearchSpecialistAgent
from app.research.source_reader_specialist_agent import (
    SourceReaderSpecialistAgent,
)
from app.research.synthesis_specialist_agent import SynthesisSpecialistAgent
from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentRecord,
)
from app.schemas.in_memory_research_source import InMemoryResearchSourceRecord
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
from app.schemas.research_request import ResearchRequest, ResearchSourceType
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_document import ResearchSourceContentType
from app.schemas.research_task import ResearchTask, ResearchTaskGraph
from app.schemas.research_workspace import ResearchWorkspace
from app.services.ollama_client import OllamaClient


def main() -> int:
    request = ResearchRequest(
        request_id="phase8c-research-001",
        question="How does a bounded multi-agent research workflow hand off artifacts?",
        objective=(
            "Demonstrate traceable specialist handoffs and local advisory review."
        ),
        maximum_sources=1,
    )
    task = ResearchTask(
        task_id="phase8c-task-001",
        request_id=request.request_id,
        title="Inspect bounded multi-agent artifact handoff",
        question=request.question,
        objective=request.objective,
        completion_criteria=[
            "Produce one traceable evidence-backed claim.",
        ],
        expected_output="One traceable claim.",
    )
    task_graph = ResearchTaskGraph(
        request_id=request.request_id,
        tasks=[task],
    )
    query_set = ResearchSearchQuerySet(
        request_id=request.request_id,
        task_graph=task_graph,
        queries=[
            ResearchSearchQuery(
                query_id="phase8c-query-001",
                request_id=request.request_id,
                task_id=task.task_id,
                query_text="bounded multi-agent artifact handoff",
                preferred_source_types=[ResearchSourceType.ACADEMIC],
                maximum_results=1,
            )
        ],
    )
    context = MultiAgentResearchRuntimeContext(
        workspace=ResearchWorkspace(
            workspace_id="phase8c-workspace-001",
            request=request,
            task_graph=task_graph,
            query_set=query_set,
        )
    )

    source_record = InMemoryResearchSourceRecord(
        source_id="phase8c-source-001",
        title="Bounded Multi-Agent Artifact Handoff",
        url="https://example.com/phase8c-artifact-handoff",
        source_type=ResearchSourceType.ACADEMIC,
        snippet=(
            "Specialist agents exchange traceable artifacts through "
            "a shared workspace and explicit references."
        ),
        keywords=["multi-agent", "artifact", "workspace", "reference"],
    )
    document_record = InMemoryResearchDocumentRecord(
        source_id=source_record.source_id,
        url=source_record.url,
        content_type=ResearchSourceContentType.TEXT,
        content=(
            "A bounded multi-agent research workflow can pass traceable "
            "artifacts from search to reading, evidence extraction, claim "
            "construction, synthesis, and advisory quality review by using "
            "a shared workspace and explicit artifact references."
        ),
        language="en",
    )

    searcher = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(records=[source_record]),
        maximum_candidates=1,
    )
    reader = PipelineSourceReaderAdapter(
        InMemoryResearchSourceReader(records=[document_record])
    )
    extractor = PipelineEvidenceExtractorAdapter(
        WholeDocumentEvidenceExtractor()
    )
    builder = DeterministicPipelineClaimBuilder()

    search_agent = SearchSpecialistAgent(
        profile=profile(
            "phase8c-agent-search",
            ResearchAgentRole.SEARCH_SPECIALIST,
            ResearchAgentCapability.SEARCH_SOURCES,
        ),
        executor=PipelineResearchSearchExecutor(
            context=context,
            searcher=searcher,
        ),
        output_reference_id_factory=lambda: "phase8c-source-set",
    )
    reader_agent = SourceReaderSpecialistAgent(
        profile=profile(
            "phase8c-agent-reader",
            ResearchAgentRole.SOURCE_READER,
            ResearchAgentCapability.READ_SOURCES,
        ),
        executor=PipelineResearchSourceReaderExecutor(
            context=context,
            reader=reader,
        ),
        output_reference_id_factory=lambda: "phase8c-document-set",
    )
    evidence_agent = EvidenceAnalystAgent(
        profile=profile(
            "phase8c-agent-evidence",
            ResearchAgentRole.EVIDENCE_ANALYST,
            ResearchAgentCapability.EXTRACT_EVIDENCE,
        ),
        executor=PipelineResearchEvidenceExecutor(
            context=context,
            extractor=extractor,
        ),
        output_reference_id_factory=lambda: "phase8c-evidence-set",
    )
    claim_agent = ClaimAnalystAgent(
        profile=profile(
            "phase8c-agent-claim",
            ResearchAgentRole.CLAIM_ANALYST,
            ResearchAgentCapability.BUILD_CLAIMS,
        ),
        executor=PipelineResearchClaimExecutor(
            context=context,
            builder=builder,
        ),
        output_reference_id_factory=lambda: "phase8c-claim-set",
    )

    registry = InMemoryResearchReportRegistry()
    synthesis_executor = RegisteredWorkspaceSynthesisExecutor(
        context=context,
        report_registry=registry,
        report_reference_id_factory=lambda: "phase8c-report-output",
        report_id_factory=lambda: "phase8c-report-001",
    )
    synthesis_agent = SynthesisSpecialistAgent(
        profile=profile(
            "phase8c-agent-synthesis",
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
            ResearchAgentCapability.SYNTHESIZE_REPORT,
        ),
        executor=synthesis_executor,
        output_reference_id_factory=(
            synthesis_executor.take_output_reference_id
        ),
    )
    quality_agent = QualityReviewerAgent(
        profile=quality_profile(),
        executor=LocalResearchQualityReviewExecutor(
            client=OllamaClient(timeout_seconds=120.0),
            model="qwen3.5:4b",
            report_registry=registry,
        ),
        output_reference_id_factory=lambda: "phase8c-quality-output",
    )
    loop = ReviewRevisionLoop(
        synthesis_agent=synthesis_agent,
        quality_reviewer=quality_agent,
        maximum_revision_rounds=0,
    )
    orchestrator = MultiAgentResearchOrchestrator(
        search_agent=search_agent,
        source_reader_agent=reader_agent,
        evidence_analyst_agent=evidence_agent,
        claim_analyst_agent=claim_agent,
        review_revision_loop=loop,
    )

    result = orchestrator.run(
        search_assignment=assignment(
            "phase8c-assignment-search",
            "phase8c-agent-search",
            ResearchAgentRole.SEARCH_SPECIALIST,
        ),
        source_reader_template=assignment(
            "phase8c-assignment-reader",
            "phase8c-agent-reader",
            ResearchAgentRole.SOURCE_READER,
        ),
        evidence_template=assignment(
            "phase8c-assignment-evidence",
            "phase8c-agent-evidence",
            ResearchAgentRole.EVIDENCE_ANALYST,
        ),
        claim_template=assignment(
            "phase8c-assignment-claim",
            "phase8c-agent-claim",
            ResearchAgentRole.CLAIM_ANALYST,
        ),
        synthesis_template=assignment(
            "phase8c-assignment-synthesis",
            "phase8c-agent-synthesis",
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
        ),
        review_template=assignment(
            "phase8c-assignment-review",
            "phase8c-agent-quality",
            ResearchAgentRole.QUALITY_REVIEWER,
        ),
    )

    payload = result.model_dump(mode="json")
    payload["workspace_stage"] = context.workspace.stage.name
    payload["report_reference_resolved"] = (
        registry.resolve("phase8c-report-output").report_id
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def identity(agent_id: str, role: ResearchAgentRole) -> ResearchAgentIdentity:
    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=role.value,
        role=role,
        description=f"{role.value} agent.",
    )


def profile(
    agent_id: str,
    role: ResearchAgentRole,
    capability: ResearchAgentCapability,
) -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id=f"profile-{agent_id}",
        agent=identity(agent_id, role),
        capabilities=[capability],
    )


def quality_profile() -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id="profile-phase8c-quality",
        agent=identity(
            "phase8c-agent-quality",
            ResearchAgentRole.QUALITY_REVIEWER,
        ),
        capabilities=[
            ResearchAgentCapability.EVALUATE_REPORT,
            ResearchAgentCapability.REQUEST_REVISION,
            ResearchAgentCapability.APPROVE_RESULT,
        ],
    )


def manager_profile(
    role: ResearchAgentRole,
) -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id=f"profile-phase8c-manager-{role.value}",
        agent=identity(
            "phase8c-agent-manager",
            ResearchAgentRole.MANAGER,
        ),
        capabilities=[ResearchAgentCapability.MANAGE_RESEARCH],
        can_delegate=True,
        delegatable_roles=[role],
    )


def required_capability(
    role: ResearchAgentRole,
) -> ResearchAgentCapability:
    return {
        ResearchAgentRole.SEARCH_SPECIALIST: ResearchAgentCapability.SEARCH_SOURCES,
        ResearchAgentRole.SOURCE_READER: ResearchAgentCapability.READ_SOURCES,
        ResearchAgentRole.EVIDENCE_ANALYST: ResearchAgentCapability.EXTRACT_EVIDENCE,
        ResearchAgentRole.CLAIM_ANALYST: ResearchAgentCapability.BUILD_CLAIMS,
        ResearchAgentRole.SYNTHESIS_SPECIALIST: ResearchAgentCapability.SYNTHESIZE_REPORT,
        ResearchAgentRole.QUALITY_REVIEWER: ResearchAgentCapability.EVALUATE_REPORT,
    }[role]


def assignment(
    assignment_id: str,
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentTaskAssignment:
    return ResearchAgentTaskAssignment(
        assignment_id=assignment_id,
        request_id="phase8c-research-001",
        workspace_id="phase8c-workspace-001",
        assigner_profile=manager_profile(role),
        assignee=identity(agent_id, role),
        required_role=role,
        required_capabilities=[required_capability(role)],
        title=f"Execute {role.value}",
        objective=f"Complete the {role.value} stage.",
        instructions=["Preserve traceable artifact handoffs."],
        inputs=[
            ResearchAgentAssignmentInput(
                name="template-input",
                reference_type="template",
                reference_id="template-001",
            )
        ],
        expected_output_type=(
            "research_report"
            if role is ResearchAgentRole.SYNTHESIS_SPECIALIST
            else (
                "research_quality_review"
                if role is ResearchAgentRole.QUALITY_REVIEWER
                else f"{role.value}_output"
            )
        ),
        acceptance_criteria=["Return one structured primary output."],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )


if __name__ == "__main__":
    raise SystemExit(main())
