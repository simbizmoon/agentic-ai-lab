"""Benchmark real HTTP source reading at bounded concurrency levels."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

from app.research.http_html_research_source_reader import (
    HttpHtmlResearchSourceReader,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceReaderAdapter,
)
from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)

URLS = [
    "https://humanloop.com/blog/openai-agents-sdk",
    "https://mem0.ai/blog/openai-agents-sdk-review",
    (
        "https://techcrunch.com/2026/04/15/"
        "openai-updates-its-agents-sdk-to-help-enterprises-"
        "build-safer-more-capable-agents"
    ),
    "https://openai.github.io/openai-agents-python",
    (
        "https://devops.com/"
        "openai-upgrades-its-agents-sdk-with-sandboxing-"
        "and-a-new-model-harness"
    ),
    (
        "https://github.com/openai/openai-agents-python/"
        "blob/main/docs/tracing.md"
    ),
    (
        "https://mtugrull.medium.com/"
        "unpacking-openais-agents-sdk-a-technical-deep-dive-"
        "into-the-future-of-ai-agents-af32dd56e9d1"
    ),
    "https://developers.openai.com/api/docs/guides/agents",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--concurrency",
        nargs="+",
        type=int,
        default=[1, 2, 4],
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--maximum-bytes",
        type=int,
        default=1_000_000,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "/mnt/ai-data/experiments/phase11c"
        ),
    )
    return parser.parse_args()


def build_candidate_set() -> ResearchSourceCandidateSet:
    request_id = "phase11c-live-http"

    task = ResearchTask(
        task_id="task-001",
        request_id=request_id,
        title="Live HTTP parallel source reading",
        question=(
            "How does bounded HTTP source-reading concurrency behave?"
        ),
        objective=(
            "Measure wall time while preserving source-read semantics."
        ),
        completion_criteria=[
            "Preserve candidate order.",
            "Record source read outcomes.",
        ],
        expected_output="Comparable source-read measurements.",
    )

    graph = ResearchTaskGraph(
        request_id=request_id,
        tasks=[task],
    )

    query = ResearchSearchQuery(
        query_id="query-001",
        request_id=request_id,
        task_id="task-001",
        query_text="OpenAI Agents SDK",
        maximum_results=len(URLS),
    )

    query_set = ResearchSearchQuerySet(
        request_id=request_id,
        task_graph=graph,
        queries=[query],
    )

    candidates = [
        ResearchSourceCandidate(
            source_id=f"source-{index:03d}",
            request_id=request_id,
            task_id="task-001",
            query_id="query-001",
            title=f"Phase 11C source {index}",
            url=url,
            source_type=ResearchSourceType.OTHER,
            snippet="Phase 11C live HTTP benchmark source.",
            rank=index,
            metadata={
                "benchmark": "phase11c",
            },
        )
        for index, url in enumerate(URLS, start=1)
    ]

    return ResearchSourceCandidateSet(
        request_id=request_id,
        query_set=query_set,
        candidates=candidates,
    )


def content_hash(content: str | None) -> str | None:
    if content is None:
        return None

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def document_record(document) -> dict[str, object]:
    error = document.error

    return {
        "source_id": document.candidate.source_id,
        "url": document.candidate.url,
        "status": document.status.value,
        "error_type": (
            error.error_type
            if error is not None
            else None
        ),
        "retryable": (
            error.retryable
            if error is not None
            else None
        ),
        "character_count": document.character_count,
        "content_sha256": content_hash(document.content),
        "http_status": document.metadata.get("http_status"),
        "final_url": document.metadata.get("final_url"),
        "redirect_count": document.metadata.get(
            "redirect_count"
        ),
    }


def main() -> int:
    args = parse_args()

    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")

    if args.maximum_bytes < 1:
        raise SystemExit("--maximum-bytes must be >= 1")

    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be > 0")

    if any(value < 1 for value in args.concurrency):
        raise SystemExit(
            "--concurrency values must all be >= 1"
        )

    candidate_set = build_candidate_set()
    expected_order = [
        candidate.source_id
        for candidate in candidate_set.candidates
    ]

    all_results: list[dict[str, object]] = []

    for concurrency in args.concurrency:
        print(
            f"\n=== CONCURRENCY {concurrency} ===",
            flush=True,
        )

        repeat_results = []

        for repeat in range(1, args.repeats + 1):
            reader = HttpHtmlResearchSourceReader(
                config=HttpHtmlReaderConfig(
                    maximum_bytes=args.maximum_bytes,
                    timeout_seconds=args.timeout_seconds,
                )
            )

            adapter = PipelineSourceReaderAdapter(
                reader,
                maximum_concurrency=concurrency,
            )

            started = time.perf_counter()
            document_set = adapter.read(candidate_set)
            elapsed = time.perf_counter() - started

            actual_order = [
                document.candidate.source_id
                for document in document_set.documents
            ]

            order_preserved = (
                actual_order == expected_order
            )

            if not order_preserved:
                raise RuntimeError(
                    "source document order changed"
                )

            records = [
                document_record(document)
                for document in document_set.documents
            ]

            successful_count = sum(
                1
                for item in records
                if item["status"] == "read"
            )

            failed_count = (
                len(records) - successful_count
            )

            print(
                f"repeat={repeat}/{args.repeats} "
                f"wall={elapsed:.3f}s "
                f"read={successful_count} "
                f"failed={failed_count}",
                flush=True,
            )

            repeat_results.append(
                {
                    "repeat": repeat,
                    "wall_seconds": elapsed,
                    "order_preserved": order_preserved,
                    "successful_count": successful_count,
                    "failed_count": failed_count,
                    "documents": records,
                }
            )

        wall_values = [
            item["wall_seconds"]
            for item in repeat_results
        ]

        all_results.append(
            {
                "concurrency": concurrency,
                "mean_wall_seconds": statistics.mean(
                    wall_values
                ),
                "median_wall_seconds": statistics.median(
                    wall_values
                ),
                "minimum_wall_seconds": min(wall_values),
                "maximum_wall_seconds": max(wall_values),
                "repeat_results": repeat_results,
            }
        )

    baseline = next(
        (
            item["mean_wall_seconds"]
            for item in all_results
            if item["concurrency"] == 1
        ),
        None,
    )

    for item in all_results:
        mean_wall = item["mean_wall_seconds"]
        item["speedup_vs_1"] = (
            baseline / mean_wall
            if baseline is not None
            and mean_wall > 0
            else None
        )

    payload = {
        "phase": "11C",
        "benchmark": "live-http-source-reading",
        "source_count": len(URLS),
        "repeats": args.repeats,
        "maximum_bytes": args.maximum_bytes,
        "timeout_seconds": args.timeout_seconds,
        "results": all_results,
        "production_behavior_changed": False,
        "limitations": [
            (
                "Real web latency and page availability can "
                "vary between repeats."
            ),
            (
                "Exact content hashes may change when sites "
                "serve dynamic HTML."
            ),
            (
                "This measures source reading only, not full "
                "AIRA research end-to-end latency."
            ),
        ],
    }

    timestamp = time.strftime(
        "%Y%m%dT%H%M%S",
        time.gmtime(),
    )

    output_dir = (
        args.output_dir
        / f"{timestamp}_phase11c-live-http"
    )
    output_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    output = output_dir / "comparison.json"

    output.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n=== SUMMARY ===")

    for item in all_results:
        print(
            f"concurrency={item['concurrency']} "
            f"mean={item['mean_wall_seconds']:.3f}s "
            f"median={item['median_wall_seconds']:.3f}s "
            f"speedup={item['speedup_vs_1']:.3f}x"
        )

    print(f"\nPhase 11C comparison: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
