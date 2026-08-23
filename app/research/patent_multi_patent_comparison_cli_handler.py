"""CLI adapter for explicit bounded patent comparison workflows."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.research.patent_multi_patent_comparison_factory import (
    build_openai_epo_patent_multi_patent_comparison_workflow,
)
from app.research.patent_multi_patent_comparison_full_workflow import (
    PatentMultiPatentFullWorkflowResult,
)
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


class PatentComparisonWorkflowProtocol(Protocol):
    """Minimal full-workflow execution contract required by the CLI."""

    def execute(
        self,
        request: PatentMultiPatentComparisonRequest,
        *,
        request_id: str,
        output_dir: Path,
        execution_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentMultiPatentFullWorkflowResult: ...


PatentComparisonWorkflowFactory = Callable[
    [PatentMultiPatentComparisonRequest],
    PatentComparisonWorkflowProtocol,
]


class PatentMultiPatentComparisonCliHandler:
    """Execute and render one explicit technical patent comparison."""

    def __init__(
        self,
        *,
        runtime_factory: PatentComparisonWorkflowFactory = (
            build_openai_epo_patent_multi_patent_comparison_workflow
        ),
        request_id_factory: Callable[[], str] | None = None,
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._runtime_factory = runtime_factory
        self._request_id_factory = request_id_factory or (
            lambda: f"patent-comparison-request-{uuid4()}"
        )
        self._execution_id_factory = execution_id_factory or (
            lambda: f"patent-comparison-{uuid4()}"
        )

    def __call__(
        self,
        request: PatentMultiPatentComparisonRequest,
        output_dir: Path,
    ) -> int:
        request_id = self._request_id_factory().strip()
        execution_id = self._execution_id_factory().strip()
        if not request_id:
            raise ValueError("request_id factory returned blank value")
        if not execution_id:
            raise ValueError("execution_id factory returned blank value")

        print("AIRA patent multi-patent technical comparison")
        print(f"request_id={request_id}")
        print(f"execution_id={execution_id}")
        print(f"target_publication={request.target_publication_number}")
        print(
            "comparison_publications="
            + ",".join(request.comparison_publication_numbers)
        )
        print(f"claim_language={request.claim_language}")
        print(f"claim_number={request.claim_number}")
        print(f"maximum_claim_elements={request.maximum_claim_elements}")
        print(
            "comparison_publication_count="
            f"{len(request.comparison_publication_numbers)}"
        )
        print(f"planned_maximum_mapping_calls={request.planned_maximum_mapping_calls}")
        print(f"maximum_mapping_calls={request.maximum_mapping_calls}")
        print()

        result = self._runtime_factory(request).execute(
            request,
            request_id=request_id,
            output_dir=output_dir,
            execution_id=execution_id,
        )
        workflow = result.workflow_result
        comparison = workflow.comparison_result.comparisons[0]
        paths = workflow.artifact_paths

        print("result_status=comparison_available")
        print(f"actual_mapping_calls={workflow.actual_mapping_calls}")
        print(f"comparison_markdown_path={paths.markdown_path}")
        print(f"comparison_json_path={paths.json_path}")
        print()
        print("=== SCOPE NOTICE ===")
        print(comparison.scope_notice)
        return 0
