"""CLI parser and dispatch tests for bounded scholarly evidence."""

from __future__ import annotations

from pathlib import Path

from app.cli import build_parser, main
from app.schemas.scholarly_evidence_request import ScholarlyEvidenceRequest
from app.schemas.scholarly_work import ScholarlyWorkType


def arguments(output_dir: Path) -> list[str]:
    return [
        "research-scholarly-evidence",
        "--query",
        "retrieval augmented generation",
        "--maximum-results",
        "3",
        "--start-date",
        "2020-01-01",
        "--end-date",
        "2026-08-23",
        "--work-type",
        "journal_article",
        "--require-abstract",
        "--output-dir",
        str(output_dir),
    ]


def test_parser_accepts_bounded_scholarly_evidence(tmp_path: Path) -> None:
    namespace = build_parser().parse_args(arguments(tmp_path))
    assert namespace.command == "research-scholarly-evidence"
    assert namespace.maximum_results == 3
    assert namespace.maximum_provider_requests == 1
    assert namespace.work_type == ["journal_article"]
    assert namespace.require_abstract is True


def test_main_builds_request_and_calls_injected_handler(tmp_path: Path) -> None:
    calls: list[tuple[ScholarlyEvidenceRequest, Path]] = []
    value = main(
        arguments(tmp_path),
        scholarly_evidence_handler=lambda request, output_dir: (
            calls.append((request, output_dir)) or 0
        ),
    )
    assert value == 0
    request, output_dir = calls[0]
    assert request.query == "retrieval augmented generation"
    assert request.maximum_results == 3
    assert request.maximum_provider_requests == 1
    assert request.work_types == (ScholarlyWorkType.JOURNAL_ARTICLE,)
    assert request.require_abstract is True
    assert output_dir == tmp_path.resolve()


def test_main_rejects_more_than_one_provider_request_before_handler(
    tmp_path: Path, capsys
) -> None:
    calls: list[object] = []
    args = arguments(tmp_path)
    args.extend(["--maximum-provider-requests", "2"])
    value = main(
        args,
        scholarly_evidence_handler=lambda *values: calls.append(values) or 0,
    )
    assert value == 2
    assert calls == []
    assert "maximum_provider_requests" in capsys.readouterr().err


def test_main_rejects_invalid_date_before_handler(tmp_path: Path, capsys) -> None:
    calls: list[object] = []
    args = arguments(tmp_path)
    args[args.index("--start-date") + 1] = "not-a-date"
    value = main(
        args,
        scholarly_evidence_handler=lambda *values: calls.append(values) or 0,
    )
    assert value == 2
    assert calls == []
    assert "start_date must use YYYY-MM-DD format" in capsys.readouterr().err
