#!/usr/bin/env python3
"""Run one live Tavily Search to HTTP Reader integration smoke test."""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from app.research.http_html_research_source_reader import (
    HttpHtmlResearchSourceReader,
)
from app.research.tavily_research_source_search_tool import (
    TavilyResearchSourceSearchTool,
)
from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.research_search_query import ResearchSearchQuery
from app.schemas.research_source_document import (
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_search import (
    ResearchSourceSearchStatus,
)
from app.schemas.tavily_search_config import (
    load_tavily_search_config,
)

DEFAULT_QUERY = "OpenAI Responses API official documentation"


def parse_args() -> argparse.Namespace:
    """Parse integration smoke-test arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Search with Tavily and read the first accessible "
            "result without printing credentials or full content."
        )
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Search query sent to Tavily.",
    )
    parser.add_argument(
        "--maximum-results",
        type=int,
        default=3,
        choices=range(1, 6),
        metavar="1-5",
        help="Maximum Tavily candidates to request.",
    )
    parser.add_argument(
        "--maximum-bytes",
        type=int,
        default=1_000_000,
        help="Maximum bytes allowed for each source read.",
    )
    return parser.parse_args()


def main() -> int:
    """Run one live Search to Read integration."""

    args = parse_args()
    load_dotenv()

    if os.getenv("RUN_SEARCH_READ_SMOKE_TEST") != "1":
        print(
            "Smoke test is disabled. Set "
            "RUN_SEARCH_READ_SMOKE_TEST=1 to run it.",
            file=sys.stderr,
        )
        return 2

    try:
        search_config = load_tavily_search_config()
        reader_config = HttpHtmlReaderConfig(
            maximum_bytes=args.maximum_bytes
        )
    except (TypeError, ValueError) as exc:
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
        query_id="search-read-smoke-query-001",
        request_id="search-read-smoke-request-001",
        task_id="search-read-smoke-task-001",
        query_text=args.query,
        maximum_results=args.maximum_results,
    )

    search_result = TavilyResearchSourceSearchTool(
        config=search_config
    ).search(search_query)

    output: dict[str, object] = {
        "query": args.query,
        "search": {
            "status": search_result.status.value,
            "provider": search_result.provider,
            "duration_ms": search_result.duration_ms,
            "candidate_count": len(search_result.candidates),
            "request_id": search_result.metadata.get("request_id"),
            "provider_response_time": search_result.metadata.get(
                "response_time"
            ),
            "usage_credits": search_result.metadata.get(
                "usage_credits"
            ),
        },
        "read_attempts": [],
    }

    if search_result.error is not None:
        output["search"]["error"] = {
            "type": search_result.error.error_type,
            "message": search_result.error.message,
            "retryable": search_result.error.retryable,
        }

    if (
        search_result.status
        is not ResearchSourceSearchStatus.SUCCEEDED
    ):
        print(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    reader = HttpHtmlResearchSourceReader(
        config=reader_config
    )
    successful_document = None
    selected_candidate = None

    attempts: list[dict[str, object]] = []

    for candidate in search_result.candidates:
        document = reader.read(candidate)
        attempt: dict[str, object] = {
            "rank": candidate.rank,
            "title": candidate.title,
            "url": candidate.url,
            "status": document.status.value,
        }

        if document.error is not None:
            attempt["error"] = {
                "type": document.error.error_type,
                "message": document.error.message,
                "retryable": document.error.retryable,
            }
        else:
            attempt["content_type"] = document.content_type.value
            attempt["character_count"] = document.character_count
            attempt["word_count"] = document.word_count
            attempt["section_count"] = len(document.sections)

        attempts.append(attempt)

        if (
            document.status
            is ResearchSourceDocumentStatus.READ
        ):
            successful_document = document
            selected_candidate = candidate
            break

    output["read_attempts"] = attempts

    if successful_document is None or selected_candidate is None:
        output["integration_status"] = "failed"
        output["message"] = (
            "Search succeeded, but no returned candidate "
            "could be read successfully."
        )
        print(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    output["integration_status"] = "succeeded"
    output["selected_source"] = {
        "rank": selected_candidate.rank,
        "source_id": selected_candidate.source_id,
        "title": selected_candidate.title,
        "url": selected_candidate.url,
    }
    output["document"] = {
        "document_id": successful_document.document_id,
        "content_type": successful_document.content_type.value,
        "character_count": successful_document.character_count,
        "word_count": successful_document.word_count,
        "section_count": len(successful_document.sections),
        "metadata": successful_document.metadata,
        "preview": successful_document.content[:500],
        "section_previews": [
            {
                "section_id": section.section_id,
                "start_character": section.start_character,
                "end_character": section.end_character,
                "preview": section.content[:160],
            }
            for section in successful_document.ordered_sections()[:3]
        ],
    }

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
