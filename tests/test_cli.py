"""Tests for the AIRA command-line interface."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cli import (
    build_parser,
    default_objective,
    main,
    validate_sources,
)


def test_parser_accepts_research_command(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.md"
    source.write_text(
        "# Evidence\n\nGrounded research uses evidence.",
        encoding="utf-8",
    )

    parser = build_parser()
    namespace = parser.parse_args(
        [
            "research",
            "--question",
            "How does grounded research use evidence?",
            "--source",
            str(source),
        ]
    )

    assert namespace.command == "research"
    assert namespace.source == [str(source)]
    assert namespace.output_dir == "reports"


def test_default_objective_is_distinct_from_question() -> None:
    question = "How does grounded research use evidence?"

    objective = default_objective(question)

    assert objective != question
    assert question in objective
    assert len(objective) >= 15


def test_validate_sources_accepts_markdown_and_text(
    tmp_path: Path,
) -> None:
    markdown = tmp_path / "one.md"
    text = tmp_path / "two.txt"

    markdown.write_text("Markdown evidence.", encoding="utf-8")
    text.write_text("Text evidence.", encoding="utf-8")

    result = validate_sources(
        [
            str(markdown),
            str(text),
        ]
    )

    assert result == (
        markdown.resolve(),
        text.resolve(),
    )


def test_validate_sources_rejects_missing_file(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.md"

    with pytest.raises(
        ValueError,
        match="source does not exist",
    ):
        validate_sources([str(missing)])


def test_validate_sources_rejects_unsupported_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"not a real PDF")

    with pytest.raises(
        ValueError,
        match="Markdown or text file",
    ):
        validate_sources([str(source)])


def test_main_calls_injected_research_handler(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.md"
    source.write_text(
        "Grounded research requires traceable evidence.",
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def handler(
        question: str,
        objective: str,
        sources: tuple[Path, ...],
        output_dir: Path,
    ) -> int:
        captured["question"] = question
        captured["objective"] = objective
        captured["sources"] = sources
        captured["output_dir"] = output_dir
        return 0

    result = main(
        [
            "research",
            "--question",
            "How does grounded research use evidence?",
            "--source",
            str(source),
            "--output-dir",
            str(tmp_path / "reports"),
        ],
        research_handler=handler,
    )

    assert result == 0
    assert captured["question"] == (
        "How does grounded research use evidence?"
    )
    assert captured["sources"] == (source.resolve(),)
    assert captured["output_dir"] == (
        tmp_path / "reports"
    ).resolve()


def test_main_returns_error_for_short_question(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.md"
    source.write_text("Evidence.", encoding="utf-8")

    result = main(
        [
            "research",
            "--question",
            "short",
            "--source",
            str(source),
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "at least 10 characters" in captured.err


def test_main_reports_unconnected_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.md"
    source.write_text(
        "Grounded research requires evidence.",
        encoding="utf-8",
    )

    result = main(
        [
            "research",
            "--question",
            "How does grounded research use evidence?",
            "--source",
            str(source),
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "runtime is not connected yet" in captured.err
