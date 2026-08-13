"""Run Phase 7C frozen-input OpenAI-vs-local worker comparison."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from app.budget import ExecutionBudget
from app.config import load_settings
from app.research.frozen_worker_backend_comparison import (
    build_local_workers,
    build_openai_workers,
    compare_frozen_pair,
    evaluate_frozen_input,
    load_frozen_input,
)
from app.research.local_worker_runtime import LocalWorkerSettings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture-result",
        action="append",
        type=Path,
        required=True,
        help="Persisted live result.json; repeat for multiple frozen cases.",
    )
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
        "--openai-timeout-seconds",
        type=float,
        default=120.0,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/mnt/ai-data/experiments/phase7-frozen"),
    )
    return parser.parse_args()


def aggregate(pairs: list[dict]) -> dict:
    if not pairs:
        raise ValueError("pairs must not be empty")

    agreement = [pair["agreement"] for pair in pairs]
    wall = [pair["wall_delta_local_minus_openai"] for pair in pairs]

    return {
        "pair_count": len(pairs),
        "mean_citation_exact_rate": mean(
            float(item["citation_exact_rate"])
            for item in agreement
        ),
        "mean_claim_relevance_exact_rate": mean(
            float(item["claim_relevance_exact_rate"])
            for item in agreement
        ),
        "answer_coverage_level_equal_rate": mean(
            1.0 if item["answer_coverage_level_equal"] else 0.0
            for item in agreement
        ),
        "mean_answer_coverage_score_delta_local_minus_openai": mean(
            float(
                item[
                    "answer_coverage_score_delta_local_minus_openai"
                ]
            )
            for item in agreement
        ),
        "mean_wall_delta_local_minus_openai": {
            stage: mean(
                float(item[stage])
                for item in wall
            )
            for stage in (
                "citation",
                "claim_relevance",
                "answer_coverage",
                "total",
            )
        },
    }


def main() -> int:
    args = parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")

    os.environ["OPENAI_TIMEOUT_SECONDS"] = str(
        args.openai_timeout_seconds
    )
    settings = load_settings()

    budget = ExecutionBudget(
        max_attempts=8,
        max_recorded_tokens=8_000,
        max_elapsed_seconds=60.0,
    )
    local_settings = LocalWorkerSettings(
        provider="local",
        model=args.local_model,
        ollama_base_url=args.ollama_base_url,
        ollama_timeout_seconds=args.ollama_timeout_seconds,
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = args.output_dir / f"{timestamp}_phase7c-frozen"
    root.mkdir(parents=True, exist_ok=False)

    pairs: list[dict] = []
    failures: list[dict] = []

    for fixture_index, fixture_path in enumerate(
        args.fixture_result,
        start=1,
    ):
        frozen = load_frozen_input(fixture_path)

        for repeat in range(1, args.repeats + 1):
            print(
                f"\n=== FIXTURE {fixture_index} "
                f"REPEAT {repeat}/{args.repeats}: OPENAI ==="
            )
            try:
                openai_run = evaluate_frozen_input(
                    provider="openai",
                    frozen=frozen,
                    workers=build_openai_workers(
                        settings=settings,
                        claim_relevance_budget=budget,
                    ),
                )

                print(
                    f"=== FIXTURE {fixture_index} "
                    f"REPEAT {repeat}/{args.repeats}: LOCAL ==="
                )
                local_run = evaluate_frozen_input(
                    provider="local",
                    frozen=frozen,
                    workers=build_local_workers(
                        settings=local_settings,
                        claim_relevance_budget=budget,
                    ),
                )

                pair = compare_frozen_pair(
                    openai_run=openai_run,
                    local_run=local_run,
                )
                pair["fixture_index"] = fixture_index
                pair["repeat"] = repeat
                pairs.append(pair)

                print(
                    "citation_agreement="
                    f"{pair['agreement']['citation_exact_rate']:.3f} "
                    "relevance_agreement="
                    f"{pair['agreement']['claim_relevance_exact_rate']:.3f} "
                    "coverage_equal="
                    f"{pair['agreement']['answer_coverage_level_equal']} "
                    "openai_wall="
                    f"{openai_run['wall_seconds']['total']:.3f}s "
                    "local_wall="
                    f"{local_run['wall_seconds']['total']:.3f}s"
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                failures.append(
                    {
                        "fixture_index": fixture_index,
                        "repeat": repeat,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                print(
                    f"FAILED: {type(exc).__name__}: {exc}"
                )

    result = {
        "benchmark": "phase7c-frozen-worker-backend-comparison",
        "fixture_results": [
            str(path) for path in args.fixture_result
        ],
        "repeats_per_fixture": args.repeats,
        "local_model": args.local_model,
        "openai_timeout_seconds": args.openai_timeout_seconds,
        "claim_relevance_budget": {
            "max_attempts": budget.max_attempts,
            "max_recorded_tokens": budget.max_recorded_tokens,
            "max_elapsed_seconds": budget.max_elapsed_seconds,
        },
        "successful_pairs": len(pairs),
        "failed_pairs": len(failures),
        "pairs": pairs,
        "aggregate": aggregate(pairs) if pairs else None,
        "failures": failures,
    }

    path = root / "comparison.json"
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nPhase 7C comparison: {path}")
    print(
        f"successful_pairs={len(pairs)} "
        f"failed_pairs={len(failures)}"
    )
    return 0 if pairs else 1


if __name__ == "__main__":
    raise SystemExit(main())
