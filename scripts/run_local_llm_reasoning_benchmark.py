"""Run verified Phase 4A-3C Think OFF/ON reasoning benchmark."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from app.evals.local_llm_benchmark import LocalLLMBenchmarkRequest
from app.evals.local_llm_benchmark_artifact import (
    LocalLLMBenchmarkArtifact,
    LocalLLMBenchmarkArtifactWriter,
)
from app.evals.local_llm_benchmark_runner import LocalLLMBenchmarkRunner
from app.evals.local_llm_benchmark_summary import (
    summarize_local_llm_results,
)
from app.evals.local_llm_reasoning_dataset import (
    reasoning_cases,
    verify_reasoning_dataset,
)
from app.services.ollama_client import OllamaClient

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_REPETITIONS = 2
DEFAULT_KEEP_ALIVE = "5m"
DEFAULT_NUM_PREDICT = 1024
DEFAULT_TEMPERATURE = 0.0
DEFAULT_SEED = 42
DEFAULT_RESULT_DIR = Path("evals/results/local_llm")


def parse_args() -> argparse.Namespace:
    """Parse benchmark command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run verified AIRA local reasoning benchmark.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--repetitions",
        type=int,
        default=DEFAULT_REPETITIONS,
    )
    parser.add_argument(
        "--keep-alive",
        default=DEFAULT_KEEP_ALIVE,
    )
    parser.add_argument(
        "--num-predict",
        type=int,
        default=DEFAULT_NUM_PREDICT,
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
    )
    parser.add_argument(
        "--result-dir",
        type=Path,
        default=DEFAULT_RESULT_DIR,
    )
    return parser.parse_args()


def safe_model_name(model: str) -> str:
    """Return file-system-safe model label."""
    return "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-"
        for char in model.strip()
    )


def main() -> int:
    """Run all verified cases under Think OFF and Think ON."""
    args = parse_args()
    if args.repetitions < 1:
        raise ValueError("repetitions must be at least 1")

    cases = reasoning_cases()
    verified = verify_reasoning_dataset()
    for case in cases:
        if verified.get(case.case_id) != case.expected_answer:
            raise ValueError(
                f"dataset verification mismatch: {case.case_id}"
            )

    model = args.model.strip()
    if not model:
        raise ValueError("model must not be blank")

    client = OllamaClient(timeout_seconds=180.0)
    runner = LocalLLMBenchmarkRunner(client=client)
    all_results = []
    mode_results = {False: [], True: []}

    for think in (False, True):
        client.unload(model=model)
        mode_name = "think-on" if think else "think-off"

        for case in cases:
            for repetition in range(1, args.repetitions + 1):
                run_label = (
                    f"{mode_name}-{case.case_id}-r{repetition}"
                )
                result = runner.run(
                    LocalLLMBenchmarkRequest(
                        benchmark_id=f"phase4a3c-{run_label}",
                        model=model,
                        prompt=case.prompt,
                        think=think,
                        run_label=run_label,
                        keep_alive=args.keep_alive,
                        expected_answer=case.expected_answer,
                        num_predict=args.num_predict,
                        temperature=args.temperature,
                        seed=args.seed,
                        metadata={
                            "phase": "4A-3C",
                            "category": "verified_reasoning",
                            "case_id": case.case_id,
                            "case_name": case.name,
                            "repetition": str(repetition),
                        },
                    )
                )
                all_results.append(result)
                mode_results[think].append(result)

                print(
                    f"{run_label}: "
                    f"status={result.status.value} "
                    f"quality={result.quality_passed} "
                    f"parsed={result.parsed_answer!r} "
                    f"done={result.done_reason} "
                    f"total="
                    f"{result.metrics.total_duration_ns / 1e9:.3f}s "
                    f"eval_tokens={result.metrics.eval_count} "
                    f"response_chars={result.response_char_count} "
                    f"thinking_chars={result.thinking_char_count}"
                )

    summaries = [
        summarize_local_llm_results(mode_results[False]),
        summarize_local_llm_results(mode_results[True]),
    ]

    created_at = datetime.now(UTC)
    artifact = LocalLLMBenchmarkArtifact(
        created_at=created_at,
        model=model,
        benchmark_group="phase4a3c-verified-reasoning",
        results=all_results,
        summaries=summaries,
        metadata={
            "runtime": "ollama",
            "case_count": str(len(cases)),
            "repetitions_per_case": str(args.repetitions),
            "keep_alive": str(args.keep_alive),
            "num_predict": str(args.num_predict),
            "temperature": str(args.temperature),
            "seed": str(args.seed),
            "dataset_verified": "true",
        },
    )

    timestamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    output_path = (
        args.result_dir
        / (
            f"{timestamp}_{safe_model_name(model)}"
            "_phase4a3c-verified-reasoning.json"
        )
    )
    LocalLLMBenchmarkArtifactWriter().write(
        artifact=artifact,
        path=output_path,
    )

    print(f"result_file={output_path}")
    print("=== SUMMARY ===")
    for summary in summaries:
        print(
            f"think={str(summary.think).lower()} "
            f"runs={summary.run_count} "
            f"success={summary.success_count} "
            f"failures={summary.failure_count} "
            f"quality_pass={summary.quality_pass_count} "
            f"mean_total_ms={summary.mean_total_duration_ms:.2f} "
            f"median_total_ms={summary.median_total_duration_ms:.2f} "
            f"mean_gen_tps="
            f"{summary.mean_generation_tokens_per_second or 0:.2f} "
            f"mean_eval_tokens={summary.mean_eval_count:.1f} "
            f"mean_response_chars="
            f"{summary.mean_response_char_count:.1f} "
            f"mean_thinking_chars="
            f"{summary.mean_thinking_char_count:.1f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
