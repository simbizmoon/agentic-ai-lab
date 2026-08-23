"""Tests for the explicit patent comparison CLI adapter."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.research.patent_multi_patent_comparison_cli_handler import (
    PatentMultiPatentComparisonCliHandler,
)
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


class FakeRuntime:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[object, str, Path, str]] = []

    def execute(
        self,
        request: PatentMultiPatentComparisonRequest,
        *,
        request_id: str,
        output_dir: Path,
        execution_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> object:
        self.calls.append((request, request_id, output_dir, execution_id))
        return self.result


def request() -> PatentMultiPatentComparisonRequest:
    return PatentMultiPatentComparisonRequest(
        target_publication_number="EP1000000B1",
        comparison_publication_numbers=("EP2000000A1", "EP3000000A1"),
        maximum_claim_elements=1,
        maximum_mapping_calls=2,
    )


def result(tmp_path: Path) -> object:
    comparison = SimpleNamespace(scope_notice="Technical comparison only.")
    workflow = SimpleNamespace(
        actual_mapping_calls=2,
        comparison_result=SimpleNamespace(comparisons=(comparison,)),
        artifact_paths=SimpleNamespace(
            markdown_path=tmp_path / "comparison-001" / "comparison.md",
            json_path=tmp_path / "comparison-001" / "comparison.json",
        ),
    )
    return SimpleNamespace(workflow_result=workflow)


def test_handler_prints_cost_bounds_paths_and_scope(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_request = request()
    runtime = FakeRuntime(result(tmp_path))

    value = PatentMultiPatentComparisonCliHandler(
        runtime_factory=lambda _request: runtime,  # type: ignore[arg-type]
        request_id_factory=lambda: "request-001",
        execution_id_factory=lambda: "comparison-001",
    )(source_request, tmp_path)

    assert value == 0
    assert runtime.calls == [
        (source_request, "request-001", tmp_path, "comparison-001")
    ]
    output = capsys.readouterr().out
    for expected in (
        "target_publication=EP1000000B1",
        "comparison_publications=EP2000000A1,EP3000000A1",
        "maximum_claim_elements=1",
        "comparison_publication_count=2",
        "planned_maximum_mapping_calls=2",
        "maximum_mapping_calls=2",
        "actual_mapping_calls=2",
        f"comparison_markdown_path={tmp_path}/comparison-001/comparison.md",
        f"comparison_json_path={tmp_path}/comparison-001/comparison.json",
        "Technical comparison only.",
    ):
        assert expected in output


@pytest.mark.parametrize(
    ("request_id", "execution_id", "message"),
    ((" ", "comparison-001", "request_id"), ("request-001", "", "execution_id")),
)
def test_handler_rejects_blank_generated_identity_before_factory(
    tmp_path: Path,
    request_id: str,
    execution_id: str,
    message: str,
) -> None:
    factory_calls: list[object] = []

    with pytest.raises(ValueError, match=message):
        PatentMultiPatentComparisonCliHandler(
            runtime_factory=lambda value: factory_calls.append(value),  # type: ignore[arg-type,return-value]
            request_id_factory=lambda: request_id,
            execution_id_factory=lambda: execution_id,
        )(request(), tmp_path)

    assert factory_calls == []
