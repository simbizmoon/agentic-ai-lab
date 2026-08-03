"""Base interface for tools used by planning agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.tool_execution import (
    ToolExecutionRequest,
    ToolExecutionResult,
)


class ToolExecutionError(RuntimeError):
    """Raised when a tool cannot complete its execution."""


class Tool(ABC):
    """Abstract executable tool."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable tool name."""

    @abstractmethod
    def execute(
        self,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResult:
        """Execute one tool request."""
