"""Vector mathematics for retrieval workflows."""

from __future__ import annotations

import math
from collections.abc import Sequence


class VectorMathError(ValueError):
    """Raised when vector operations receive invalid input."""


def cosine_similarity(
    first: Sequence[float],
    second: Sequence[float],
) -> float:
    """Return cosine similarity between two numeric vectors."""

    if not first or not second:
        raise VectorMathError(
            "vectors must not be empty"
        )

    if len(first) != len(second):
        raise VectorMathError(
            "vectors must have matching dimensions"
        )

    if not all(math.isfinite(value) for value in first):
        raise VectorMathError(
            "first vector values must be finite"
        )

    if not all(math.isfinite(value) for value in second):
        raise VectorMathError(
            "second vector values must be finite"
        )

    first_magnitude = math.sqrt(
        sum(value * value for value in first)
    )
    second_magnitude = math.sqrt(
        sum(value * value for value in second)
    )

    if first_magnitude == 0:
        raise VectorMathError(
            "first vector must have nonzero magnitude"
        )

    if second_magnitude == 0:
        raise VectorMathError(
            "second vector must have nonzero magnitude"
        )

    dot_product = sum(
        first_value * second_value
        for first_value, second_value in zip(
            first,
            second,
            strict=True,
        )
    )

    similarity = dot_product / (
        first_magnitude * second_magnitude
    )

    return max(-1.0, min(1.0, similarity))
