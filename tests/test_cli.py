"""Tests for the AIRA command-line interface."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.cli import (
    build_parser,
    default_objective,
    main,
    validate_sources,
)
from app.research.local_document_access_policy import LocalDocumentAccessResult
from app.schemas.patent_research_request import PatentResearchRequest
from tests.test_local_hwpx_text_extractor import write_hwpx
from tests.test_local_pdf_text_extractor import write_pdf


@pytest.fixture(autouse=True)
def isolate_runtime_caches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))


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
            "--allowed-root",
            str(tmp_path),
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
            "--approve-external-send",
            "--question",
            "How does semantic local research work?",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
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
                "--allowed-root",
                str(tmp_path),
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


@pytest.mark.parametrize("suffix", [".hwp", ".docx"])
def test_validate_sources_rejects_unsupported_file(
    tmp_path: Path,
    suffix: str,
) -> None:
    source = tmp_path / f"source{suffix}"
    source.write_bytes(b"unsupported")

    with pytest.raises(
        ValueError,
        match="Markdown, text, PDF, or HWPX file",
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
            "--allowed-root",
            str(tmp_path),
        ]
    )

    assert result == 2
    assert message in capsys.readouterr().err


def test_validate_sources_accepts_hwpx(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.hwpx"
    write_hwpx(
        source,
        sections={"Contents/section0.xml": ("Local evidence.",)},
    )

    assert validate_sources([str(source)]) == (source.resolve(),)


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
        sources: tuple[LocalDocumentAccessResult, ...],
        output_dir: Path,
        _access_policy: object,
        _approval: object,
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
            "--allowed-root",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "reports"),
        ],
        research_handler=handler,
    )

    assert result == 0
    assert captured["question"] == ("How does grounded research use evidence?")
    assert tuple(result.resolved_path for result in captured["sources"]) == (
        source.resolve(),
    )
    assert captured["output_dir"] == (tmp_path / "reports").resolve()


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
            "--approve-external-send",
            "--question",
            "How does semantic local research work?",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
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
        sources: tuple[LocalDocumentAccessResult, ...],
        _output_dir: Path,
        _access_policy: object,
        _approval: object,
    ) -> int:
        calls.append(
            (
                "deterministic",
                tuple(result.resolved_path for result in sources),
            )
        )
        return 0

    def semantic_handler(
        _question: str,
        _objective: str,
        sources: tuple[LocalDocumentAccessResult, ...],
        _output_dir: Path,
        _access_policy: object,
        _approval: object,
    ) -> int:
        calls.append(
            (
                "semantic",
                tuple(result.resolved_path for result in sources),
            )
        )
        return 0

    arguments = [
        "research",
        "--question",
        "How does local PDF research work?",
        "--source",
        str(source),
        "--allowed-root",
        str(tmp_path),
    ]
    if mode == "semantic":
        arguments[1:1] = [
            "--mode",
            "semantic",
            "--approve-external-send",
        ]

    result = main(
        arguments,
        research_handler=deterministic_handler,
        semantic_research_handler=semantic_handler,
    )

    assert result == 0
    assert calls == [(mode, (source.resolve(),))]


@pytest.mark.parametrize("mode", ["deterministic", "semantic"])
def test_main_passes_resolved_hwpx_to_selected_local_handler(
    tmp_path: Path,
    mode: str,
) -> None:
    source = tmp_path / "source.hwpx"
    write_hwpx(
        source,
        sections={"Contents/section0.xml": ("Local evidence.",)},
    )
    calls: list[tuple[str, tuple[Path, ...]]] = []

    def deterministic_handler(
        _question: str,
        _objective: str,
        sources: tuple[LocalDocumentAccessResult, ...],
        _output_dir: Path,
        _access_policy: object,
        _approval: object,
    ) -> int:
        calls.append(
            (
                "deterministic",
                tuple(result.resolved_path for result in sources),
            )
        )
        return 0

    def semantic_handler(
        _question: str,
        _objective: str,
        sources: tuple[LocalDocumentAccessResult, ...],
        _output_dir: Path,
        _access_policy: object,
        _approval: object,
    ) -> int:
        calls.append(
            (
                "semantic",
                tuple(result.resolved_path for result in sources),
            )
        )
        return 0

    arguments = [
        "research",
        "--question",
        "How does local HWPX research work?",
        "--source",
        str(source),
        "--allowed-root",
        str(tmp_path),
    ]
    if mode == "semantic":
        arguments[1:1] = [
            "--mode",
            "semantic",
            "--approve-external-send",
        ]

    result = main(
        arguments,
        research_handler=deterministic_handler,
        semantic_research_handler=semantic_handler,
    )

    assert result == 0
    assert calls == [(mode, (source.resolve(),))]


def test_main_reports_malformed_hwpx_through_local_handler(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "malformed.hwpx"
    source.write_bytes(b"not an HWPX package")

    result = main(
        [
            "research",
            "--question",
            "How does local HWPX research handle errors?",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
        ]
    )

    assert result == 2
    assert "not a valid ZIP archive" in capsys.readouterr().err


def test_main_runs_default_local_hwpx_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "grounded.hwpx"
    write_hwpx(
        source,
        sections={
            "Contents/section0.xml": (
                "Grounded HWPX research connects claims to evidence.",
            )
        },
    )
    output_dir = tmp_path / "hwpx-reports"

    result = main(
        [
            "research",
            "--question",
            "How does grounded HWPX research use evidence?",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    execution_dirs = list(output_dir.iterdir())
    assert result == 0
    assert captured.err == ""
    assert len(execution_dirs) == 1
    assert (execution_dirs[0] / "report.md").is_file()
    assert (execution_dirs[0] / "result.json").is_file()


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
            "--allowed-root",
            str(tmp_path),
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
            "--allowed-root",
            str(tmp_path),
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
    assert (execution_dirs[0] / "report.md").is_file()
    assert (execution_dirs[0] / "result.json").is_file()


def test_main_requires_allowed_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    calls: list[object] = []

    result = main(
        [
            "research",
            "--question",
            "How does allowed-root validation work?",
            "--source",
            str(source),
        ],
        research_handler=lambda *args: calls.append(args) or 0,
    )

    assert result == 2
    assert calls == []
    assert "at least one allowed root is required" in capsys.readouterr().err


def test_main_accepts_nested_source_inside_allowed_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    source = nested / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    captured: list[tuple[LocalDocumentAccessResult, ...]] = []

    def handler(
        _question: str,
        _objective: str,
        sources: tuple[LocalDocumentAccessResult, ...],
        _output_dir: Path,
        _access_policy: object,
        _approval: object,
    ) -> int:
        captured.append(sources)
        return 0

    result = main(
        [
            "research",
            "--question",
            "How does nested source validation work?",
            "--source",
            str(source),
            "--allowed-root",
            str(root),
        ],
        research_handler=handler,
    )

    assert result == 0
    assert captured[0][0].resolved_path == source.resolve()


@pytest.mark.parametrize("lookalike", [False, True])
def test_main_rejects_source_outside_root_before_handler(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    lookalike: bool,
) -> None:
    root = tmp_path / "data"
    outside = tmp_path / ("database" if lookalike else "outside")
    root.mkdir()
    outside.mkdir()
    source = outside / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    calls: list[object] = []

    result = main(
        [
            "research",
            "--question",
            "How does root containment validation work?",
            "--source",
            str(source),
            "--allowed-root",
            str(root),
        ],
        research_handler=lambda *args: calls.append(args) or 0,
    )

    assert result == 2
    assert calls == []
    assert "outside the allowed roots" in capsys.readouterr().err


def test_main_rejects_leaf_symlink_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    link = tmp_path / "source-link.txt"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("platform cannot create symlinks")

    result = main(
        [
            "research",
            "--question",
            "How does symlink source validation work?",
            "--source",
            str(link),
            "--allowed-root",
            str(tmp_path),
        ],
        research_handler=lambda *args: 0,
    )

    assert result == 2
    assert "must not be a symlink" in capsys.readouterr().err


def test_main_rejects_ancestor_symlink_escape(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    source = outside / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("platform cannot create symlinks")

    result = main(
        [
            "research",
            "--question",
            "How does ancestor symlink validation work?",
            "--source",
            str(link / source.name),
            "--allowed-root",
            str(root),
        ],
        research_handler=lambda *args: 0,
    )

    assert result == 2
    assert "outside the allowed roots" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("root_kind", "message"),
    [("missing", "exist and be readable"), ("file", "must be directories")],
)
def test_main_rejects_invalid_allowed_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    root_kind: str,
    message: str,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    root = tmp_path / root_kind
    if root_kind == "file":
        root.write_text("not a directory", encoding="utf-8")

    result = main(
        [
            "research",
            "--question",
            "How does allowed-root configuration work?",
            "--source",
            str(source),
            "--allowed-root",
            str(root),
        ],
        research_handler=lambda *args: 0,
    )

    assert result == 2
    assert message in capsys.readouterr().err


def test_main_rejects_duplicate_canonical_allowed_roots(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")

    result = main(
        [
            "research",
            "--question",
            "How does duplicate root validation work?",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
            "--allowed-root",
            str(tmp_path / "."),
        ],
        research_handler=lambda *args: 0,
    )

    assert result == 2
    assert "allowed roots must be unique" in capsys.readouterr().err


def test_main_rejects_oversize_source_before_handler(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"12345")
    calls: list[object] = []
    monkeypatch.setattr("app.cli.DEFAULT_MAXIMUM_LOCAL_SOURCE_BYTES", 4)

    result = main(
        [
            "research",
            "--question",
            "How does source size validation work?",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
        ],
        research_handler=lambda *args: calls.append(args) or 0,
    )

    assert result == 2
    assert calls == []
    assert "exceeds the maximum file size" in capsys.readouterr().err


def test_gate_rejection_does_not_call_local_document_adapter(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    source = tmp_path / "outside.txt"
    source.write_text("evidence", encoding="utf-8")
    adapter_calls: list[object] = []

    def fail_if_called(*args: object, **kwargs: object) -> object:
        adapter_calls.append((args, kwargs))
        raise AssertionError("adapter must not be called")

    monkeypatch.setattr(
        "app.research.local_document_adapter.LocalDocumentAdapter.load_validated",
        fail_if_called,
    )

    result = main(
        [
            "research",
            "--question",
            "How does pre-parse root validation work?",
            "--source",
            str(source),
            "--allowed-root",
            str(root),
        ]
    )

    assert result == 2
    assert adapter_calls == []
    assert "outside the allowed roots" in capsys.readouterr().err


def test_main_semantic_requires_external_send_approval(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("semantic evidence", encoding="utf-8")
    calls: list[object] = []

    result = main(
        [
            "research",
            "--mode",
            "semantic",
            "--question",
            "How does semantic approval work?",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
        ],
        semantic_research_handler=lambda *args: calls.append(args) or 0,
    )

    assert result == 2
    assert calls == []
    assert "explicit external-send approval is required" in capsys.readouterr().err


def test_main_semantic_approval_is_bound_to_validated_sources(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"semantic evidence")
    captured: list[tuple[object, ...]] = []

    result = main(
        [
            "research",
            "--mode",
            "semantic",
            "--approve-external-send",
            "--question",
            "How does semantic approval work?",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
        ],
        semantic_research_handler=lambda *args: captured.append(args) or 0,
    )

    assert result == 0
    access_results = captured[0][2]
    approval = captured[0][5]
    assert approval.approved is True
    assert approval.sources[0].resolved_path == source.resolve()
    assert approval.sources[0].content_sha256 == access_results[0].content_sha256
    assert approval.sources[0].file_size_bytes == len(b"semantic evidence")


def test_main_rejects_external_send_approval_in_deterministic_mode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("offline evidence", encoding="utf-8")

    result = main(
        [
            "research",
            "--approve-external-send",
            "--question",
            "How does deterministic research work?",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
        ],
        research_handler=lambda *args: 0,
    )

    assert result == 2
    assert "only valid with --mode semantic" in capsys.readouterr().err


def test_semantic_trust_failure_precedes_approval_and_handler(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    source = tmp_path / "outside.txt"
    source.write_text("semantic evidence", encoding="utf-8")
    calls: list[object] = []

    result = main(
        [
            "research",
            "--mode",
            "semantic",
            "--approve-external-send",
            "--question",
            "How does semantic trust validation work?",
            "--source",
            str(source),
            "--allowed-root",
            str(root),
        ],
        semantic_research_handler=lambda *args: calls.append(args) or 0,
    )

    assert result == 2
    assert calls == []
    assert "outside the allowed roots" in capsys.readouterr().err


def test_research_live_does_not_accept_external_send_approval() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "research-live",
                "--question",
                "How does live grounded research work?",
                "--approve-external-send",
            ]
        )


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
    assert captured["output_dir"] == (tmp_path / "live-reports").resolve()


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
    assert "maximum_bytes must be at least 1024" in captured.err


def test_parser_accepts_integrated_research_command(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("Integrated evidence.", encoding="utf-8")

    namespace = build_parser().parse_args(
        [
            "research-integrated",
            "--question",
            "How does integrated research work?",
            "--objective",
            "Explain federated Web and Local research.",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
            "--approve-external-send",
        ]
    )

    assert namespace.command == "research-integrated"
    assert namespace.maximum_sources == 3
    assert namespace.maximum_bytes == 1_000_000
    assert namespace.output_dir == "reports/integrated"
    assert not hasattr(namespace, "mode")


def test_integrated_command_passes_bound_approval_and_limits(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"Integrated evidence.")
    captured: dict[str, object] = {}

    def handler(*args):
        captured["args"] = args
        return 0

    result = main(
        [
            "research-integrated",
            "--question",
            "How does integrated research work?",
            "--objective",
            "Explain federated Web and Local research.",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
            "--approve-external-send",
            "--maximum-sources",
            "4",
            "--maximum-bytes",
            "2048",
            "--output-dir",
            str(tmp_path / "reports"),
        ],
        integrated_research_handler=handler,
    )

    assert result == 0
    args = captured["args"]
    access_result = args[2][0]
    approval = args[7]
    assert access_result.resolved_path == source.resolve()
    assert approval.purpose == "integrated_web_local_research"
    assert approval.sources[0].content_sha256 == access_result.content_sha256
    assert args[3:5] == (4, 2048)


def test_integrated_command_requires_approval_flag(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("Integrated evidence.", encoding="utf-8")

    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "research-integrated",
                "--question",
                "How does integrated research work?",
                "--objective",
                "Explain federated Web and Local research.",
                "--source",
                str(source),
                "--allowed-root",
                str(tmp_path),
            ]
        )


def test_integrated_command_rejects_out_of_root_before_handler(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    source = outside / "source.txt"
    source.write_text("Integrated evidence.", encoding="utf-8")
    calls: list[object] = []

    result = main(
        [
            "research-integrated",
            "--question",
            "How does integrated research work?",
            "--objective",
            "Explain federated Web and Local research.",
            "--source",
            str(source),
            "--allowed-root",
            str(allowed),
            "--approve-external-send",
        ],
        integrated_research_handler=lambda *args: calls.append(args) or 0,
    )

    assert result == 2
    assert calls == []
    assert "outside the allowed roots" in capsys.readouterr().err


def test_integrated_command_rejects_leaf_symlink_before_handler(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("Integrated evidence.", encoding="utf-8")
    source = tmp_path / "source.txt"
    try:
        source.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable")
    calls: list[object] = []

    result = main(
        [
            "research-integrated",
            "--question",
            "How does integrated research work?",
            "--objective",
            "Explain federated Web and Local research.",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
            "--approve-external-send",
        ],
        integrated_research_handler=lambda *args: calls.append(args) or 0,
    )

    assert result == 2
    assert calls == []
    assert "must not be a symlink" in capsys.readouterr().err


def test_integrated_command_enforces_raw_size_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"four")
    monkeypatch.setattr("app.cli.DEFAULT_MAXIMUM_LOCAL_SOURCE_BYTES", 3)
    calls: list[object] = []

    result = main(
        [
            "research-integrated",
            "--question",
            "How does integrated research work?",
            "--objective",
            "Explain federated Web and Local research.",
            "--source",
            str(source),
            "--allowed-root",
            str(tmp_path),
            "--approve-external-send",
        ],
        integrated_research_handler=lambda *args: calls.append(args) or 0,
    )

    assert result == 2
    assert calls == []
    assert "maximum file size" in capsys.readouterr().err


def test_parser_accepts_patent_research_command() -> None:
    namespace = build_parser().parse_args(
        [
            "research-patent",
            "--question",
            "How do pressure sensors detect seat occupancy?",
        ]
    )
    assert namespace.command == "research-patent"
    assert namespace.maximum_search_results == 8
    assert namespace.maximum_sources == 4
    assert namespace.maximum_bytes == 1_000_000


def test_main_calls_injected_patent_research_handler() -> None:
    captured: list[PatentResearchRequest] = []
    result = main(
        [
            "research-patent",
            "--question",
            "How do pressure sensors detect seat occupancy?",
            "--objective",
            "Identify technically relevant patent publications.",
            "--prior-art-cutoff-date",
            "2026-08-18",
            "--maximum-search-results",
            "2",
            "--maximum-sources",
            "1",
            "--maximum-bytes",
            "2048",
        ],
        patent_research_handler=lambda request: captured.append(request) or 0,
    )
    assert result == 0
    request = captured[0]
    assert request.prior_art_cutoff_date == date(2026, 8, 18)
    assert request.maximum_search_results == 2
    assert request.maximum_sources == 1
    assert request.maximum_bytes == 2048


def test_patent_research_rejects_invalid_cutoff_before_handler(capsys) -> None:
    calls: list[object] = []
    result = main(
        [
            "research-patent",
            "--question",
            "How do pressure sensors detect seat occupancy?",
            "--prior-art-cutoff-date",
            "2026/08/18",
        ],
        patent_research_handler=lambda request: calls.append(request) or 0,
    )
    assert result == 2
    assert calls == []
    assert "must use YYYY-MM-DD format" in capsys.readouterr().err


def test_patent_research_rejects_source_bound_violation(capsys) -> None:
    calls: list[object] = []
    result = main(
        [
            "research-patent",
            "--question",
            "How do pressure sensors detect seat occupancy?",
            "--maximum-search-results",
            "1",
            "--maximum-sources",
            "2",
        ],
        patent_research_handler=lambda request: calls.append(request) or 0,
    )
    assert result == 2
    assert calls == []
    error_output = capsys.readouterr().err
    assert error_output == (
        "aira: error: maximum_sources must not exceed maximum_search_results\n"
    )
    assert "validation error for PatentResearchRequest" not in error_output
    assert "pydantic.dev" not in error_output
