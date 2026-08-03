"""Tests for retrieval vector mathematics."""

import math

import pytest

from app.rag.vector_math import (
    VectorMathError,
    cosine_similarity,
)


def test_identical_vectors_have_similarity_one() -> None:
    score = cosine_similarity(
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 3.0],
    )

    assert score == pytest.approx(1.0)


def test_orthogonal_vectors_have_similarity_zero() -> None:
    score = cosine_similarity(
        [1.0, 0.0],
        [0.0, 1.0],
    )

    assert score == pytest.approx(0.0)


def test_opposite_vectors_have_similarity_negative_one() -> None:
    score = cosine_similarity(
        [1.0, 0.0],
        [-1.0, 0.0],
    )

    assert score == pytest.approx(-1.0)


def test_similarity_is_scale_independent() -> None:
    score = cosine_similarity(
        [1.0, 2.0],
        [10.0, 20.0],
    )

    assert score == pytest.approx(1.0)


def test_similarity_is_symmetric() -> None:
    first = [1.0, 2.0, 3.0]
    second = [3.0, 2.0, 1.0]

    assert cosine_similarity(
        first,
        second,
    ) == pytest.approx(
        cosine_similarity(
            second,
            first,
        )
    )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ([], [1.0]),
        ([1.0], []),
        ([1.0], [1.0, 2.0]),
        ([0.0, 0.0], [1.0, 0.0]),
        ([1.0, 0.0], [0.0, 0.0]),
        ([math.inf], [1.0]),
        ([1.0], [math.nan]),
    ],
)
def test_invalid_vectors_are_rejected(
    first: list[float],
    second: list[float],
) -> None:
    with pytest.raises(VectorMathError):
        cosine_similarity(first, second)
