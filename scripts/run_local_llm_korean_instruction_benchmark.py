"""Run Phase 5B-1 Korean instruction-following benchmark."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.evals.local_llm_benchmark import LocalLLMBenchmarkRequest
from app.evals.local_llm_benchmark_runner import LocalLLMBenchmarkRunner
from app.evals.local_llm_korean_instruction_benchmark import (
    KoreanInstructionBenchmarkCaseResult,
    summarize_korean_instruction_results,
)
from app.evals.local_llm_korean_instruction_dataset import (
    evaluate_korean_instruction_response,
    korean_instruction_cases,
)
from app.services.ollama_client import OllamaClient

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_REPETITIONS = 3
DEFAULT_KEEP_ALIVE = "5m"
DEFAULT_NUM_PREDICT = 256
DEFAULT_TEMPERATURE = 0.0
DEFAULT_SEED = 42
DEFAULT_RESULT_DIR = Path("evals/results/local_llm")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run Korean instruction-following benchmark.",
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
    """Return a filesystem-safe model name."""
    return "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-"
        for char in model.strip()
    )


def main() -> int:
    """Run all deterministic Korean instruction cases."""
    args = parse_args()

    if args.repetitions < 1:
        raise ValueError("repetitions must be at least 1")

    model = args.model.strip()
    if not model:
        raise ValueError("model must not be blank")

    cases = korean_instruction_cases()
    client = OllamaClient(timeout_seconds=120.0)
    runner = LocalLLMBenchmarkRunner(client=client)

    client.unload(model=model)

    scored_results: list[KoreanInstructionBenchmarkCaseResult] = []

    for case in cases:
        for repetition in range(1, args.repetitions + 1):
            run_label = (
                f"korean-{case.case_id}-r{repetition}"
            )
            benchmark_result = runner.run(
                LocalLLMBenchmarkRequest(
                    benchmark_id=f"phase5b1-{run_label}",
                    model=model,
                    prompt=case.prompt,
                    think=False,
                    run_label=run_label,
                    keep_alive=args.keep_alive,
                    num_predict=args.num_predict,
                    temperature=args.temperature,
                    seed=args.seed,
                    metadata={
                        "phase": "5B-1",
                        "category": "korean_instruction",
                        "case_id": case.case_id,
                        "case_name": case.name,
                        "repetition": str(repetition),
                    },
                )
            )

            score = evaluate_korean_instruction_response(
                case,
                benchmark_result.response,
            )
            scored = KoreanInstructionBenchmarkCaseResult(
                case_id=case.case_id,
                case_name=case.name,
                repetition=repetition,
                benchmark_result=benchmark_result,
                instruction_passed=(
                    benchmark_result.status.value == "succeeded"
                    and score.passed
                ),
                checks_passed=score.checks_passed,
                checks_total=score.checks_total,
                failures=score.failures,
            )
            scored_results.append(scored)

            print(
                f"{run_label}: "
                f"status={benchmark_result.status.value} "
                f"instruction_pass={scored.instruction_passed} "
                f"checks={scored.checks_passed}/{scored.checks_total} "
                f"total={benchmark_result.metrics.total_duration_ns / 1e9:.3f}s "
                f"eval_tokens={benchmark_result.metrics.eval_count} "
                f"response={benchmark_result.response!r}"
            )
            if scored.failures:
                print(
                    "  failures="
                    + " | ".join(scored.failures)
                )

    summary = summarize_korean_instruction_results(
        model=model,
        case_count=len(cases),
        results=scored_results,
    )

    created_at = datetime.now(UTC)
    payload = {
        "created_at": created_at.isoformat(),
        "benchmark_group": "phase5b1-korean-instruction",
        "model": model,
        "configuration": {
            "think": False,
            "repetitions": args.repetitions,
            "keep_alive": str(args.keep_alive),
            "num_predict": args.num_predict,
            "temperature": args.temperature,
            "seed": args.seed,
        },
        "summary": {
            "run_count": summary.run_count,
            "case_count": summary.case_count,
            "passed_runs": summary.passed_runs,
            "pass_rate": summary.pass_rate,
            "check_count": summary.check_count,
            "passed_checks": summary.passed_checks,
            "check_pass_rate": summary.check_pass_rate,
            "mean_total_duration_ms": summary.mean_total_duration_ms,
            "mean_eval_tokens": summary.mean_eval_tokens,
        },
        "results": [
            {
                "case_id": item.case_id,
                "case_name": item.case_name,
                "repetition": item.repetition,
                "instruction_passed": item.instruction_passed,
                "checks_passed": item.checks_passed,
                "checks_total": item.checks_total,
                "failures": list(item.failures),
                "response": item.benchmark_result.response,
                "thinking": item.benchmark_result.thinking,
                "status": item.benchmark_result.status.value,
                "done_reason": item.benchmark_result.done_reason,
                "failure_reason": item.benchmark_result.failure_reason,
                "metrics": item.benchmark_result.metrics.model_dump(
                    mode="json"
                ),
            }
            for item in scored_results
        ],
    }

    args.result_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        args.result_dir
        / (
            f"{created_at.strftime('%Y%m%dT%H%M%SZ')}_"
            f"{safe_model_name(model)}_"
            "phase5b1-korean-instruction.json"
        )
    )
    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"result_file={output_path}")
    print("=== SUMMARY ===")
    print(
        f"model={summary.model} "
        f"runs={summary.run_count} "
        f"cases={summary.case_count} "
        f"passed={summary.passed_runs} "
        f"pass_rate={summary.pass_rate:.3f} "
        f"checks={summary.passed_checks}/{summary.check_count} "
        f"check_pass_rate={summary.check_pass_rate:.3f} "
        f"mean_total_ms={summary.mean_total_duration_ms:.2f} "
        f"mean_eval_tokens={summary.mean_eval_tokens:.1f}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
