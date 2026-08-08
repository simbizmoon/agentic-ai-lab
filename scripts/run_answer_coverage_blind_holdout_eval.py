"""Run the fresh semantic answer coverage blind holdout evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openai import OpenAI

from app.evals.answer_coverage_blind_holdout_dataset import (
    build_answer_coverage_blind_holdout_dataset,
)
from app.evals.answer_coverage_evaluation_runner import (
    AnswerCoverageEvaluationRunner,
)
from app.research.openai_answer_coverage_evaluator import (
    OpenAIAnswerCoverageEvaluator,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the answer coverage blind holdout evaluation."
    )
    parser.add_argument(
        "--model",
        required=True,
        help="OpenAI model identifier to evaluate.",
    )
    parser.add_argument(
        "--output",
        default="reports/answer_coverage_blind_holdout_v1.json",
        help="JSON output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    client = OpenAI()
    evaluator = OpenAIAnswerCoverageEvaluator(
        client=client,
        model=args.model,
    )
    runner = AnswerCoverageEvaluationRunner(
        evaluator=evaluator,
        model=args.model,
    )
    dataset = build_answer_coverage_blind_holdout_dataset()
    result = runner.run(dataset=dataset)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"dataset={result.dataset_id} "
        f"version={result.dataset_version}"
    )
    print(
        f"accuracy={result.correct_count}/{result.case_count} "
        f"({result.accuracy:.2%})"
    )
    print(
        "false_fully_covered="
        f"{result.false_fully_covered_count}"
    )
    print(
        "false_insufficient="
        f"{result.false_insufficient_count}"
    )
    print("confusion:")
    for entry in result.confusion:
        print(
            f"  expected={entry.expected.value} "
            f"actual={entry.actual.value} "
            f"count={entry.count}"
        )
    print(f"result={output_path}")


if __name__ == "__main__":
    main()
