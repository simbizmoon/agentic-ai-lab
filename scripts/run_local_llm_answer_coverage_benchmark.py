"""Run Phase 5B-7 AIRA-native answer coverage benchmark."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.evals.answer_coverage_blind_holdout_dataset import (
    build_answer_coverage_blind_holdout_dataset,
)
from app.evals.answer_coverage_evaluation_runner import (
    AnswerCoverageEvaluationRunner,
)
from app.evals.answer_coverage_golden_dataset import (
    build_answer_coverage_golden_dataset,
)
from app.research.local_answer_coverage_evaluator import (
    LocalAnswerCoverageEvaluator,
)
from app.services.ollama_client import OllamaClient

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_RESULT_DIR = Path("evals/results/local_llm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local LLM answer coverage benchmark."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--num-predict", type=int, default=384)
    parser.add_argument("--result-dir", type=Path, default=DEFAULT_RESULT_DIR)
    return parser.parse_args()


def run_dataset(
    *,
    dataset_name: str,
    evaluator: LocalAnswerCoverageEvaluator,
    model: str,
) -> dict[str, Any]:
    if dataset_name == "dev":
        dataset = build_answer_coverage_golden_dataset()
    elif dataset_name == "holdout":
        dataset = build_answer_coverage_blind_holdout_dataset()
    else:
        raise ValueError(f"unsupported dataset name: {dataset_name}")

    runner = AnswerCoverageEvaluationRunner(
        evaluator=evaluator,
        model=model,
    )
    result = runner.run(dataset=dataset)

    by_expected = Counter()
    by_expected_correct = Counter()

    for item in result.results:
        expected = item.expected_coverage_level.value
        by_expected[expected] += 1
        if item.correct:
            by_expected_correct[expected] += 1

    per_class = {
        label: {
            "count": by_expected[label],
            "correct": by_expected_correct[label],
            "accuracy": (
                by_expected_correct[label] / by_expected[label]
                if by_expected[label]
                else 0.0
            ),
        }
        for label in sorted(by_expected)
    }

    print(
        f"{dataset_name}: "
        f"{result.correct_count}/{result.case_count} "
        f"accuracy={result.accuracy:.4f} "
        f"false_full={result.false_fully_covered_count} "
        f"false_insufficient={result.false_insufficient_count}"
    )

    for item in result.results:
        status = "PASS" if item.correct else "FAIL"
        print(
            f"  {status} {item.case_id}: "
            f"expected={item.expected_coverage_level.value} "
            f"actual={item.actual_coverage_level.value} "
            f"score={item.coverage_score:.3f}"
        )

    return {
        "dataset_name": dataset_name,
        "dataset_id": result.dataset_id,
        "dataset_version": result.dataset_version,
        "case_count": result.case_count,
        "correct_count": result.correct_count,
        "accuracy": result.accuracy,
        "false_fully_covered_count": (
            result.false_fully_covered_count
        ),
        "false_insufficient_count": result.false_insufficient_count,
        "per_class": per_class,
        "confusion": [
            {
                "expected": entry.expected.value,
                "actual": entry.actual.value,
                "count": entry.count,
            }
            for entry in result.confusion
        ],
        "results": [
            {
                "case_id": item.case_id,
                "expected": item.expected_coverage_level.value,
                "actual": item.actual_coverage_level.value,
                "coverage_score": item.coverage_score,
                "correct": item.correct,
                "covered_aspects": item.covered_aspects,
                "missing_aspects": item.missing_aspects,
                "rationale": item.rationale,
            }
            for item in result.results
        ],
    }


def main() -> int:
    args = parse_args()
    model = args.model.strip()

    if not model:
        raise ValueError("model must not be blank")
    if args.num_predict < 1:
        raise ValueError("num_predict must be at least 1")

    evaluator = LocalAnswerCoverageEvaluator(
        client=OllamaClient(timeout_seconds=120.0),
        model=model,
        num_predict=args.num_predict,
        temperature=0.0,
        seed=42,
    )

    dev = run_dataset(
        dataset_name="dev",
        evaluator=evaluator,
        model=model,
    )
    holdout = run_dataset(
        dataset_name="holdout",
        evaluator=evaluator,
        model=model,
    )

    payload = {
        "benchmark_group": "phase5b7-answer-coverage",
        "created_at": datetime.now(UTC).isoformat(),
        "model": model,
        "configuration": {
            "think": False,
            "temperature": 0.0,
            "seed": 42,
            "num_predict": args.num_predict,
            "response_format": "AnswerCoverageJudgment JSON Schema",
        },
        "dev": dev,
        "holdout": holdout,
    }

    args.result_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_model = model.replace(":", "-")
    path = (
        args.result_dir
        / f"{stamp}_{safe_model}_phase5b7-answer-coverage.json"
    )
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"result_file={path}")
    print("=== SUMMARY ===")
    print(
        "dev",
        {
            "correct": dev["correct_count"],
            "total": dev["case_count"],
            "accuracy": dev["accuracy"],
            "false_full": dev["false_fully_covered_count"],
            "false_insufficient": dev["false_insufficient_count"],
        },
    )
    print(
        "holdout",
        {
            "correct": holdout["correct_count"],
            "total": holdout["case_count"],
            "accuracy": holdout["accuracy"],
            "false_full": holdout["false_fully_covered_count"],
            "false_insufficient": holdout["false_insufficient_count"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
