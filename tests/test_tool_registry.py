"""Tests for the planning-agent tool registry."""

import pytest

from app.schemas.tool_execution import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from app.tools.planning_tool_registry import (
    ToolRegistry,
    ToolRegistryError,
)
from app.tools.tool import Tool


class FakeTool(Tool):
    """Simple deterministic test tool."""

    def __init__(
        self,
        name: str,
    ) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def execute(
        self,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolExecutionStatus.SUCCEEDED,
            output=request.arguments,
        )


def test_registry_registers_and_retrieves_tool() -> None:
    registry = ToolRegistry()
    tool = FakeTool("python")

    registry.register(tool)

    assert registry.get("python") is tool
    assert registry.contains("python") is True
    assert registry.count() == 1


def test_registry_rejects_duplicate_name() -> None:
    registry = ToolRegistry()
    registry.register(FakeTool("python"))

    with pytest.raises(
        ToolRegistryError,
        match="already registered",
    ):
        registry.register(FakeTool("python"))


def test_registry_requires_registered_tool() -> None:
    registry = ToolRegistry()

    with pytest.raises(
        ToolRegistryError,
        match="not registered",
    ):
        registry.require("missing")


def test_registry_returns_sorted_names() -> None:
    registry = ToolRegistry()
    registry.register(FakeTool("pytest"))
    registry.register(FakeTool("python"))

    assert registry.names() == [
        "pytest",
        "python",
    ]


def test_registry_unregisters_tool() -> None:
    registry = ToolRegistry()
    tool = FakeTool("python")
    registry.register(tool)

    removed = registry.unregister("python")

    assert removed is tool
    assert registry.count() == 0


def test_registry_rejects_blank_name() -> None:
    registry = ToolRegistry()

    with pytest.raises(
        ToolRegistryError,
        match="must not be blank",
    ):
        registry.get(" ")
