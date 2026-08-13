"""Benchmark serial vs parallel source-reader adapter execution."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from app.research.pipeline_source_adapters import PipelineSourceReaderAdapter
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)


@dataclass(frozen=True)
class DelayedReader:
    delay_seconds: float

    def read(
        self,
        candidate: ResearchSourceCandidate,
    ) -> ResearchSourceDocument:
        time.sleep(self.delay_seconds)
        content = f"content for {candidate.source_id}"

        return ResearchSourceDocument(
            document_id=f"document-{candidate.source_id}",
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=ResearchSourceContentType.TEXT,
            content=content,
            language=None,
            sections=[],
            word_count=len(content.split()),
            character_count=len(content),
            reader="phase11b-delayed-reader",
            error=None,
            metadata={},
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=int, default=8)
    parser.add_argument("--delay-seconds", type=float, default=0.05)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--concurrency",
        type=int,
        nargs="+",
        default=[1, 2, 4],
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/mnt/ai-data/experiments/phase11b"),
    )
    return parser.parse_args()


def source_candidate_set(
    count: int,
) -> ResearchSourceCandidateSet:
    task = ResearchTask(
        task_id="task-001",
        request_id="phase11b-request",
        title="Parallel source reading benchmark",
        question="How does parallel source reading behave?",
        objective=(
            "Measure bounded source-reader scheduling performance."
        ),
        completion_criteria=[
            "Preserve deterministic candidate order."
        ],
        expected_output="Ordered source documents.",
    )
    graph = ResearchTaskGraph(
        request_id="phase11b-request",
        tasks=[task],
    )
    query = ResearchSearchQuery(
        query_id="query-001",
        request_id="phase11b-request",
        task_id="task-001",
        query_text="parallel source reading benchmark",
        maximum_results=count,
    )
    query_set = ResearchSearchQuerySet(
        request_id="phase11b-request",
        task_graph=graph,
        queries=[query],
    )

    candidates = [
        ResearchSourceCandidate(
            source_id=f"source-{index:03d}",
            request_id="phase11b-request",
            task_id="task-001",
            query_id="query-001",
            title=f"Source {index}",
            url=f"https://example.com/{index}",
            source_type=ResearchSourceType.OTHER,
            snippet="benchmark",
            rank=index,
            metadata={},
        )
        for index in range(1, count + 1)
    ]

    return ResearchSourceCandidateSet(
        request_id="phase11b-request",
        query_set=query_set,
        candidates=candidates,
    )


def main() -> int:
    args = parse_args()
    if args.candidates < 1:
        raise SystemExit("--candidates must be >= 1")
    if args.delay_seconds < 0:
        raise SystemExit("--delay-seconds must be >= 0")
    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")
    if any(value < 1 for value in args.concurrency):
        raise SystemExit("--concurrency values must be >= 1")

    candidates = source_candidate_set(args.candidates)
    expected_order = [item.source_id for item in candidates.candidates]
    rows = []

    for concurrency in args.concurrency:
        elapsed_values = []
        for _ in range(args.repeats):
            adapter = PipelineSourceReaderAdapter(
                DelayedReader(args.delay_seconds),
                maximum_concurrency=concurrency,
            )
            started = time.perf_counter()
            documents = adapter.read(candidates)
            elapsed_values.append(time.perf_counter() - started)

            actual_order = [
                item.candidate.source_id
                for item in documents.documents
            ]
            if actual_order != expected_order:
                raise RuntimeError("candidate order changed")

        rows.append(
            {
                "concurrency": concurrency,
                "mean_seconds": statistics.mean(elapsed_values),
                "median_seconds": statistics.median(elapsed_values),
                "repeats": args.repeats,
            }
        )

    baseline = next(
        row["mean_seconds"]
        for row in rows
        if row["concurrency"] == 1
    )
    for row in rows:
        row["speedup_vs_1"] = baseline / row["mean_seconds"]

    payload = {
        "phase": "11B",
        "candidate_count": args.candidates,
        "delay_seconds": args.delay_seconds,
        "results": rows,
        "production_behavior_changed": False,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "comparison.json"
    output.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2))
    print(f"Phase 11B comparison: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
