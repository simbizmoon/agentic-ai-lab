"""Tests for agent plan ID generation."""

from app.planning.plan_id_generator import (
    UuidPlanIdGenerator,
)


def test_uuid_generator_returns_prefixed_unique_ids() -> None:
    generator = UuidPlanIdGenerator()

    first = generator.generate()
    second = generator.generate()

    assert first.startswith("plan-")
    assert second.startswith("plan-")
    assert first != second
