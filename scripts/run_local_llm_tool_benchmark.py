"""Run Phase 5B-3 AIRA-native tool selection and calling benchmark."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.evals.local_llm_benchmark import LocalLLMBenchmarkRequest
from app.evals.local_llm_benchmark_runner import LocalLLMBenchmarkRunner
from app.evals.local_llm_tool_benchmark_dataset import (
    ToolSelectionOutput,
    local_llm_tool_benchmark_cases,
    ollama_tool_schemas,
    tool_selection_prompt,
)
from app.services.ollama_client import OllamaClient
from app.services.ollama_tool_client import OllamaToolClient
from app.tools.tool_dispatcher import ToolDispatchError, dispatch_tool_call

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_REPETITIONS = 3
DEFAULT_RESULT_DIR = Path("evals/results/local_llm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AIRA-native local LLM tool benchmark.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--repetitions",
        type=int,
        default=DEFAULT_REPETITIONS,
    )
    parser.add_argument(
        "--result-dir",
        type=Path,
        default=DEFAULT_RESULT_DIR,
    )
    return parser.parse_args()


def selection_schema() -> dict[str, Any]:
    return ToolSelectionOutput.model_json_schema()


def run_selection(
    *,
    model: str,
    repetitions: int,
) -> list[dict[str, Any]]:
    client = OllamaClient(timeout_seconds=120.0)
    runner = LocalLLMBenchmarkRunner(client=client)
    rows: list[dict[str, Any]] = []

    for case in local_llm_tool_benchmark_cases():
        for repetition in range(1, repetitions + 1):
            result = runner.run(
                LocalLLMBenchmarkRequest(
                    benchmark_id=(
                        f"phase5b3a-{case.case_id}-r{repetition}"
                    ),
                    model=model,
                    prompt=tool_selection_prompt(case.user_request),
                    think=False,
                    run_label=(
                        f"selection-{case.case_id}-r{repetition}"
                    ),
                    keep_alive="5m",
                    num_predict=128,
                    temperature=0.0,
                    seed=42,
                    response_format=selection_schema(),
                    metadata={
                        "phase": "5B-3a",
                        "case_id": case.case_id,
                    },
                )
            )

            parsed_tool_name: str | None = None
            schema_passed = False
            try:
                parsed = ToolSelectionOutput.model_validate_json(
                    result.response
                )
                parsed_tool_name = parsed.tool_name
                schema_passed = True
            except ValidationError:
                schema_passed = False

            selection_passed = (
                schema_passed
                and parsed_tool_name == case.expected_tool_name
            )
            rows.append(
                {
                    "case_id": case.case_id,
                    "repetition": repetition,
                    "expected_tool_name": case.expected_tool_name,
                    "actual_tool_name": parsed_tool_name,
                    "runtime_status": result.status.value,
                    "schema_passed": schema_passed,
                    "selection_passed": selection_passed,
                    "response": result.response,
                    "total_duration_ns": (
                        result.metrics.total_duration_ns
                    ),
                    "eval_count": result.metrics.eval_count,
                }
            )
            print(
                f"selection-{case.case_id}-r{repetition}: "
                f"expected={case.expected_tool_name!r} "
                f"actual={parsed_tool_name!r} "
                f"pass={selection_passed} "
                f"total={result.metrics.total_duration_ns / 1e9:.3f}s"
            )

    return rows


def run_native_calling(
    *,
    model: str,
    repetitions: int,
) -> list[dict[str, Any]]:
    client = OllamaToolClient(timeout_seconds=120.0)
    tools = ollama_tool_schemas()
    rows: list[dict[str, Any]] = []

    for case in local_llm_tool_benchmark_cases():
        for repetition in range(1, repetitions + 1):
            response = client.chat(
                model=model,
                user_request=case.user_request,
                tools=tools,
                think=False,
                keep_alive="5m",
                temperature=0.0,
                seed=42,
            )

            call_count = len(response.tool_calls)
            all_tool_calls = [
                {
                    "name": call.name,
                    "arguments": call.arguments,
                }
                for call in response.tool_calls
            ]
            actual_tool_name: str | None = None
            actual_arguments: dict[str, Any] | None = None
            dispatch_passed: bool | None = None
            dispatch_error: str | None = None

            if call_count == 1:
                call = response.tool_calls[0]
                actual_tool_name = call.name
                actual_arguments = call.arguments
                try:
                    dispatch_tool_call(
                        tool_name=call.name,
                        arguments_json=json.dumps(
                            call.arguments,
                            ensure_ascii=False,
                        ),
                    )
                    dispatch_passed = True
                except ToolDispatchError as error:
                    dispatch_passed = False
                    dispatch_error = error.code.value

            expected_none = case.expected_tool_name is None
            selection_passed = (
                call_count == 0
                if expected_none
                else (
                    call_count == 1
                    and actual_tool_name == case.expected_tool_name
                )
            )

            arguments_passed = (
                call_count == 0
                if expected_none
                else (
                    actual_arguments == case.expected_arguments
                )
            )

            native_passed = (
                selection_passed
                and arguments_passed
                and (
                    expected_none
                    or dispatch_passed is True
                )
            )

            rows.append(
                {
                    "case_id": case.case_id,
                    "repetition": repetition,
                    "expected_tool_name": case.expected_tool_name,
                    "actual_tool_name": actual_tool_name,
                    "expected_arguments": case.expected_arguments,
                    "actual_arguments": actual_arguments,
                    "all_tool_calls": all_tool_calls,
                    "tool_call_count": call_count,
                    "selection_passed": selection_passed,
                    "arguments_passed": arguments_passed,
                    "dispatch_passed": dispatch_passed,
                    "dispatch_error": dispatch_error,
                    "native_passed": native_passed,
                    "content": response.content,
                    "thinking_chars": len(response.thinking),
                    "total_duration_ns": response.total_duration_ns,
                    "eval_count": response.eval_count,
                }
            )

            print(
                f"native-{case.case_id}-r{repetition}: "
                f"calls={call_count} "
                f"expected={case.expected_tool_name!r} "
                f"actual={actual_tool_name!r} "
                f"args={arguments_passed} "
                f"dispatch={dispatch_passed} "
                f"pass={native_passed} "
                f"total={response.total_duration_seconds:.3f}s"
            )
            if actual_arguments is not None:
                print(f"  arguments={actual_arguments!r}")
            if response.content:
                print(f"  content={response.content!r}")

    return rows


def summarize(rows: list[dict[str, Any]], pass_key: str) -> dict[str, Any]:
    count = len(rows)
    passed = sum(bool(row[pass_key]) for row in rows)
    return {
        "run_count": count,
        "passed_count": passed,
        "pass_rate": passed / count,
        "mean_total_duration_ms": (
            sum(int(row["total_duration_ns"]) for row in rows)
            / count
            / 1_000_000
        ),
        "mean_eval_tokens": (
            sum(int(row["eval_count"]) for row in rows)
            / count
        ),
    }


def main() -> int:
    args = parse_args()
    if args.repetitions < 1:
        raise ValueError("repetitions must be at least 1")

    model = args.model.strip()
    if not model:
        raise ValueError("model must not be blank")

    selection_rows = run_selection(
        model=model,
        repetitions=args.repetitions,
    )
    native_rows = run_native_calling(
        model=model,
        repetitions=args.repetitions,
    )

    payload = {
        "benchmark_group": "phase5b3-tool-selection-calling",
        "created_at": datetime.now(UTC).isoformat(),
        "model": model,
        "configuration": {
            "think": False,
            "temperature": 0.0,
            "seed": 42,
            "repetitions": args.repetitions,
        },
        "selection_summary": summarize(
            selection_rows,
            "selection_passed",
        ),
        "native_summary": summarize(
            native_rows,
            "native_passed",
        ),
        "selection_results": selection_rows,
        "native_results": native_rows,
    }

    args.result_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_model = model.replace(":", "-")
    path = (
        args.result_dir
        / f"{stamp}_{safe_model}_phase5b3-tool-selection-calling.json"
    )
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"result_file={path}")
    print("=== SUMMARY ===")
    print("selection", payload["selection_summary"])
    print("native", payload["native_summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
