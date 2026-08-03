"""ID generation abstractions for agent memories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4


class MemoryIdGenerator(ABC):
    """Abstract generator for unique memory IDs."""

    @abstractmethod
    def generate(self) -> str:
        """Return one new memory ID."""


class UuidMemoryIdGenerator(MemoryIdGenerator):
    """Generate memory IDs using UUID version 4."""

    def generate(self) -> str:
        """Return one prefixed UUID memory ID."""

        return f"mem-{uuid4()}"
