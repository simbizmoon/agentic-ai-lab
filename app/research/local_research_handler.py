"""Default CLI handler for local-document research."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from app.research.local_document_adapter import (
    LocalDocumentAdapter,
)
from app.research.local_runtime import (
    build_local_research_pipeline,
)
from app.research.research_result_guardrail import (
    ResearchResultGuardrail,
)
from app.research.research_result_writer import (
    ResearchResultWriter,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)


class LocalResearchHandler:
    """Execute local research and persist its results."""

    def __init__(
        self,
        *,
        id_factory: Callable[[], str] | None = None,
        writer: ResearchResultWriter | None = None,
        guardrail: ResearchResultGuardrail | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._id_factory = id_factory or self._default_id
        self._writer = writer or ResearchResultWriter()
        self._guardrail = (
            guardrail or ResearchResultGuardrail()
        )
        self._stdout = stdout or sys.stdout

    def __call__(
        self,
        question: str,
        objective: str,
        sources: tuple[Path, ...],
        output_dir: Path,
    ) -> int:
        """Run the local pipeline and write report artifacts."""

        execution_id = self._id_factory().strip()

        if not execution_id:
            raise RuntimeError(
                "research execution ID factory returned blank value"
            )

        bundle = LocalDocumentAdapter().load(sources)
        pipeline = build_local_research_pipeline(bundle)
        request = ResearchRequest(
            request_id=execution_id,
            question=question,
            objective=objective,
            preferred_source_types=[
                ResearchSourceType.OTHER,
            ],
            maximum_sources=max(1, len(sources)),
        )

        result = pipeline.run(
            request,
            workspace_id=f"{execution_id}-workspace",
        )
        self._guardrail.validate(
            result,
            execution_id=execution_id,
        )
        paths = self._writer.write(
            result,
            output_dir=output_dir,
            execution_id=execution_id,
        )

        print(
            f"AIRA report: {paths.report_path}",
            file=self._stdout,
        )
        print(
            f"AIRA result: {paths.result_path}",
            file=self._stdout,
        )

        return 0

    @staticmethod
    def _default_id() -> str:
        """Return a unique local execution identifier."""

        return f"aira-{uuid4().hex}"
