"""CLI parser and dispatch tests for explicit patent comparison."""

from __future__ import annotations

from pathlib import Path

from app.cli import build_parser, main
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


def arguments(output_dir: Path) -> list[str]:
    return [
        "research-patent-compare",
        "--target-publication",
        "EP1000000B1",
        "--comparison-publication",
        "EP2000000A1",
        "--comparison-publication",
        "EP3000000A1",
        "--claim-language",
        "EN",
        "--claim-number",
        "1",
        "--maximum-claim-elements",
        "1",
        "--maximum-mapping-calls",
        "2",
        "--maximum-bytes",
        "4096",
        "--output-dir",
        str(output_dir),
    ]


def test_parser_accepts_explicit_patent_comparison(tmp_path: Path) -> None:
    namespace = build_parser().parse_args(arguments(tmp_path))

    assert namespace.command == "research-patent-compare"
    assert namespace.target_publication == "EP1000000B1"
    assert namespace.comparison_publication == ["EP2000000A1", "EP3000000A1"]
    assert namespace.maximum_mapping_calls == 2


def test_main_builds_request_and_calls_injected_handler(tmp_path: Path) -> None:
    calls: list[tuple[PatentMultiPatentComparisonRequest, Path]] = []

    value = main(
        arguments(tmp_path),
        patent_comparison_handler=lambda request, output_dir: (
            calls.append((request, output_dir)) or 0
        ),
    )

    assert value == 0
    request, output_dir = calls[0]
    assert request.target_publication_number == "EP1000000B1"
    assert request.comparison_publication_numbers == (
        "EP2000000A1",
        "EP3000000A1",
    )
    assert request.planned_maximum_mapping_calls == 2
    assert request.maximum_bytes == 4096
    assert output_dir == tmp_path.resolve()


def test_main_rejects_mapping_budget_before_handler(
    tmp_path: Path,
    capsys,
) -> None:
    calls: list[object] = []
    args = arguments(tmp_path)
    args[args.index("--maximum-claim-elements") + 1] = "2"

    value = main(
        args,
        patent_comparison_handler=lambda *values: calls.append(values) or 0,
    )

    assert value == 2
    assert calls == []
    assert "exceed maximum_mapping_calls" in capsys.readouterr().err
