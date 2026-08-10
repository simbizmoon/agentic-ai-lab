"""Run Phase 5B-2 structured-output benchmark."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.evals.local_llm_benchmark import LocalLLMBenchmarkRequest
from app.evals.local_llm_benchmark_runner import LocalLLMBenchmarkRunner
from app.evals.local_llm_structured_output_dataset import (
    StructuredOutputMode,
    evaluate_structured_output,
    response_format_for,
    structured_output_cases,
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
    parser = argparse.ArgumentParser(
        description="Run structured-output benchmark.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument("--keep-alive", default=DEFAULT_KEEP_ALIVE)
    parser.add_argument("--num-predict", type=int, default=DEFAULT_NUM_PREDICT)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--result-dir", type=Path, default=DEFAULT_RESULT_DIR)
    return parser.parse_args()


def safe_model_name(model: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-"
        for char in model.strip()
    )


def main() -> int:
    args = parse_args()
    if args.repetitions < 1:
        raise ValueError("repetitions must be at least 1")

    model = args.model.strip()
    if not model:
        raise ValueError("model must not be blank")

    client = OllamaClient(timeout_seconds=120.0)
    runner = LocalLLMBenchmarkRunner(client=client)
    cases = structured_output_cases()
    modes = tuple(StructuredOutputMode)

    client.unload(model=model)

    rows: list[dict[str, object]] = []

    for mode in modes:
        for case in cases:
            for repetition in range(1, args.repetitions + 1):
                response_format = response_format_for(case, mode)
                result = runner.run(
                    LocalLLMBenchmarkRequest(
                        benchmark_id=(
                            f"phase5b2-{mode.value}-"
                            f"{case.case_id}-r{repetition}"
                        ),
                        model=model,
                        prompt=case.prompt,
                        think=False,
                        run_label=(
                            f"{mode.value}-{case.case_id}-r{repetition}"
                        ),
                        keep_alive=args.keep_alive,
                        num_predict=args.num_predict,
                        temperature=args.temperature,
                        seed=args.seed,
                        response_format=response_format,
                        metadata={
                            "phase": "5B-2",
                            "category": "structured_output",
                            "mode": mode.value,
                            "case_id": case.case_id,
                            "repetition": str(repetition),
                        },
                    )
                )
                score = evaluate_structured_output(case, result.response)

                row = {
                    "mode": mode.value,
                    "case_id": case.case_id,
                    "repetition": repetition,
                    "runtime_status": result.status.value,
                    "json_parse_passed": score.json_parse_passed,
                    "schema_passed": score.schema_passed,
                    "exact_value_passed": score.exact_value_passed,
                    "failure": score.failure,
                    "response": result.response,
                    "done_reason": result.done_reason,
                    "failure_reason": result.failure_reason,
                    "metrics": result.metrics.model_dump(mode="json"),
                }
                rows.append(row)

                print(
                    f"{mode.value}-{case.case_id}-r{repetition}: "
                    f"status={result.status.value} "
                    f"json={score.json_parse_passed} "
                    f"schema={score.schema_passed} "
                    f"exact={score.exact_value_passed} "
                    f"total={result.metrics.total_duration_ns / 1e9:.3f}s "
                    f"eval_tokens={result.metrics.eval_count} "
                    f"response={result.response!r}"
                )
                if score.failure:
                    print(f"  failure={score.failure}")

    summaries: dict[str, dict[str, float | int]] = {}
    for mode in modes:
        subset = [row for row in rows if row["mode"] == mode.value]
        run_count = len(subset)
        summaries[mode.value] = {
            "run_count": run_count,
            "runtime_success_count": sum(
                row["runtime_status"] == "succeeded"
                for row in subset
            ),
            "json_parse_count": sum(
                bool(row["json_parse_passed"])
                for row in subset
            ),
            "schema_pass_count": sum(
                bool(row["schema_passed"])
                for row in subset
            ),
            "exact_value_pass_count": sum(
                bool(row["exact_value_passed"])
                for row in subset
            ),
            "exact_value_pass_rate": (
                sum(
                    bool(row["exact_value_passed"])
                    for row in subset
                )
                / run_count
            ),
            "mean_total_duration_ms": (
                sum(
                    int(row["metrics"]["total_duration_ns"])
                    for row in subset
                )
                / run_count
                / 1_000_000
            ),
            "mean_eval_tokens": (
                sum(
                    int(row["metrics"]["eval_count"])
                    for row in subset
                )
                / run_count
            ),
        }

    created_at = datetime.now(UTC)
    payload = {
        "created_at": created_at.isoformat(),
        "benchmark_group": "phase5b2-structured-output",
        "model": model,
        "configuration": {
            "think": False,
            "repetitions": args.repetitions,
            "keep_alive": str(args.keep_alive),
            "num_predict": args.num_predict,
            "temperature": args.temperature,
            "seed": args.seed,
        },
        "case_count": len(cases),
        "modes": [mode.value for mode in modes],
        "summaries": summaries,
        "results": rows,
    }

    args.result_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        args.result_dir
        / (
            f"{created_at.strftime('%Y%m%dT%H%M%SZ')}_"
            f"{safe_model_name(model)}_"
            "phase5b2-structured-output.json"
        )
    )
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"result_file={output_path}")
    print("=== SUMMARY ===")
    for mode in modes:
        print(mode.value, summaries[mode.value])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
