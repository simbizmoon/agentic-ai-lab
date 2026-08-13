"""Compare two single-agent research runs that differ by worker backend."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

WORKER_STAGE_NAMES = (
    "round_1_citation_verification",
    "round_1_claim_relevance",
    "round_1_answer_coverage",
    "coverage_citation_verification",
    "coverage_claim_relevance",
    "coverage_answer_coverage",
)


@dataclass(frozen=True)
class WorkerStageSummary:
    """Aggregate bounded-worker metrics from one research result."""

    call_count: int
    recorded_tokens: int
    elapsed_seconds: float


@dataclass(frozen=True)
class ResearchBackendRunSummary:
    """Normalized fields used for Phase 7 backend comparison."""

    provider: str
    result_path: str
    quality_score: float
    quality_level: str
    quality_passed: bool
    claim_count: int
    citation_count: int
    source_count: int
    evidence_count: int
    total_elapsed_seconds: float
    llm_call_count: int
    recorded_tokens: int
    worker_metrics: WorkerStageSummary
    citation_decisions: dict[str, int]
    citation_support_levels: dict[str, int]
    claim_relevance_levels: dict[str, int]
    answer_coverage_level: str | None
    answer_coverage_score: float | None
    ollama_provenance_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "result_path": self.result_path,
            "quality_score": self.quality_score,
            "quality_level": self.quality_level,
            "quality_passed": self.quality_passed,
            "claim_count": self.claim_count,
            "citation_count": self.citation_count,
            "source_count": self.source_count,
            "evidence_count": self.evidence_count,
            "total_elapsed_seconds": self.total_elapsed_seconds,
            "llm_call_count": self.llm_call_count,
            "recorded_tokens": self.recorded_tokens,
            "worker_metrics": {
                "call_count": self.worker_metrics.call_count,
                "recorded_tokens": self.worker_metrics.recorded_tokens,
                "elapsed_seconds": self.worker_metrics.elapsed_seconds,
            },
            "citation_decisions": self.citation_decisions,
            "citation_support_levels": self.citation_support_levels,
            "claim_relevance_levels": self.claim_relevance_levels,
            "answer_coverage_level": self.answer_coverage_level,
            "answer_coverage_score": self.answer_coverage_score,
            "ollama_provenance_count": self.ollama_provenance_count,
        }


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("result JSON must contain an object")
    return data


def _stage_metrics(run_metrics: dict[str, Any]) -> WorkerStageSummary:
    calls = 0
    tokens = 0
    elapsed = 0.0

    for name in WORKER_STAGE_NAMES:
        stage = run_metrics.get(name) or {}
        if not isinstance(stage, dict):
            continue
        calls += int(stage.get("call_count", 0))
        tokens += int(stage.get("recorded_tokens", 0))
        elapsed += float(stage.get("elapsed_seconds", 0.0))

    return WorkerStageSummary(
        call_count=calls,
        recorded_tokens=tokens,
        elapsed_seconds=elapsed,
    )


def summarize_result(
    *,
    provider: str,
    result_path: Path,
) -> ResearchBackendRunSummary:
    """Normalize one persisted research result."""
    provider_name = provider.strip().casefold()
    if provider_name not in {"openai", "local"}:
        raise ValueError("provider must be 'openai' or 'local'")

    data = _load_json(result_path)
    workspace = data.get("workspace") or {}
    quality = data.get("quality") or {}
    run_metrics = data.get("run_metrics") or {}

    if not isinstance(workspace, dict):
        raise TypeError("workspace must be an object")
    if not isinstance(quality, dict):
        raise TypeError("quality must be an object")
    if not isinstance(run_metrics, dict):
        raise TypeError("run_metrics must be an object")

    document_set = workspace.get("document_set") or {}
    evidence_set = workspace.get("evidence_set") or {}
    claim_set = workspace.get("claim_set") or {}

    documents = (
        document_set.get("documents", [])
        if isinstance(document_set, dict)
        else []
    )
    evidence = (
        evidence_set.get("evidence", [])
        if isinstance(evidence_set, dict)
        else []
    )
    claims = (
        claim_set.get("claims", [])
        if isinstance(claim_set, dict)
        else []
    )

    citation_verifications = data.get("citation_verifications") or []
    claim_relevance = data.get("claim_relevance_evaluations") or []
    answer_coverage = data.get("answer_coverage_evaluation")

    decision_counts = Counter(
        item.get("decision")
        for item in citation_verifications
        if isinstance(item, dict) and item.get("decision")
    )
    support_counts = Counter(
        item.get("support_level")
        for item in citation_verifications
        if isinstance(item, dict) and item.get("support_level")
    )
    relevance_counts = Counter(
        item.get("relevance_level")
        for item in claim_relevance
        if isinstance(item, dict) and item.get("relevance_level")
    )

    citation_count = 0
    for claim in claims:
        if isinstance(claim, dict):
            citations = claim.get("citations") or []
            citation_count += len(citations)

    serialized = json.dumps(data, ensure_ascii=False)
    answer_level = None
    answer_score = None
    if isinstance(answer_coverage, dict):
        raw_level = answer_coverage.get("coverage_level")
        raw_score = answer_coverage.get("coverage_score")
        answer_level = str(raw_level) if raw_level is not None else None
        answer_score = float(raw_score) if raw_score is not None else None

    llm_stages = [
        value
        for key, value in run_metrics.items()
        if isinstance(value, dict)
        and "call_count" in value
        and key not in {
            "search_provider_calls",
        }
    ]

    return ResearchBackendRunSummary(
        provider=provider_name,
        result_path=str(result_path),
        quality_score=float(quality.get("overall_score", 0.0)),
        quality_level=str(quality.get("quality_level", "")),
        quality_passed=bool(quality.get("passed", False)),
        claim_count=len(claims),
        citation_count=citation_count,
        source_count=len(documents),
        evidence_count=len(evidence),
        total_elapsed_seconds=float(
            run_metrics.get("total_elapsed_seconds", 0.0)
        ),
        llm_call_count=sum(
            int(stage.get("call_count", 0))
            for stage in llm_stages
        ),
        recorded_tokens=sum(
            int(stage.get("recorded_tokens", 0))
            for stage in llm_stages
        ),
        worker_metrics=_stage_metrics(run_metrics),
        citation_decisions=dict(sorted(decision_counts.items())),
        citation_support_levels=dict(sorted(support_counts.items())),
        claim_relevance_levels=dict(sorted(relevance_counts.items())),
        answer_coverage_level=answer_level,
        answer_coverage_score=answer_score,
        ollama_provenance_count=serialized.count("ollama-local"),
    )


def compare_pair(
    *,
    openai: ResearchBackendRunSummary,
    local: ResearchBackendRunSummary,
) -> dict[str, Any]:
    """Compare one OpenAI/local pair without inventing a winner."""
    if openai.provider != "openai":
        raise ValueError("openai summary must use provider='openai'")
    if local.provider != "local":
        raise ValueError("local summary must use provider='local'")

    return {
        "openai": openai.as_dict(),
        "local": local.as_dict(),
        "delta_local_minus_openai": {
            "quality_score": local.quality_score - openai.quality_score,
            "total_elapsed_seconds": (
                local.total_elapsed_seconds
                - openai.total_elapsed_seconds
            ),
            "llm_call_count": local.llm_call_count - openai.llm_call_count,
            "recorded_tokens": (
                local.recorded_tokens - openai.recorded_tokens
            ),
            "worker_elapsed_seconds": (
                local.worker_metrics.elapsed_seconds
                - openai.worker_metrics.elapsed_seconds
            ),
            "worker_recorded_tokens": (
                local.worker_metrics.recorded_tokens
                - openai.worker_metrics.recorded_tokens
            ),
            "claim_count": local.claim_count - openai.claim_count,
            "citation_count": (
                local.citation_count - openai.citation_count
            ),
            "source_count": local.source_count - openai.source_count,
            "evidence_count": (
                local.evidence_count - openai.evidence_count
            ),
        },
    }


def aggregate_pairs(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate repeated paired runs."""
    if not pairs:
        raise ValueError("pairs must not be empty")

    metrics = (
        "quality_score",
        "total_elapsed_seconds",
        "llm_call_count",
        "recorded_tokens",
        "worker_elapsed_seconds",
        "worker_recorded_tokens",
        "claim_count",
        "citation_count",
        "source_count",
        "evidence_count",
    )

    return {
        "pair_count": len(pairs),
        "mean_delta_local_minus_openai": {
            metric: mean(
                float(pair["delta_local_minus_openai"][metric])
                for pair in pairs
            )
            for metric in metrics
        },
    }
