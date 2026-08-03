"""ID generation abstractions for agent plans."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4


class PlanIdGenerator(ABC):
    """Abstract generator for unique plan IDs."""

    @abstractmethod
    def generate(self) -> str:
        """Return one new plan ID."""


class UuidPlanIdGenerator(PlanIdGenerator):
    """Generate plan IDs using UUID version 4."""

    def generate(self) -> str:
        """Return one prefixed UUID plan ID."""

        return f"plan-{uuid4()}"
