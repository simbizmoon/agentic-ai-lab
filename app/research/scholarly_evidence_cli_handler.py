"""CLI adapter for bounded scholarly exact-evidence workflows."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.research.scholarly_evidence_factory import (
    build_openalex_scholarly_evidence_workflow,
)
from app.research.scholarly_evidence_full_workflow import (
    ScholarlyEvidenceFullWorkflowResult,
)
from app.schemas.scholarly_evidence_request import ScholarlyEvidenceRequest


class ScholarlyEvidenceWorkflowProtocol(Protocol):
    """Minimal full-workflow contract required by the CLI."""

    def execute(
        self,
        request: ScholarlyEvidenceRequest,
        *,
        request_id: str,
        task_id: str,
        output_dir: Path,
        execution_id: str,
    ) -> ScholarlyEvidenceFullWorkflowResult: ...


ScholarlyEvidenceWorkflowFactory = Callable[
    [ScholarlyEvidenceRequest], ScholarlyEvidenceWorkflowProtocol
]


class ScholarlyEvidenceCliHandler:
    """Execute and render one explicit bounded scholarly evidence request."""

    def __init__(
        self,
        *,
        runtime_factory: ScholarlyEvidenceWorkflowFactory = (
            build_openalex_scholarly_evidence_workflow
        ),
        request_id_factory: Callable[[], str] | None = None,
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._runtime_factory = runtime_factory
        self._request_id_factory = request_id_factory or (
            lambda: f"scholarly-evidence-request-{uuid4()}"
        )
        self._execution_id_factory = execution_id_factory or (
            lambda: f"scholarly-evidence-{uuid4()}"
        )

    def __call__(self, request: ScholarlyEvidenceRequest, output_dir: Path) -> int:
        request_id = self._request_id_factory().strip()
        execution_id = self._execution_id_factory().strip()
        if not request_id:
            raise ValueError("request_id factory returned blank value")
        if not execution_id:
            raise ValueError("execution_id factory returned blank value")

        print("AIRA bounded scholarly exact evidence")
        print("provider=OpenAlex")
        print(f"request_id={request_id}")
        print(f"execution_id={execution_id}")
        print(f"query={request.query}")
        print(f"maximum_results={request.maximum_results}")
        print(
            "planned_maximum_provider_requests="
            f"{request.planned_maximum_provider_requests}"
        )
        print(f"require_abstract={str(request.require_abstract).lower()}")
        print("openai_requests=0")
        print("pdf_downloads=0")
        print("full_text_downloads=0")
        print()

        result = self._runtime_factory(request).execute(
            request,
            request_id=request_id,
            task_id="scholarly-exact-abstract-evidence",
            output_dir=output_dir,
            execution_id=execution_id,
        )
        workflow = result.workflow_result
        paths = result.artifact_paths
        print("result_status=scholarly_evidence_available")
        print(f"actual_provider_requests={workflow.actual_provider_requests}")
        print(f"records_received={workflow.records_received}")
        print(f"works_accepted={workflow.works_accepted}")
        print(f"records_rejected={workflow.records_rejected}")
        print(f"abstract_documents={workflow.abstract_documents_created}")
        print(
            f"works_omitted_without_abstract={workflow.works_omitted_without_abstract}"
        )
        print(f"whole_abstract_evidence={workflow.whole_abstract_evidence_created}")
        print(f"scholarly_evidence_markdown_path={paths.markdown_path}")
        print(f"scholarly_evidence_json_path={paths.json_path}")
        print()
        print("=== SCOPE NOTICE ===")
        print(
            "This command preserves provider metadata and exact whole-abstract "
            "evidence. It does not assess semantic relevance, paper quality, "
            "citation impact, systematic-review completeness, or permission to "
            "obtain or use full text."
        )
        return 0
