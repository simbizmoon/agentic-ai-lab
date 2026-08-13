"""Architecture-level interpretation of frozen bounded-worker comparisons."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HybridArchitectureBenchmarkSummary(BaseModel):
    """Normalized Phase-10C architecture comparison summary."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    pair_count: int = Field(ge=1)
    artifact_scope: str
    openai_heavy_roles: tuple[str, ...]
    hybrid_openai_roles: tuple[str, ...]
    hybrid_local_roles: tuple[str, ...]
    local_heavy_distinct: bool
    citation_exact_agreement_rate: float = Field(ge=0, le=1)
    claim_relevance_exact_agreement_rate: float = Field(ge=0, le=1)
    answer_coverage_level_agreement_rate: float = Field(ge=0, le=1)
    answer_coverage_score_delta_hybrid_minus_openai: float
    worker_wall_delta_hybrid_minus_openai_seconds: float
    openai_worker_wall_mean_seconds: float
    hybrid_local_worker_wall_mean_seconds: float
    hybrid_wall_reduction_fraction: float
    hybrid_speedup_ratio: float
    interpretation: tuple[str, ...]
    limitations: tuple[str, ...]


def summarize_phase10c(
    *,
    phase7_payload: dict[str, object],
) -> HybridArchitectureBenchmarkSummary:
    """Map the validated Phase-7 frozen benchmark into Phase-10C terms."""

    aggregate = phase7_payload.get("aggregate")
    if not isinstance(aggregate, dict):
        raise TypeError("phase7 payload must contain aggregate metrics")

    pair_count = _number(aggregate, "pair_count")
    if pair_count < 1:
        raise ValueError("pair_count must be at least one")

    citation_rate = _number(
        aggregate,
        "mean_citation_exact_rate",
    )
    relevance_rate = _number(
        aggregate,
        "mean_claim_relevance_exact_rate",
    )
    coverage_level_rate = _number(
        aggregate,
        "answer_coverage_level_equal_rate",
    )
    coverage_delta = _number(
        aggregate,
        "mean_answer_coverage_score_delta_local_minus_openai",
    )

    wall = _wall_metrics(aggregate)
    total_delta = _number(
        wall,
        "total",
    )

    rows = phase7_payload.get("pairs")
    if not isinstance(rows, list) or not rows:
        raise ValueError("phase7 payload must contain successful pairs")

    openai_totals: list[float] = []
    local_totals: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("pair entries must be mappings")
        openai_total, local_total = _pair_totals(row)
        openai_totals.append(openai_total)
        local_totals.append(local_total)

    openai_mean = sum(openai_totals) / len(openai_totals)
    local_mean = sum(local_totals) / len(local_totals)
    reduction_fraction = (
        (openai_mean - local_mean) / openai_mean
        if openai_mean > 0
        else 0.0
    )
    speedup = (
        openai_mean / local_mean
        if local_mean > 0
        else 0.0
    )

    return HybridArchitectureBenchmarkSummary(
        pair_count=int(pair_count),
        artifact_scope=(
            "Frozen request/claim/citation inputs; only semantic citation, "
            "claim relevance, and answer coverage providers vary."
        ),
        openai_heavy_roles=(
            "evidence_relevance",
            "claim_generation",
            "semantic_citation",
            "claim_relevance",
            "answer_coverage",
        ),
        hybrid_openai_roles=(
            "evidence_relevance",
            "claim_generation",
        ),
        hybrid_local_roles=(
            "semantic_citation",
            "claim_relevance",
            "answer_coverage",
        ),
        local_heavy_distinct=False,
        citation_exact_agreement_rate=citation_rate,
        claim_relevance_exact_agreement_rate=relevance_rate,
        answer_coverage_level_agreement_rate=coverage_level_rate,
        answer_coverage_score_delta_hybrid_minus_openai=coverage_delta,
        worker_wall_delta_hybrid_minus_openai_seconds=total_delta,
        openai_worker_wall_mean_seconds=openai_mean,
        hybrid_local_worker_wall_mean_seconds=local_mean,
        hybrid_wall_reduction_fraction=reduction_fraction,
        hybrid_speedup_ratio=speedup,
        interpretation=(
            (
                "Hybrid preserves OpenAI for high-judgment evidence "
                "relevance and claim generation."
            ),
            (
                "Local qwen3.5:4b replaces only the three previously "
                "accepted bounded worker roles."
            ),
            (
                "Answer coverage remains advisory because prior frozen "
                "benchmarks showed optimistic local judgments."
            ),
        ),
        limitations=(
            (
                "This benchmark isolates bounded-worker substitution and "
                "does not measure full live-search end-to-end cost."
            ),
            (
                "The inherited frozen runner executes OpenAI before Local, "
                "so warm-runtime ordering remains a latency limitation."
            ),
            (
                "Embedding-provider usage is outside these bounded-worker "
                "metrics."
            ),
            (
                "Local-heavy is not a distinct safe baseline because no "
                "additional high-judgment local roles have been validated."
            ),
        ),
    )


def _wall_metrics(
    aggregate: dict[str, object],
) -> dict[str, object]:
    direct = aggregate.get("mean_wall_delta_local_minus_openai")
    if isinstance(direct, dict):
        return direct

    legacy = aggregate.get(
        "mean_wall_seconds_delta_local_minus_openai"
    )
    if isinstance(legacy, dict):
        return legacy

    raise ValueError(
        "aggregate does not expose mean worker wall-time deltas"
    )


def _pair_totals(row: dict[str, object]) -> tuple[float, float]:
    openai = row.get("openai")
    local = row.get("local")
    if not isinstance(openai, dict) or not isinstance(local, dict):
        raise TypeError("pair must contain openai and local mappings")

    return (
        _provider_total(openai),
        _provider_total(local),
    )


def _provider_total(payload: dict[str, object]) -> float:
    wall_seconds = payload.get("wall_seconds")
    if isinstance(wall_seconds, dict):
        total = wall_seconds.get("total")
        if isinstance(total, (int, float)) and not isinstance(total, bool):
            return float(total)

    for key in (
        "total_wall_seconds",
        "worker_wall_seconds",
        "wall_elapsed_seconds",
        "total_elapsed_seconds",
    ):
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)

    raise ValueError("provider payload does not expose worker wall time")


def _number(
    payload: dict[str, object],
    key: str,
) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{key} must be numeric")
    return float(value)
