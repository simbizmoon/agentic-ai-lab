#!/usr/bin/env python3
"""Run one explicit live smoke test for the HTTP/HTML source reader."""

from __future__ import annotations

import argparse
import json
import os
import sys

from app.research.http_html_research_source_reader import (
    HttpHtmlResearchSourceReader,
)
from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceDocumentStatus,
)

DEFAULT_URL = (
    "https://developers.openai.com/api/reference/"
    "responses/overview"
)


def parse_args() -> argparse.Namespace:
    """Parse smoke-test arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Read one public HTML page without printing "
            "the complete document body."
        )
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Public HTTP or HTTPS source URL.",
    )
    parser.add_argument(
        "--maximum-bytes",
        type=int,
        default=1_000_000,
        help="Maximum response bytes (default: 1000000).",
    )
    return parser.parse_args()


def main() -> int:
    """Run one live HTTP/HTML read."""

    args = parse_args()

    if os.getenv("RUN_HTTP_READER_SMOKE_TEST") != "1":
        print(
            "Smoke test is disabled. Set "
            "RUN_HTTP_READER_SMOKE_TEST=1 to run it.",
            file=sys.stderr,
        )
        return 2

    try:
        config = HttpHtmlReaderConfig(
            maximum_bytes=args.maximum_bytes
        )
        candidate = ResearchSourceCandidate(
            source_id="http-reader-smoke-source-001",
            request_id="http-reader-smoke-request-001",
            task_id="http-reader-smoke-task-001",
            query_id="http-reader-smoke-query-001",
            title="HTTP reader live smoke source",
            url=args.url,
            source_type=ResearchSourceType.OTHER,
            rank=1,
        )
    except ValueError as exc:
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

    document = HttpHtmlResearchSourceReader(
        config=config
    ).read(candidate)

    output: dict[str, object] = {
        "status": document.status.value,
        "reader": document.reader,
        "content_type": document.content_type.value,
        "character_count": document.character_count,
        "word_count": document.word_count,
        "section_count": len(document.sections),
        "metadata": document.metadata,
    }

    if document.error is not None:
        output["error"] = {
            "type": document.error.error_type,
            "message": document.error.message,
            "retryable": document.error.retryable,
        }
    else:
        output["preview"] = document.content[:500]
        output["section_previews"] = [
            {
                "section_id": section.section_id,
                "start_character": section.start_character,
                "end_character": section.end_character,
                "preview": section.content[:160],
            }
            for section in document.ordered_sections()[:3]
        ]

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
    )

    if document.status is ResearchSourceDocumentStatus.FAILED:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
