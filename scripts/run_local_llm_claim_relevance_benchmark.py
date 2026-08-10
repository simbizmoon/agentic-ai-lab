"""Run Phase 5B-5 claim relevance benchmark on DEV and HOLDOUT v2."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.evals.claim_relevance_evaluation_runner import (
    ClaimRelevanceEvaluationRunner,
)
from app.evals.claim_relevance_golden_dataset_v2 import (
    build_claim_relevance_golden_dataset_v2,
)
from app.evals.claim_relevance_holdout_dataset_v2 import (
    build_claim_relevance_holdout_dataset_v2,
)
from app.research.local_claim_relevance_evaluator import (
    LocalClaimRelevanceEvaluator,
)
from app.services.ollama_client import OllamaClient

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_RESULT_DIR = Path("evals/results/local_llm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local LLM claim relevance benchmark."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--num-predict", type=int, default=256)
    parser.add_argument("--result-dir", type=Path, default=DEFAULT_RESULT_DIR)
    return parser.parse_args()


def run_dataset(
    *,
    dataset_name: str,
    evaluator: LocalClaimRelevanceEvaluator,
    model: str,
) -> dict[str, Any]:
    if dataset_name == "dev":
        dataset = build_claim_relevance_golden_dataset_v2()
    elif dataset_name == "holdout":
        dataset = build_claim_relevance_holdout_dataset_v2()
    else:
        raise ValueError(f"unsupported dataset name: {dataset_name}")

    runner = ClaimRelevanceEvaluationRunner(
        evaluator=evaluator,
        model=model,
    )
    result = runner.run(dataset=dataset)

    by_expected = Counter()
    by_expected_correct = Counter()

    for item in result.results:
        expected = item.expected_relevance_level.value
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
        f"false_direct={result.false_directly_relevant_count} "
        f"false_irrelevant={result.false_irrelevant_count}"
    )

    for item in result.results:
        status = "PASS" if item.correct else "FAIL"
        print(
            f"  {status} {item.case_id}: "
            f"expected={item.expected_relevance_level.value} "
            f"actual={item.actual_relevance_level.value} "
            f"score={item.relevance_score:.3f}"
        )

    return {
        "dataset_name": dataset_name,
        "dataset_id": result.dataset_id,
        "dataset_version": result.dataset_version,
        "case_count": result.case_count,
        "correct_count": result.correct_count,
        "accuracy": result.accuracy,
        "false_directly_relevant_count": (
            result.false_directly_relevant_count
        ),
        "false_irrelevant_count": result.false_irrelevant_count,
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
                "expected": item.expected_relevance_level.value,
                "actual": item.actual_relevance_level.value,
                "relevance_score": item.relevance_score,
                "correct": item.correct,
                "rationale": item.rationale,
                "issues": item.issues,
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

    evaluator = LocalClaimRelevanceEvaluator(
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
        "benchmark_group": "phase5b5-claim-relevance",
        "created_at": datetime.now(UTC).isoformat(),
        "model": model,
        "configuration": {
            "think": False,
            "temperature": 0.0,
            "seed": 42,
            "num_predict": args.num_predict,
            "response_format": "ClaimRelevanceJudgment JSON Schema",
        },
        "dev": dev,
        "holdout": holdout,
    }

    args.result_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_model = model.replace(":", "-")
    path = (
        args.result_dir
        / f"{stamp}_{safe_model}_phase5b5-claim-relevance.json"
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
            "false_direct": dev["false_directly_relevant_count"],
            "false_irrelevant": dev["false_irrelevant_count"],
        },
    )
    print(
        "holdout",
        {
            "correct": holdout["correct_count"],
            "total": holdout["case_count"],
            "accuracy": holdout["accuracy"],
            "false_direct": holdout["false_directly_relevant_count"],
            "false_irrelevant": holdout["false_irrelevant_count"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
