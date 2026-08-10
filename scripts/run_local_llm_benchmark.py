"""Run the Phase 4A-2 cold/warm local LLM benchmark."""

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
from app.services.ollama_client import OllamaClient

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_PROMPT = (
    "한국어로만 답하라. 로컬 LLM을 AIRA의 Worker Agent로 사용할 때 "
    "장점 두 가지를 정확히 두 문장으로 설명하라."
)
DEFAULT_RESULT_DIR = Path("evals/results/local_llm")


def parse_args() -> argparse.Namespace:
    """Parse benchmark CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run AIRA local LLM cold/warm benchmark.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument(
        "--think",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--keep-alive",
        default="5m",
        help="Ollama keep_alive value used for benchmark calls.",
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
    """Run cold and warm calls and persist one JSON artifact."""
    args = parse_args()
    model = args.model.strip()
    prompt = args.prompt.strip()

    if not model:
        raise ValueError("model must not be blank")
    if not prompt:
        raise ValueError("prompt must not be blank")

    client = OllamaClient()
    runner = LocalLLMBenchmarkRunner(client=client)

    client.unload(model=model)

    common_metadata = {
        "phase": "4A-2",
        "category": "runtime_cold_warm",
    }

    cold = runner.run(
        LocalLLMBenchmarkRequest(
            benchmark_id="phase4a2-cold",
            model=model,
            prompt=prompt,
            think=args.think,
            run_label="cold",
            keep_alive=args.keep_alive,
            metadata=common_metadata,
        )
    )

    warm = runner.run(
        LocalLLMBenchmarkRequest(
            benchmark_id="phase4a2-warm",
            model=model,
            prompt=prompt,
            think=args.think,
            run_label="warm",
            keep_alive=args.keep_alive,
            metadata=common_metadata,
        )
    )

    created_at = datetime.now(UTC)
    artifact = LocalLLMBenchmarkArtifact(
        created_at=created_at,
        model=model,
        benchmark_group="phase4a2-cold-warm",
        results=[cold, warm],
        metadata={
            "runtime": "ollama",
            "think": str(args.think).lower(),
            "keep_alive": str(args.keep_alive),
        },
    )

    timestamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    output_path = (
        args.result_dir
        / (
            f"{timestamp}_{safe_model_name(model)}"
            f"_think-{str(args.think).lower()}.json"
        )
    )
    LocalLLMBenchmarkArtifactWriter().write(
        artifact=artifact,
        path=output_path,
    )

    print(f"result_file={output_path}")
    for result in artifact.results:
        metrics = result.metrics
        print(
            f"{result.run_label}: "
            f"total={metrics.total_duration_ns / 1e9:.3f}s "
            f"load={metrics.load_duration_ns / 1e9:.3f}s "
            f"prompt_tps={metrics.prompt_tokens_per_second or 0:.2f} "
            f"generation_tps="
            f"{metrics.generation_tokens_per_second or 0:.2f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
