"""Run Phase 9B frozen repeated Single-vs-Multi architecture benchmark."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median

from app.evals.multi_agent_workflow_evaluator import MultiAgentWorkflowEvaluator
from app.research.claim_analyst_agent import ClaimAnalystAgent
from app.research.deterministic_quality_review_executor import (
    DeterministicApprovedQualityReviewExecutor,
)
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
from app.research.local_runtime import (
    LocalDocumentSourceQualityEvaluator,
    WholeDocumentEvidenceExtractor,
)
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
from app.research.pipeline_compatibility import (
    PipelineQueryPlannerAdapter,
    PipelineTaskDecomposerAdapter,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceReaderAdapter,
    PipelineSourceSearchAdapter,
)
from app.research.quality_reviewer_agent import QualityReviewerAgent
from app.research.research_execution_benchmark import (
    ResearchExecutionBenchmarkNormalizer,
    research_workspace_artifacts_equivalent,
)
from app.research.research_request_validator import ResearchRequestValidator
from app.research.review_revision_loop import ReviewRevisionLoop
from app.research.search_specialist_agent import SearchSpecialistAgent
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
)
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


@dataclass(frozen=True)
class BenchmarkFixture:
    """One frozen local research case."""

    fixture_id: str
    question: str
    objective: str
    query_text: str
    title: str
    url: str
    content: str
    keywords: tuple[str, ...]


FIXTURES = (
    BenchmarkFixture(
        fixture_id="artifact-handoff",
        question=(
            "How does a bounded multi-agent research workflow "
            "hand off artifacts?"
        ),
        objective=(
            "Explain traceable specialist handoffs through a shared workspace."
        ),
        query_text="bounded multi-agent artifact handoff",
        title="Bounded Multi-Agent Artifact Handoff",
        url="https://example.com/phase9b/artifact-handoff",
        content=(
            "A bounded multi-agent research workflow can pass traceable "
            "artifacts from search to reading, evidence extraction, claim "
            "construction, and synthesis through a shared workspace and "
            "explicit artifact references."
        ),
        keywords=(
            "bounded",
            "multi-agent",
            "artifact",
            "handoff",
            "workspace",
        ),
    ),
    BenchmarkFixture(
        fixture_id="evidence-traceability",
        question=(
            "How does evidence traceability support grounded research?"
        ),
        objective=(
            "Explain how sources, documents, evidence, claims, and citations "
            "remain traceable."
        ),
        query_text="grounded research evidence traceability",
        title="Evidence Traceability in Grounded Research",
        url="https://example.com/phase9b/evidence-traceability",
        content=(
            "Grounded research preserves traceability by linking a source "
            "candidate to a read document, extracted evidence, a supported "
            "claim, and a citation that refers back to the evidence."
        ),
        keywords=(
            "grounded",
            "research",
            "evidence",
            "traceability",
            "citation",
        ),
    ),
    BenchmarkFixture(
        fixture_id="deterministic-coordination",
        question=(
            "Why can deterministic coordination help bound multi-agent "
            "research execution?"
        ),
        objective=(
            "Explain how fixed stage ordering and explicit assignments "
            "constrain coordination."
        ),
        query_text="deterministic multi-agent coordination bounded execution",
        title="Deterministic Coordination for Bounded Research",
        url="https://example.com/phase9b/deterministic-coordination",
        content=(
            "Deterministic multi-agent coordination bounds execution by "
            "using fixed stage ordering, explicit assignments, typed artifact "
            "handoffs, and a finite review loop instead of unconstrained "
            "autonomous agent selection."
        ),
        keywords=(
            "deterministic",
            "multi-agent",
            "coordination",
            "bounded",
            "assignment",
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--local-model", default="qwen3.5:4b")
    parser.add_argument(
        "--ollama-base-url",
        default="http://127.0.0.1:11434",
    )
    parser.add_argument(
        "--ollama-timeout-seconds",
        type=float,
        default=120.0,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/mnt/ai-data/experiments/phase9-frozen"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = args.output_dir / f"{timestamp}_phase9b-frozen"
    root.mkdir(parents=True, exist_ok=False)

    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for fixture_index, fixture in enumerate(FIXTURES, start=1):
        for repeat in range(1, args.repeats + 1):
            label = (
                f"FIXTURE {fixture_index}/{len(FIXTURES)} "
                f"{fixture.fixture_id} REPEAT {repeat}/{args.repeats}"
            )
            print(f"\n=== {label}: SINGLE ===")

            try:
                pair = run_fixture_pair(
                    fixture=fixture,
                    repeat=repeat,
                    local_model=args.local_model,
                    ollama_base_url=args.ollama_base_url,
                    ollama_timeout_seconds=args.ollama_timeout_seconds,
                )
                rows.append(pair)
                print(
                    "single="
                    f"{pair['single_wall_seconds']:.6f}s "
                    "multi_det="
                    f"{pair['multi_deterministic_wall_seconds']:.6f}s "
                    "multi_local="
                    f"{pair['multi_local_wall_seconds']:.6f}s "
                    "artifact_equal="
                    f"{pair['all_upstream_artifacts_equivalent']}"
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                failures.append(
                    {
                        "fixture_id": fixture.fixture_id,
                        "repeat": repeat,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                print(f"FAILED: {type(exc).__name__}: {exc}")

    result = {
        "benchmark": "phase9b-frozen-single-vs-multi",
        "fixtures": [fixture.fixture_id for fixture in FIXTURES],
        "repeats_per_fixture": args.repeats,
        "local_model": args.local_model,
        "successful_triplets": len(rows),
        "failed_triplets": len(failures),
        "rows": rows,
        "aggregate": aggregate(rows) if rows else None,
        "failures": failures,
        "interpretation_policy": {
            "architecture_overhead": (
                "multi_deterministic minus single"
            ),
            "local_reviewer_overhead": (
                "multi_local minus multi_deterministic"
            ),
            "decision_ready_requires": [
                "all upstream artifacts equivalent",
                "deterministic architecture runs successful",
                "multi workflow integrity passed",
            ],
            "local_reviewer_is_authoritative": False,
        },
    }

    path = root / "comparison.json"
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nPhase 9B comparison: {path}")
    print(
        f"successful_triplets={len(rows)} "
        f"failed_triplets={len(failures)}"
    )
    return 0 if rows else 1


def run_fixture_pair(
    *,
    fixture: BenchmarkFixture,
    repeat: int,
    local_model: str,
    ollama_base_url: str,
    ollama_timeout_seconds: float,
) -> dict[str, object]:
    request_id = f"phase9b-{fixture.fixture_id}-{repeat:02d}"
    workspace_id = f"{request_id}-workspace"
    request = ResearchRequest(
        request_id=request_id,
        question=fixture.question,
        objective=fixture.objective,
        include_topics=[fixture.query_text],
        preferred_source_types=[ResearchSourceType.ACADEMIC],
        maximum_sources=1,
    )
    source_record = InMemoryResearchSourceRecord(
        source_id=f"{request_id}-source",
        title=fixture.title,
        url=fixture.url,
        source_type=ResearchSourceType.ACADEMIC,
        snippet=fixture.content,
        keywords=list(fixture.keywords),
    )
    document_record = InMemoryResearchDocumentRecord(
        source_id=source_record.source_id,
        url=source_record.url,
        content_type=ResearchSourceContentType.TEXT,
        content=fixture.content,
        language="en",
    )

    single_pipeline = build_single_pipeline(
        source_record=source_record,
        document_record=document_record,
    )
    single_started = time.perf_counter()
    single_result = single_pipeline.run(
        request,
        workspace_id=workspace_id,
    )
    single_elapsed = max(0.0, time.perf_counter() - single_started)

    deterministic_runtime = build_multi_runtime(
        request=request,
        workspace_id=workspace_id,
        fixture=fixture,
        source_record=source_record,
        document_record=document_record,
        reviewer_mode="deterministic",
        local_model=local_model,
        ollama_base_url=ollama_base_url,
        ollama_timeout_seconds=ollama_timeout_seconds,
    )
    deterministic_started = time.perf_counter()
    deterministic_result = run_multi(
        runtime=deterministic_runtime,
        request_id=request_id,
        workspace_id=workspace_id,
    )
    deterministic_elapsed = max(
        0.0,
        time.perf_counter() - deterministic_started,
    )
    deterministic_eval = MultiAgentWorkflowEvaluator().evaluate(
        deterministic_result
    )

    local_runtime = build_multi_runtime(
        request=request,
        workspace_id=workspace_id,
        fixture=fixture,
        source_record=source_record,
        document_record=document_record,
        reviewer_mode="local",
        local_model=local_model,
        ollama_base_url=ollama_base_url,
        ollama_timeout_seconds=ollama_timeout_seconds,
    )
    local_started = time.perf_counter()
    local_result = run_multi(
        runtime=local_runtime,
        request_id=request_id,
        workspace_id=workspace_id,
    )
    local_elapsed = max(0.0, time.perf_counter() - local_started)
    local_eval = MultiAgentWorkflowEvaluator().evaluate(local_result)

    deterministic_context = deterministic_runtime["context"]
    local_context = local_runtime["context"]

    single_vs_det = research_workspace_artifacts_equivalent(
        single_result.workspace,
        deterministic_context.workspace,
    )
    single_vs_local = research_workspace_artifacts_equivalent(
        single_result.workspace,
        local_context.workspace,
    )
    det_vs_local = research_workspace_artifacts_equivalent(
        deterministic_context.workspace,
        local_context.workspace,
    )

    normalizer = ResearchExecutionBenchmarkNormalizer()
    single_metrics = normalizer.single(
        result=single_result,
        wall_elapsed_seconds=single_elapsed,
    )
    deterministic_metrics = normalizer.multi(
        result=deterministic_result,
        wall_elapsed_seconds=deterministic_elapsed,
        workflow_evaluation=deterministic_eval,
    )
    local_metrics = normalizer.multi(
        result=local_result,
        wall_elapsed_seconds=local_elapsed,
        workflow_evaluation=local_eval,
    )

    return {
        "fixture_id": fixture.fixture_id,
        "repeat": repeat,
        "single": single_metrics.model_dump(mode="json"),
        "multi_deterministic": deterministic_metrics.model_dump(
            mode="json"
        ),
        "multi_local": local_metrics.model_dump(mode="json"),
        "single_wall_seconds": single_elapsed,
        "multi_deterministic_wall_seconds": deterministic_elapsed,
        "multi_local_wall_seconds": local_elapsed,
        "architecture_overhead_seconds": (
            deterministic_elapsed - single_elapsed
        ),
        "local_reviewer_overhead_seconds": (
            local_elapsed - deterministic_elapsed
        ),
        "single_vs_multi_deterministic_artifacts_equivalent": (
            single_vs_det
        ),
        "single_vs_multi_local_artifacts_equivalent": single_vs_local,
        "multi_deterministic_vs_local_artifacts_equivalent": det_vs_local,
        "all_upstream_artifacts_equivalent": (
            single_vs_det and single_vs_local and det_vs_local
        ),
        "deterministic_workflow_integrity_passed": (
            deterministic_eval.passed
        ),
        "local_workflow_integrity_passed": local_eval.passed,
        "deterministic_terminal_status": (
            deterministic_result.status.value
        ),
        "local_terminal_status": local_result.status.value,
    }


def aggregate(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        raise ValueError("rows must not be empty")

    single_times = [
        float(row["single_wall_seconds"]) for row in rows
    ]
    deterministic_times = [
        float(row["multi_deterministic_wall_seconds"]) for row in rows
    ]
    local_times = [
        float(row["multi_local_wall_seconds"]) for row in rows
    ]
    architecture_overhead = [
        float(row["architecture_overhead_seconds"]) for row in rows
    ]
    reviewer_overhead = [
        float(row["local_reviewer_overhead_seconds"]) for row in rows
    ]

    return {
        "triplet_count": len(rows),
        "artifact_equivalence_rate": mean(
            1.0
            if bool(row["all_upstream_artifacts_equivalent"])
            else 0.0
            for row in rows
        ),
        "deterministic_workflow_integrity_rate": mean(
            1.0
            if bool(row["deterministic_workflow_integrity_passed"])
            else 0.0
            for row in rows
        ),
        "local_workflow_integrity_rate": mean(
            1.0
            if bool(row["local_workflow_integrity_passed"])
            else 0.0
            for row in rows
        ),
        "wall_seconds": {
            "single_mean": mean(single_times),
            "single_median": median(single_times),
            "multi_deterministic_mean": mean(deterministic_times),
            "multi_deterministic_median": median(deterministic_times),
            "multi_local_mean": mean(local_times),
            "multi_local_median": median(local_times),
            "architecture_overhead_mean": mean(architecture_overhead),
            "architecture_overhead_median": median(architecture_overhead),
            "local_reviewer_overhead_mean": mean(reviewer_overhead),
            "local_reviewer_overhead_median": median(reviewer_overhead),
        },
        "mean_tool_calls": {
            "single": mean(
                _metric(row, "single", "tool_call_count")
                for row in rows
            ),
            "multi_deterministic": mean(
                _metric(row, "multi_deterministic", "tool_call_count")
                for row in rows
            ),
            "multi_local": mean(
                _metric(row, "multi_local", "tool_call_count")
                for row in rows
            ),
        },
        "mean_recorded_tokens": {
            "single": mean(
                _metric(row, "single", "recorded_token_count")
                for row in rows
            ),
            "multi_deterministic": mean(
                _metric(
                    row,
                    "multi_deterministic",
                    "recorded_token_count",
                )
                for row in rows
            ),
            "multi_local": mean(
                _metric(row, "multi_local", "recorded_token_count")
                for row in rows
            ),
        },
        "mean_execution_steps": {
            "single": mean(
                _metric(row, "single", "execution_step_count")
                for row in rows
            ),
            "multi_deterministic": mean(
                _metric(
                    row,
                    "multi_deterministic",
                    "execution_step_count",
                )
                for row in rows
            ),
            "multi_local": mean(
                _metric(row, "multi_local", "execution_step_count")
                for row in rows
            ),
        },
        "mean_participating_agents": {
            "single": mean(
                _metric(row, "single", "participating_agent_count")
                for row in rows
            ),
            "multi_deterministic": mean(
                _metric(
                    row,
                    "multi_deterministic",
                    "participating_agent_count",
                )
                for row in rows
            ),
            "multi_local": mean(
                _metric(
                    row,
                    "multi_local",
                    "participating_agent_count",
                )
                for row in rows
            ),
        },
        "semantic_repair_rate_local": mean(
            1.0
            if _metric(row, "multi_local", "semantic_repair_count") > 0
            else 0.0
            for row in rows
        ),
        "runtime_success_rate": {
            "single": mean(
                1.0
                if _metric_bool(row, "single", "runtime_succeeded")
                else 0.0
                for row in rows
            ),
            "multi_deterministic": mean(
                1.0
                if _metric_bool(
                    row,
                    "multi_deterministic",
                    "runtime_succeeded",
                )
                else 0.0
                for row in rows
            ),
            "multi_local": mean(
                1.0
                if _metric_bool(
                    row,
                    "multi_local",
                    "runtime_succeeded",
                )
                else 0.0
                for row in rows
            ),
        },
    }


def _metric(
    row: dict[str, object],
    group: str,
    field: str,
) -> float:
    payload = row[group]
    if not isinstance(payload, dict):
        raise TypeError(f"{group} payload must be a mapping")
    value = payload[field]
    if value is None:
        return 0.0
    return float(value)


def _metric_bool(
    row: dict[str, object],
    group: str,
    field: str,
) -> bool:
    payload = row[group]
    if not isinstance(payload, dict):
        raise TypeError(f"{group} payload must be a mapping")
    return bool(payload[field])


def build_single_pipeline(
    *,
    source_record: InMemoryResearchSourceRecord,
    document_record: InMemoryResearchDocumentRecord,
) -> SingleResearchAgentPipeline:
    return SingleResearchAgentPipeline(
        request_validator=ResearchRequestValidator(),
        task_decomposer=PipelineTaskDecomposerAdapter(),
        query_planner=PipelineQueryPlannerAdapter(),
        source_searcher=PipelineSourceSearchAdapter(
            InMemoryResearchSourceSearchTool(records=[source_record]),
            maximum_candidates=1,
        ),
        source_reader=PipelineSourceReaderAdapter(
            InMemoryResearchSourceReader(records=[document_record])
        ),
        evidence_extractor=PipelineEvidenceExtractorAdapter(
            WholeDocumentEvidenceExtractor()
        ),
        claim_builder=DeterministicPipelineClaimBuilder(),
        source_quality_evaluator=LocalDocumentSourceQualityEvaluator(),
        collect_run_metrics=True,
    )


def build_multi_runtime(
    *,
    request: ResearchRequest,
    workspace_id: str,
    fixture: BenchmarkFixture,
    source_record: InMemoryResearchSourceRecord,
    document_record: InMemoryResearchDocumentRecord,
    reviewer_mode: str,
    local_model: str,
    ollama_base_url: str,
    ollama_timeout_seconds: float,
) -> dict[str, object]:
    prefix = f"{request.request_id}-{reviewer_mode}"
    task = ResearchTask(
        task_id=f"{prefix}-task",
        request_id=request.request_id,
        title=f"Research {fixture.fixture_id}",
        question=request.question,
        objective=request.objective,
        completion_criteria=[
            "Produce one traceable evidence-backed claim.",
        ],
        expected_output="One traceable claim.",
    )
    graph = ResearchTaskGraph(
        request_id=request.request_id,
        tasks=[task],
    )
    queries = ResearchSearchQuerySet(
        request_id=request.request_id,
        task_graph=graph,
        queries=[
            ResearchSearchQuery(
                query_id=f"{prefix}-query",
                request_id=request.request_id,
                task_id=task.task_id,
                query_text=fixture.query_text,
                preferred_source_types=[
                    ResearchSourceType.ACADEMIC,
                ],
                maximum_results=1,
            )
        ],
    )
    context = MultiAgentResearchRuntimeContext(
        workspace=ResearchWorkspace(
            workspace_id=workspace_id,
            request=request,
            task_graph=graph,
            query_set=queries,
        )
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
            f"{prefix}-agent-search",
            ResearchAgentRole.SEARCH_SPECIALIST,
            ResearchAgentCapability.SEARCH_SOURCES,
        ),
        executor=PipelineResearchSearchExecutor(
            context=context,
            searcher=searcher,
        ),
        output_reference_id_factory=lambda: f"{prefix}-source-set",
    )
    reader_agent = SourceReaderSpecialistAgent(
        profile=profile(
            f"{prefix}-agent-reader",
            ResearchAgentRole.SOURCE_READER,
            ResearchAgentCapability.READ_SOURCES,
        ),
        executor=PipelineResearchSourceReaderExecutor(
            context=context,
            reader=reader,
        ),
        output_reference_id_factory=lambda: f"{prefix}-document-set",
    )
    evidence_agent = EvidenceAnalystAgent(
        profile=profile(
            f"{prefix}-agent-evidence",
            ResearchAgentRole.EVIDENCE_ANALYST,
            ResearchAgentCapability.EXTRACT_EVIDENCE,
        ),
        executor=PipelineResearchEvidenceExecutor(
            context=context,
            extractor=extractor,
        ),
        output_reference_id_factory=lambda: f"{prefix}-evidence-set",
    )
    claim_agent = ClaimAnalystAgent(
        profile=profile(
            f"{prefix}-agent-claim",
            ResearchAgentRole.CLAIM_ANALYST,
            ResearchAgentCapability.BUILD_CLAIMS,
        ),
        executor=PipelineResearchClaimExecutor(
            context=context,
            builder=builder,
        ),
        output_reference_id_factory=lambda: f"{prefix}-claim-set",
    )

    registry = InMemoryResearchReportRegistry()
    report_id = f"{prefix}-report"
    report_reference_id = f"{prefix}-report-output"
    synthesis_executor = RegisteredWorkspaceSynthesisExecutor(
        context=context,
        report_registry=registry,
        report_reference_id_factory=lambda: report_reference_id,
        report_id_factory=lambda: report_id,
    )
    synthesis_agent = SynthesisSpecialistAgent(
        profile=profile(
            f"{prefix}-agent-synthesis",
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
            ResearchAgentCapability.SYNTHESIZE_REPORT,
        ),
        executor=synthesis_executor,
        output_reference_id_factory=(
            synthesis_executor.take_output_reference_id
        ),
    )

    if reviewer_mode == "deterministic":
        review_executor = DeterministicApprovedQualityReviewExecutor(
            report_id=report_id
        )
    elif reviewer_mode == "local":
        review_executor = LocalResearchQualityReviewExecutor(
            client=OllamaClient(
                base_url=ollama_base_url,
                timeout_seconds=ollama_timeout_seconds,
            ),
            model=local_model,
            report_registry=registry,
        )
    else:
        raise ValueError(
            "reviewer_mode must be 'deterministic' or 'local'"
        )

    quality_agent = QualityReviewerAgent(
        profile=quality_profile(
            f"{prefix}-agent-quality"
        ),
        executor=review_executor,
        output_reference_id_factory=(
            lambda: f"{prefix}-quality-output"
        ),
    )
    loop = ReviewRevisionLoop(
        synthesis_agent=synthesis_agent,
        quality_reviewer=quality_agent,
        maximum_revision_rounds=0,
    )

    return {
        "context": context,
        "registry": registry,
        "orchestrator": MultiAgentResearchOrchestrator(
            search_agent=search_agent,
            source_reader_agent=reader_agent,
            evidence_analyst_agent=evidence_agent,
            claim_analyst_agent=claim_agent,
            review_revision_loop=loop,
        ),
        "prefix": prefix,
    }


def run_multi(
    *,
    runtime: dict[str, object],
    request_id: str,
    workspace_id: str,
):
    prefix = runtime["prefix"]
    if not isinstance(prefix, str):
        raise TypeError("runtime prefix must be a string")
    orchestrator = runtime["orchestrator"]

    return orchestrator.run(
        search_assignment=assignment(
            f"{prefix}-assignment-search",
            f"{prefix}-agent-search",
            ResearchAgentRole.SEARCH_SPECIALIST,
            request_id=request_id,
            workspace_id=workspace_id,
        ),
        source_reader_template=assignment(
            f"{prefix}-assignment-reader",
            f"{prefix}-agent-reader",
            ResearchAgentRole.SOURCE_READER,
            request_id=request_id,
            workspace_id=workspace_id,
        ),
        evidence_template=assignment(
            f"{prefix}-assignment-evidence",
            f"{prefix}-agent-evidence",
            ResearchAgentRole.EVIDENCE_ANALYST,
            request_id=request_id,
            workspace_id=workspace_id,
        ),
        claim_template=assignment(
            f"{prefix}-assignment-claim",
            f"{prefix}-agent-claim",
            ResearchAgentRole.CLAIM_ANALYST,
            request_id=request_id,
            workspace_id=workspace_id,
        ),
        synthesis_template=assignment(
            f"{prefix}-assignment-synthesis",
            f"{prefix}-agent-synthesis",
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
            request_id=request_id,
            workspace_id=workspace_id,
        ),
        review_template=assignment(
            f"{prefix}-assignment-review",
            f"{prefix}-agent-quality",
            ResearchAgentRole.QUALITY_REVIEWER,
            request_id=request_id,
            workspace_id=workspace_id,
        ),
    )


def identity(
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentIdentity:
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


def quality_profile(
    agent_id: str,
) -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id=f"profile-{agent_id}",
        agent=identity(
            agent_id,
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
        profile_id=f"profile-phase9b-manager-{role.value}",
        agent=identity(
            "phase9b-agent-manager",
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
        ResearchAgentRole.SEARCH_SPECIALIST: (
            ResearchAgentCapability.SEARCH_SOURCES
        ),
        ResearchAgentRole.SOURCE_READER: (
            ResearchAgentCapability.READ_SOURCES
        ),
        ResearchAgentRole.EVIDENCE_ANALYST: (
            ResearchAgentCapability.EXTRACT_EVIDENCE
        ),
        ResearchAgentRole.CLAIM_ANALYST: (
            ResearchAgentCapability.BUILD_CLAIMS
        ),
        ResearchAgentRole.SYNTHESIS_SPECIALIST: (
            ResearchAgentCapability.SYNTHESIZE_REPORT
        ),
        ResearchAgentRole.QUALITY_REVIEWER: (
            ResearchAgentCapability.EVALUATE_REPORT
        ),
    }[role]


def assignment(
    assignment_id: str,
    agent_id: str,
    role: ResearchAgentRole,
    *,
    request_id: str,
    workspace_id: str,
) -> ResearchAgentTaskAssignment:
    return ResearchAgentTaskAssignment(
        assignment_id=assignment_id,
        request_id=request_id,
        workspace_id=workspace_id,
        assigner_profile=manager_profile(role),
        assignee=identity(agent_id, role),
        required_role=role,
        required_capabilities=[required_capability(role)],
        title=f"Execute {role.value}",
        objective=f"Complete the {role.value} stage.",
        instructions=["Preserve traceable artifact handoffs."],
        expected_output_type=f"{role.value}_output",
        acceptance_criteria=[
            "Return one structured primary output.",
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )


if __name__ == "__main__":
    raise SystemExit(main())
