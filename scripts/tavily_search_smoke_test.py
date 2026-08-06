#!/usr/bin/env python3
"""Run one explicit live smoke test against Tavily Search API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from dotenv import load_dotenv

from app.research.tavily_research_source_search_tool import (
    TavilyResearchSourceSearchTool,
)
from app.schemas.research_search_query import ResearchSearchQuery
from app.schemas.research_source_search import (
    ResearchSourceSearchStatus,
)
from app.schemas.tavily_search_config import (
    load_tavily_search_config,
)

DEFAULT_QUERY = "OpenAI Responses API official documentation"


def parse_args() -> argparse.Namespace:
    """Parse smoke-test arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Run one live Tavily search without printing "
            "the API key or request headers."
        )
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Search query sent to Tavily.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=3,
        choices=range(1, 6),
        metavar="1-5",
        help="Maximum results to request (default: 3).",
    )
    return parser.parse_args()


def safe_output(
    *,
    result: Any,
) -> dict[str, object]:
    """Return output containing no authentication data."""

    output: dict[str, object] = {
        "provider": result.provider,
        "status": result.status.value,
        "duration_ms": result.duration_ms,
        "candidate_count": len(result.candidates),
        "request_id": result.metadata.get("request_id"),
        "provider_response_time": result.metadata.get(
            "response_time"
        ),
        "usage_credits": result.metadata.get(
            "usage_credits"
        ),
    }

    if result.error is not None:
        output["error"] = {
            "type": result.error.error_type,
            "message": result.error.message,
            "retryable": result.error.retryable,
            "http_status": result.metadata.get(
                "http_status"
            ),
            "retry_after": result.metadata.get(
                "retry_after"
            ),
        }

    output["results"] = [
        {
            "rank": candidate.rank,
            "title": candidate.title,
            "url": candidate.url,
            "source_id": candidate.source_id,
            "provider_score": candidate.metadata.get(
                "provider_score"
            ),
        }
        for candidate in result.candidates
    ]

    return output


def main() -> int:
    """Run one live Tavily search."""

    args = parse_args()
    load_dotenv()

    if os.getenv("RUN_TAVILY_SMOKE_TEST") != "1":
        print(
            "Smoke test is disabled. Set "
            "RUN_TAVILY_SMOKE_TEST=1 to run it.",
            file=sys.stderr,
        )
        return 2

    try:
        config = load_tavily_search_config()
    except (ValueError, TypeError) as exc:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    search_query = ResearchSearchQuery(
        query_id="tavily-smoke-query-001",
        request_id="tavily-smoke-request-001",
        task_id="tavily-smoke-task-001",
        query_text=args.query,
        maximum_results=args.max_results,
    )

    result = TavilyResearchSourceSearchTool(
        config=config
    ).search(search_query)

    print(
        json.dumps(
            safe_output(result=result),
            ensure_ascii=False,
            indent=2,
        )
    )

    if result.status is ResearchSourceSearchStatus.FAILED:
        return 1

    if result.status is ResearchSourceSearchStatus.NO_RESULTS:
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
