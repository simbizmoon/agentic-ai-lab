"""Run Phase 10C by reusing the validated Phase-7 frozen harness."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.research.hybrid_backend_comparison import summarize_phase10c


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture-result",
        action="append",
        type=Path,
        required=True,
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
        default=Path("/mnt/ai-data/experiments/phase10c"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = args.output_dir / f"{timestamp}_phase10c-hybrid-vs-openai"
    inherited = root / "phase7-frozen"
    inherited.mkdir(parents=True, exist_ok=False)

    command = [
        sys.executable,
        "scripts/run_phase7_frozen_worker_comparison.py",
    ]
    for path in args.fixture_result:
        command.extend(["--fixture-result", str(path)])
    command.extend(
        [
            "--repeats",
            str(args.repeats),
            "--local-model",
            args.local_model,
            "--ollama-base-url",
            args.ollama_base_url,
            "--ollama-timeout-seconds",
            str(args.ollama_timeout_seconds),
            "--openai-timeout-seconds",
            str(args.openai_timeout_seconds),
            "--output-dir",
            str(inherited),
        ]
    )

    completed = subprocess.run(
        command,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        return completed.returncode

    candidates = sorted(inherited.rglob("comparison.json"))
    if not candidates:
        raise RuntimeError("inherited Phase-7 comparison.json not found")

    source = candidates[-1]
    phase7_payload = json.loads(source.read_text(encoding="utf-8"))
    summary = summarize_phase10c(phase7_payload=phase7_payload)

    payload = {
        "benchmark": "phase10c-hybrid-vs-openai-heavy",
        "source_benchmark": str(source),
        "fixtures": [str(path) for path in args.fixture_result],
        "repeats": args.repeats,
        "local_model": args.local_model,
        "architectures": {
            "openai_heavy": {
                "evidence_relevance": "openai",
                "claim_generation": "openai",
                "semantic_citation": "openai",
                "claim_relevance": "openai",
                "answer_coverage": "openai",
            },
            "hybrid": {
                "evidence_relevance": "openai",
                "claim_generation": "openai",
                "semantic_citation": "local",
                "claim_relevance": "local",
                "answer_coverage": "local",
            },
            "local_heavy": {
                "distinct_safe_baseline": False,
                "reason": (
                    "No additional high-judgment local roles have been "
                    "validated; the safe local-heavy boundary equals Hybrid."
                ),
            },
        },
        "summary": summary.model_dump(mode="json"),
        "inherited_phase7_aggregate": phase7_payload.get("aggregate"),
        "inherited_failures": phase7_payload.get("failures", []),
    }

    output = root / "comparison.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"\nPhase 10C comparison: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
