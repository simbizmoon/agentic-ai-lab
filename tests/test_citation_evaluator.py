"""Tests for deterministic citation evaluation."""

import pytest

from app.rag.citation_evaluator import (
    evaluate_citations,
)


def test_exact_citation_match_passes() -> None:
    result = evaluate_citations(
        expected_citation_ids=["S1", "S2"],
        cited_ids=["S1", "S2"],
    )

    assert result.matched_ids == ["S1", "S2"]
    assert result.missing_ids == []
    assert result.unexpected_ids == []
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.passed is True


def test_missing_citation_reduces_recall() -> None:
    result = evaluate_citations(
        expected_citation_ids=["S1", "S2"],
        cited_ids=["S1"],
    )

    assert result.missing_ids == ["S2"]
    assert result.precision == 1.0
    assert result.recall == 0.5
    assert result.passed is False


def test_unexpected_citation_reduces_precision() -> None:
    result = evaluate_citations(
        expected_citation_ids=["S1"],
        cited_ids=["S1", "S9"],
    )

    assert result.unexpected_ids == ["S9"]
    assert result.precision == pytest.approx(0.5)
    assert result.recall == 1.0
    assert result.passed is False


def test_no_expected_and_no_cited_passes() -> None:
    result = evaluate_citations(
        expected_citation_ids=[],
        cited_ids=[],
    )

    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.passed is True


def test_expected_but_no_cited_fails() -> None:
    result = evaluate_citations(
        expected_citation_ids=["S1"],
        cited_ids=[],
    )

    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.missing_ids == ["S1"]
    assert result.passed is False


def test_no_expected_but_cited_fails() -> None:
    result = evaluate_citations(
        expected_citation_ids=[],
        cited_ids=["S1"],
    )

    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.unexpected_ids == ["S1"]
    assert result.passed is False


def test_duplicate_input_ids_are_normalized() -> None:
    result = evaluate_citations(
        expected_citation_ids=["S1", "S1"],
        cited_ids=["S1", "S1"],
    )

    assert result.expected_citation_ids == ["S1"]
    assert result.cited_ids == ["S1"]
    assert result.passed is True
