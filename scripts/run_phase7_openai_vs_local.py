"""Run repeated OpenAI-vs-local bounded-worker comparisons."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app.research.single_agent_backend_comparison import (
    aggregate_pairs,
    compare_pair,
    summarize_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--maximum-sources", type=int, default=1)
    parser.add_argument("--maximum-bytes", type=int, default=300000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/mnt/ai-data/experiments/phase7"),
    )
    parser.add_argument(
        "--local-model",
        default="qwen3.5:4b",
    )
    parser.add_argument(
        "--openai-timeout-seconds",
        type=float,
        default=120.0,
    )
    return parser.parse_args()


def newest_result(directory: Path) -> Path:
    results = sorted(directory.rglob("result.json"))
    if not results:
        raise RuntimeError(f"no result.json found under {directory}")
    return max(results, key=lambda path: path.stat().st_mtime_ns)


def run_research(
    *,
    provider: str,
    args: argparse.Namespace,
    output_dir: Path,
) -> tuple[Path, float]:
    env = os.environ.copy()
    env["AIRA_RESEARCH_WORKER_PROVIDER"] = provider
    env["OPENAI_TIMEOUT_SECONDS"] = str(
        args.openai_timeout_seconds
    )

    if provider == "local":
        env["AIRA_LOCAL_WORKER_MODEL"] = args.local_model
        env.setdefault(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        )
        env.setdefault("OLLAMA_TIMEOUT_SECONDS", "120")

    command = [
        "aira",
        "research-live",
        "--question",
        args.question,
        "--objective",
        args.objective,
        "--maximum-sources",
        str(args.maximum_sources),
        "--maximum-bytes",
        str(args.maximum_bytes),
        "--output-dir",
        str(output_dir),
    ]

    started = time.perf_counter()
    completed = subprocess.run(
        command,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    wall_seconds = max(0.0, time.perf_counter() - started)

    print(completed.stdout, end="")
    if completed.returncode != 0:
        raise RuntimeError(
            f"{provider} research-live failed with "
            f"exit code {completed.returncode}"
        )

    return newest_result(output_dir), wall_seconds


def main() -> int:
    args = parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = args.output_dir / f"{timestamp}_openai-vs-local"
    root.mkdir(parents=True, exist_ok=False)

    pairs = []
    failures = []

    for index in range(1, args.repeats + 1):
        print(f"\n=== PAIR {index}/{args.repeats}: OPENAI ===")
        openai_dir = root / f"pair-{index:02d}" / "openai"
        local_dir = root / f"pair-{index:02d}" / "local"

        try:
            openai_path, openai_wall = run_research(
                provider="openai",
                args=args,
                output_dir=openai_dir,
            )

            print(f"\n=== PAIR {index}/{args.repeats}: LOCAL ===")
            local_path, local_wall = run_research(
                provider="local",
                args=args,
                output_dir=local_dir,
            )

            openai_summary = summarize_result(
                provider="openai",
                result_path=openai_path,
            )
            local_summary = summarize_result(
                provider="local",
                result_path=local_path,
            )
            comparison = compare_pair(
                openai=openai_summary,
                local=local_summary,
            )
            comparison["pair_index"] = index
            comparison["wall_seconds"] = {
                "openai": openai_wall,
                "local": local_wall,
                "delta_local_minus_openai": (
                    local_wall - openai_wall
                ),
            }
            pairs.append(comparison)

        except (
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            failures.append(
                {
                    "pair_index": index,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            print(
                f"PAIR {index} FAILED: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    result = {
        "benchmark": "phase7-openai-vs-local-single-agent-workers",
        "question": args.question,
        "objective": args.objective,
        "maximum_sources": args.maximum_sources,
        "maximum_bytes": args.maximum_bytes,
        "requested_repeats": args.repeats,
        "successful_pairs": len(pairs),
        "failed_pairs": len(failures),
        "local_model": args.local_model,
        "openai_timeout_seconds": args.openai_timeout_seconds,
        "interpretation_scope": (
            "Same AIRA single-agent pipeline; bounded worker backend differs. "
            "Search and upstream OpenAI stages execute separately per run, so "
            "end-to-end deltas include external/upstream run variance."
        ),
        "pairs": pairs,
        "aggregate": aggregate_pairs(pairs) if pairs else None,
        "failures": failures,
    }

    result_path = root / "comparison.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nPhase 7 comparison: {result_path}")
    print(
        f"successful_pairs={len(pairs)} "
        f"failed_pairs={len(failures)}"
    )

    return 0 if pairs else 1


if __name__ == "__main__":
    raise SystemExit(main())
