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
from tests.test_local_pdf_text_extractor import write_pdf


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
    assert namespace.mode == "deterministic"
    assert namespace.source == [str(source)]
    assert namespace.output_dir == "reports"


def test_parser_accepts_semantic_research_mode(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.md"
    source.write_text("Local evidence.", encoding="utf-8")

    namespace = build_parser().parse_args(
        [
            "research",
            "--mode",
            "semantic",
            "--question",
            "How does semantic local research work?",
            "--source",
            str(source),
        ]
    )

    assert namespace.mode == "semantic"


def test_parser_rejects_unsupported_research_mode(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.md"
    source.write_text("Local evidence.", encoding="utf-8")

    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "research",
                "--mode",
                "unsupported",
                "--question",
                "How does semantic local research work?",
                "--source",
                str(source),
            ]
        )


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


def test_validate_sources_accepts_pdf(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"CLI validation does not parse content")

    assert validate_sources([str(source)]) == (source.resolve(),)


def test_validate_sources_rejects_unsupported_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.docx"
    source.write_bytes(b"unsupported")

    with pytest.raises(
        ValueError,
        match="Markdown, text, or PDF file",
    ):
        validate_sources([str(source)])



@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("malformed", "could not be opened or parsed"),
        ("encrypted", "encrypted PDF requires credentials"),
        ("no-text", "no extractable nonblank text"),
    ],
)
def test_main_reports_invalid_pdf_through_local_handler(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    fixture: str,
    message: str,
) -> None:
    source = tmp_path / f"{fixture}.pdf"
    if fixture == "malformed":
        source.write_bytes(b"not a PDF")
    elif fixture == "encrypted":
        write_pdf(source, ["Protected text."], password="secret")
    else:
        write_pdf(source, [None])

    result = main(
        [
            "research",
            "--question",
            "How does local PDF research handle errors?",
            "--source",
            str(source),
        ]
    )

    assert result == 2
    assert message in capsys.readouterr().err


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


def test_main_selects_semantic_local_handler(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.md"
    source.write_text("Semantic local evidence.", encoding="utf-8")
    calls: list[str] = []

    def deterministic_handler(*args: object) -> int:
        calls.append("deterministic")
        return 0

    def semantic_handler(*args: object) -> int:
        calls.append("semantic")
        return 0

    result = main(
        [
            "research",
            "--mode",
            "semantic",
            "--question",
            "How does semantic local research work?",
            "--source",
            str(source),
        ],
        research_handler=deterministic_handler,
        semantic_research_handler=semantic_handler,
    )

    assert result == 0
    assert calls == ["semantic"]


@pytest.mark.parametrize("mode", ["deterministic", "semantic"])
def test_main_passes_resolved_pdf_to_selected_local_handler(
    tmp_path: Path,
    mode: str,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"handler test PDF")
    calls: list[tuple[str, tuple[Path, ...]]] = []

    def deterministic_handler(
        _question: str,
        _objective: str,
        sources: tuple[Path, ...],
        _output_dir: Path,
    ) -> int:
        calls.append(("deterministic", sources))
        return 0

    def semantic_handler(
        _question: str,
        _objective: str,
        sources: tuple[Path, ...],
        _output_dir: Path,
    ) -> int:
        calls.append(("semantic", sources))
        return 0

    arguments = [
        "research",
        "--question",
        "How does local PDF research work?",
        "--source",
        str(source),
    ]
    if mode == "semantic":
        arguments[1:1] = ["--mode", "semantic"]

    result = main(
        arguments,
        research_handler=deterministic_handler,
        semantic_research_handler=semantic_handler,
    )

    assert result == 0
    assert calls == [(mode, (source.resolve(),))]


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


def test_main_runs_default_local_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.md"
    source.write_text(
        (
            "# Grounded Research Evidence\n\n"
            "Grounded research connects claims to "
            "traceable evidence."
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "reports"

    result = main(
        [
            "research",
            "--question",
            "How does grounded research use evidence?",
            "--source",
            str(source),
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    execution_dirs = list(output_dir.iterdir())

    assert result == 0
    assert captured.err == ""
    assert "AIRA report:" in captured.out
    assert "AIRA result:" in captured.out
    assert len(execution_dirs) == 1
    assert (
        execution_dirs[0] / "report.md"
    ).is_file()
    assert (
        execution_dirs[0] / "result.json"
    ).is_file()


def test_parser_accepts_live_research_command() -> None:
    parser = build_parser()
    namespace = parser.parse_args(
        [
            "research-live",
            "--question",
            "How does live grounded research work?",
        ]
    )

    assert namespace.command == "research-live"
    assert namespace.maximum_sources == 3
    assert namespace.maximum_bytes == 1_000_000
    assert namespace.output_dir == "reports/live"


def test_main_calls_injected_live_research_handler(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def handler(
        question: str,
        objective: str,
        maximum_sources: int,
        maximum_bytes: int,
        output_dir: Path,
    ) -> int:
        captured["question"] = question
        captured["objective"] = objective
        captured["maximum_sources"] = maximum_sources
        captured["maximum_bytes"] = maximum_bytes
        captured["output_dir"] = output_dir
        return 0

    result = main(
        [
            "research-live",
            "--question",
            "How does live grounded research work?",
            "--maximum-sources",
            "2",
            "--maximum-bytes",
            "2048",
            "--output-dir",
            str(tmp_path / "live-reports"),
        ],
        live_research_handler=handler,
    )

    assert result == 0
    assert captured["maximum_sources"] == 2
    assert captured["maximum_bytes"] == 2048
    assert captured["output_dir"] == (
        tmp_path / "live-reports"
    ).resolve()


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        (
            "--maximum-sources",
            "0",
            "maximum_sources must be greater than zero",
        ),
        (
            "--maximum-bytes",
            "0",
            "maximum_bytes must be greater than zero",
        ),
    ],
)
def test_live_research_rejects_nonpositive_limits(
    option: str,
    value: str,
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        [
            "research-live",
            "--question",
            "How does live grounded research work?",
            option,
            value,
        ],
        live_research_handler=lambda *args: 0,
    )

    captured = capsys.readouterr()

    assert result == 2
    assert message in captured.err

def test_live_research_rejects_too_small_maximum_bytes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        [
            "research-live",
            "--question",
            "How does live grounded research work?",
            "--maximum-bytes",
            "100",
        ],
        live_research_handler=lambda *args: 0,
    )

    captured = capsys.readouterr()

    assert result == 2
    assert (
        "maximum_bytes must be at least 1024"
        in captured.err
    )
