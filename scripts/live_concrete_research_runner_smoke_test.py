#!/usr/bin/env python3
"""Run one live Concrete AIRA Research Runner smoke test."""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from app.application.research_execution import (
    ApplicationResearchExecutionRequest,
)
from app.research.concrete_aira_research_runner import (
    ConcreteAiraResearchRunner,
)
from app.research.live_runtime import (
    build_live_research_pipeline,
)
from app.schemas.http_html_reader_config import (
    HttpHtmlReaderConfig,
)
from app.schemas.tavily_search_config import (
    load_tavily_search_config,
)

DEFAULT_QUERY = (
    "OpenAI Responses API official documentation overview"
)


def parse_args() -> argparse.Namespace:
    """Parse live runner smoke-test arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Execute one application research request through "
            "the live Tavily and HTTP reader pipeline."
        )
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Research question used by the application request.",
    )
    parser.add_argument(
        "--maximum-bytes",
        type=int,
        default=1_000_000,
        help="Maximum response bytes for one source.",
    )
    return parser.parse_args()


def main() -> int:
    """Execute one live concrete research runner."""

    args = parse_args()
    load_dotenv()

    if os.getenv("RUN_LIVE_RESEARCH_RUNNER_SMOKE_TEST") != "1":
        print(
            "Smoke test is disabled. Set "
            "RUN_LIVE_RESEARCH_RUNNER_SMOKE_TEST=1 to run it.",
            file=sys.stderr,
        )
        return 2

    try:
        search_config = load_tavily_search_config()
        reader_config = HttpHtmlReaderConfig(
            maximum_bytes=args.maximum_bytes
        )
        application_request = ApplicationResearchExecutionRequest(
            request_id="live-runner-smoke-request-001",
            workspace_id="live-runner-smoke-workspace-001",
            agent_id="aira-live-research-agent",
            query=args.query,
            context={
                "objective": (
                    "Produce a grounded answer with traceable "
                    "evidence from one live web source."
                ),
                "depth": "quick",
                "output_format": "brief",
                "maximum_sources": 1,
                "require_citations": True,
            },
            metadata={
                "mode": "live-smoke-test",
            },
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

    runner = ConcreteAiraResearchRunner(
        pipeline_factory=lambda research_request: (
            build_live_research_pipeline(
                request=research_request,
                search_config=search_config,
                reader_config=reader_config,
            )
        )
    )

    try:
        output = runner.execute(application_request)
    except (RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    payload = {
        "status": "succeeded",
        "request_id": application_request.request_id,
        "workspace_id": application_request.workspace_id,
        "agent_id": application_request.agent_id,
        "summary": output.summary,
        "result": output.result,
        "artifact_ids": output.artifact_ids,
        "citation_ids": output.citation_ids,
    }

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
