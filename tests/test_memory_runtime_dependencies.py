"""Tests for memory service runtime dependencies."""

from datetime import UTC

from app.memory.clock import SystemClock
from app.memory.memory_id_generator import (
    UuidMemoryIdGenerator,
)


def test_system_clock_returns_utc_datetime() -> None:
    value = SystemClock().now()

    assert value.tzinfo is not None
    assert value.utcoffset() == UTC.utcoffset(value)


def test_uuid_generator_returns_prefixed_unique_ids() -> None:
    generator = UuidMemoryIdGenerator()

    first = generator.generate()
    second = generator.generate()

    assert first.startswith("mem-")
    assert second.startswith("mem-")
    assert first != second
