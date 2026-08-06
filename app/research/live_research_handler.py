"""CLI handler for live web research."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO
from uuid import uuid4

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
from app.research.research_result_writer import (
    ResearchResultWriter,
)
from app.schemas.http_html_reader_config import (
    HttpHtmlReaderConfig,
)
from app.schemas.tavily_search_config import (
    TavilySearchConfig,
    load_tavily_search_config,
)


class LiveResearchHandler:
    """Execute live web research and persist its artifacts."""

    def __init__(
        self,
        *,
        id_factory: Callable[[], str] | None = None,
        config_loader: (
            Callable[[], TavilySearchConfig] | None
        ) = None,
        writer: ResearchResultWriter | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._id_factory = id_factory or self._default_id
        self._config_loader = (
            config_loader or self._load_config
        )
        self._writer = writer or ResearchResultWriter()
        self._stdout = stdout or sys.stdout

    def __call__(
        self,
        question: str,
        objective: str,
        maximum_sources: int,
        maximum_bytes: int,
        output_dir: Path,
    ) -> int:
        """Run one live research request and write artifacts."""

        execution_id = self._id_factory().strip()

        if not execution_id:
            raise RuntimeError(
                "live research execution ID factory "
                "returned blank value"
            )

        search_config = self._config_loader()
        reader_config = HttpHtmlReaderConfig(
            maximum_bytes=maximum_bytes
        )
        request = ApplicationResearchExecutionRequest(
            request_id=execution_id,
            workspace_id=f"{execution_id}-workspace",
            agent_id="aira-live-research-agent",
            query=question,
            context={
                "objective": objective,
                "depth": "quick",
                "output_format": "brief",
                "maximum_sources": maximum_sources,
                "require_citations": True,
            },
            metadata={
                "mode": "live-cli",
            },
        )
        runner = ConcreteAiraResearchRunner(
            pipeline_factory=lambda research_request: (
                build_live_research_pipeline(
                    request=research_request,
                    search_config=search_config,
                    reader_config=reader_config,
                )
            ),
            writer=self._writer,
            output_dir=output_dir,
            artifact_execution_id_factory=(
                lambda _request: execution_id
            ),
        )
        output = runner.execute(request)
        paths = output.result["artifact_paths"]

        print(
            f"AIRA live report: {paths['report']}",
            file=self._stdout,
        )
        print(
            f"AIRA live result: {paths['result']}",
            file=self._stdout,
        )
        print(
            f"AIRA live quality: "
            f"{output.result['quality_score']}",
            file=self._stdout,
        )

        return 0

    @staticmethod
    def _load_config() -> TavilySearchConfig:
        """Load dotenv values and validated Tavily configuration."""

        load_dotenv()
        return load_tavily_search_config()

    @staticmethod
    def _default_id() -> str:
        """Return one unique live execution identifier."""

        return f"aira-live-{uuid4().hex}"
