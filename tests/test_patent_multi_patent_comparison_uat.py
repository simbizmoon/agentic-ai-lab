"""Scripted offline UAT for the patent comparison CLI boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cli import main


def _valid_arguments(output_dir: Path) -> list[str]:
    return [
        "research-patent-compare",
        "--target-publication",
        "EP1000000B1",
        "--comparison-publication",
        "EP2000000A1",
        "--comparison-publication",
        "EP3000000A1",
        "--output-dir",
        str(output_dir),
    ]


def test_uat_help_explains_identity_repetition_defaults_cost_and_scope(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["research-patent-compare", "--help"])

    assert raised.value.code == 0
    output = capsys.readouterr().out
    normalized = " ".join(output.split())
    assert "Exact EP publication with kind code" in normalized
    assert "repeat this option 2 to 4 times" in normalized
    assert (
        "maximum claim elements multiplied by comparison publication count"
        in normalized
    )
    assert "(default: EN)" in normalized
    assert "(default: 2)" in normalized
    assert "Markdown and JSON artifacts" in normalized
    assert "does not make patent-law conclusions or rank patents" in normalized


def test_uat_one_comparison_has_actionable_error_before_provider(capsys) -> None:
    provider_calls: list[object] = []
    value = main(
        [
            "research-patent-compare",
            "--target-publication",
            "EP1000000B1",
            "--comparison-publication",
            "EP2000000A1",
        ],
        patent_comparison_handler=lambda *values: provider_calls.append(values) or 0,
    )

    assert value == 2
    assert provider_calls == []
    error = capsys.readouterr().err
    assert "at least 2 --comparison-publication values are required" in error
    assert "repeat the option" in error
    assert "Tuple" not in error
    assert "validation error" not in error


def test_uat_invalid_publication_has_domain_error_before_provider(capsys) -> None:
    provider_calls: list[object] = []
    arguments = _valid_arguments(Path("reports/patent-comparisons"))
    arguments[arguments.index("EP1000000B1")] = "NOT-A-PATENT"

    value = main(
        arguments,
        patent_comparison_handler=lambda *values: provider_calls.append(values) or 0,
    )

    assert value == 2
    assert provider_calls == []
    error = capsys.readouterr().err
    assert "requires an EP publication with kind code" in error
    assert "validation error" not in error


def test_uat_budget_overflow_explains_bound_before_provider(
    tmp_path: Path,
    capsys,
) -> None:
    provider_calls: list[object] = []
    arguments = _valid_arguments(tmp_path)
    arguments.extend(["--maximum-claim-elements", "2"])

    value = main(
        arguments,
        patent_comparison_handler=lambda *values: provider_calls.append(values) or 0,
    )

    assert value == 2
    assert provider_calls == []
    assert (
        "planned element/evidence pairs exceed maximum_mapping_calls"
        in capsys.readouterr().err
    )


def test_uat_valid_request_reaches_injected_handler_with_default_bounds(
    tmp_path: Path,
) -> None:
    calls: list[tuple[object, Path]] = []

    value = main(
        _valid_arguments(tmp_path),
        patent_comparison_handler=lambda request, output_dir: (
            calls.append((request, output_dir)) or 0
        ),
    )

    assert value == 0
    request, output_dir = calls[0]
    assert request.planned_maximum_mapping_calls == 2
    assert request.maximum_mapping_calls == 2
    assert output_dir == tmp_path.resolve()
