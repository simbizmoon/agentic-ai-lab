"""Run Phase 5B-4 AIRA-native research-planning benchmark."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.evals.local_llm_benchmark import LocalLLMBenchmarkRequest
from app.evals.local_llm_benchmark_runner import LocalLLMBenchmarkRunner
from app.evals.local_llm_research_planning_dataset import (
    query_draft_schema,
    query_planning_prompt,
    research_planning_cases,
    task_draft_schema,
    task_planning_prompt,
    validate_query_draft,
    validate_task_draft,
)
from app.research.research_task_decomposer import ResearchTaskDecomposer
from app.services.ollama_client import OllamaClient

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_REPETITIONS = 3
DEFAULT_RESULT_DIR = Path("evals/results/local_llm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local LLM research-planning benchmark.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument("--num-predict", type=int, default=1536)
    parser.add_argument("--result-dir", type=Path, default=DEFAULT_RESULT_DIR)
    return parser.parse_args()


def _result_row(
    *,
    case_id: str,
    repetition: int,
    stage: str,
    result: Any,
    score: Any,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "repetition": repetition,
        "stage": stage,
        "runtime_status": result.status.value,
        "done_reason": result.done_reason,
        "failure_reason": result.failure_reason,
        "schema_passed": score.schema_passed,
        "container_validation_passed": score.graph_or_query_set_passed,
        "checks_passed": score.checks_passed,
        "checks_total": score.checks_total,
        "passed": score.passed,
        "failures": list(score.failures),
        "response": result.response,
        "total_duration_ns": result.metrics.total_duration_ns,
        "eval_count": result.metrics.eval_count,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    run_count = len(rows)
    passed = sum(bool(row["passed"]) for row in rows)
    checks_total = sum(int(row["checks_total"]) for row in rows)
    checks_passed = sum(int(row["checks_passed"]) for row in rows)
    return {
        "run_count": run_count,
        "passed_count": passed,
        "pass_rate": passed / run_count,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "check_pass_rate": checks_passed / checks_total,
        "mean_total_duration_ms": (
            sum(int(row["total_duration_ns"]) for row in rows)
            / run_count
            / 1_000_000
        ),
        "mean_eval_tokens": (
            sum(int(row["eval_count"]) for row in rows) / run_count
        ),
    }


def main() -> int:
    args = parse_args()
    if args.repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    if args.num_predict < 1:
        raise ValueError("num_predict must be at least 1")

    model = args.model.strip()
    if not model:
        raise ValueError("model must not be blank")

    runner = LocalLLMBenchmarkRunner(
        client=OllamaClient(timeout_seconds=180.0)
    )

    task_rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []

    for case in research_planning_cases():
        baseline_graph = (
            ResearchTaskDecomposer()
            .decompose(case.request)
            .task_graph
        )

        for repetition in range(1, args.repetitions + 1):
            task_result = runner.run(
                LocalLLMBenchmarkRequest(
                    benchmark_id=(
                        f"phase5b4-task-{case.case_id}-r{repetition}"
                    ),
                    model=model,
                    prompt=task_planning_prompt(case),
                    think=False,
                    run_label=f"task-{case.case_id}-r{repetition}",
                    keep_alive="5m",
                    num_predict=args.num_predict,
                    temperature=0.0,
                    seed=42,
                    response_format=task_draft_schema(),
                    metadata={
                        "phase": "5B-4",
                        "stage": "task_decomposition",
                        "case_id": case.case_id,
                    },
                )
            )
            _, task_score = validate_task_draft(
                case=case,
                response=task_result.response,
            )
            task_rows.append(
                _result_row(
                    case_id=case.case_id,
                    repetition=repetition,
                    stage="task_decomposition",
                    result=task_result,
                    score=task_score,
                )
            )
            print(
                f"task-{case.case_id}-r{repetition}: "
                f"schema={task_score.schema_passed} "
                f"container={task_score.graph_or_query_set_passed} "
                f"checks={task_score.checks_passed}/"
                f"{task_score.checks_total} "
                f"pass={task_score.passed} "
                f"total={task_result.metrics.total_duration_ns / 1e9:.3f}s"
            )
            if task_score.failures:
                print(f"  failures={list(task_score.failures)!r}")

            query_result = runner.run(
                LocalLLMBenchmarkRequest(
                    benchmark_id=(
                        f"phase5b4-query-{case.case_id}-r{repetition}"
                    ),
                    model=model,
                    prompt=query_planning_prompt(
                        case,
                        baseline_graph,
                    ),
                    think=False,
                    run_label=f"query-{case.case_id}-r{repetition}",
                    keep_alive="5m",
                    num_predict=args.num_predict,
                    temperature=0.0,
                    seed=42,
                    response_format=query_draft_schema(),
                    metadata={
                        "phase": "5B-4",
                        "stage": "query_planning",
                        "case_id": case.case_id,
                    },
                )
            )
            query_score = validate_query_draft(
                case=case,
                graph=baseline_graph,
                response=query_result.response,
            )
            query_rows.append(
                _result_row(
                    case_id=case.case_id,
                    repetition=repetition,
                    stage="query_planning",
                    result=query_result,
                    score=query_score,
                )
            )
            print(
                f"query-{case.case_id}-r{repetition}: "
                f"schema={query_score.schema_passed} "
                f"container={query_score.graph_or_query_set_passed} "
                f"checks={query_score.checks_passed}/"
                f"{query_score.checks_total} "
                f"pass={query_score.passed} "
                f"total={query_result.metrics.total_duration_ns / 1e9:.3f}s"
            )
            if query_score.failures:
                print(f"  failures={list(query_score.failures)!r}")

    payload = {
        "benchmark_group": "phase5b4-research-planning",
        "created_at": datetime.now(UTC).isoformat(),
        "model": model,
        "configuration": {
            "think": False,
            "temperature": 0.0,
            "seed": 42,
            "num_predict": args.num_predict,
            "repetitions": args.repetitions,
            "task_cases": len(research_planning_cases()),
            "query_cases": len(research_planning_cases()),
        },
        "task_summary": summarize(task_rows),
        "query_summary": summarize(query_rows),
        "task_results": task_rows,
        "query_results": query_rows,
    }

    args.result_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_model = model.replace(":", "-")
    result_path = (
        args.result_dir
        / f"{stamp}_{safe_model}_phase5b4-research-planning.json"
    )
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"result_file={result_path}")
    print("=== SUMMARY ===")
    print("task", payload["task_summary"])
    print("query", payload["query_summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
