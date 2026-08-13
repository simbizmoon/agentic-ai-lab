"""Tests for live source-reading concurrency settings."""

from __future__ import annotations

import pytest

from app.research.live_runtime import (
    DEFAULT_SOURCE_READ_CONCURRENCY,
    MAX_SOURCE_READ_CONCURRENCY,
    MIN_SOURCE_READ_CONCURRENCY,
    SOURCE_READ_CONCURRENCY_ENV,
    resolve_source_read_concurrency,
)


def test_source_read_concurrency_defaults_to_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        SOURCE_READ_CONCURRENCY_ENV,
        raising=False,
    )

    assert (
        resolve_source_read_concurrency()
        == DEFAULT_SOURCE_READ_CONCURRENCY
        == 2
    )


@pytest.mark.parametrize(
    "value",
    [
        MIN_SOURCE_READ_CONCURRENCY,
        2,
        4,
        MAX_SOURCE_READ_CONCURRENCY,
    ],
)
def test_source_read_concurrency_accepts_bounded_values(
    monkeypatch: pytest.MonkeyPatch,
    value: int,
) -> None:
    monkeypatch.setenv(
        SOURCE_READ_CONCURRENCY_ENV,
        str(value),
    )

    assert resolve_source_read_concurrency() == value


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "must not be blank"),
        ("two", "must be an integer"),
        ("0", "must be between"),
        ("9", "must be between"),
    ],
)
def test_source_read_concurrency_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(
        SOURCE_READ_CONCURRENCY_ENV,
        value,
    )

    with pytest.raises(RuntimeError, match=message):
        resolve_source_read_concurrency()
