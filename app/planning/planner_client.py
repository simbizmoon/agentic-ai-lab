"""Interfaces for structured agent planner clients."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planner_client_result import (
    PlannerClientResult,
)
from app.schemas.planner_prompt import PlannerPrompt


class PlannerClientError(RuntimeError):
    """Raised when a planner client cannot return valid output."""


class PlannerClient(ABC):
    """Abstract client for structured planner models."""

    @abstractmethod
    def create_plan(
        self,
        *,
        request: PlanCreationRequest,
        prompt: PlannerPrompt,
    ) -> PlannerClientResult:
        """Generate and validate one structured plan draft."""
