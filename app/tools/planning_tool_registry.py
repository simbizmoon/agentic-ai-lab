"""Object registry for tools available to planning agents."""

from __future__ import annotations

from app.tools.tool import Tool


class ToolRegistryError(RuntimeError):
    """Raised when tool registry operations are invalid."""


class ToolRegistry:
    """Register and retrieve tools by stable name."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        tool: Tool,
    ) -> None:
        """Register one tool."""

        name = self._validated_name(tool.name)

        if name in self._tools:
            raise ToolRegistryError(
                f"tool is already registered: {name}"
            )

        self._tools[name] = tool

    def unregister(
        self,
        name: str,
    ) -> Tool:
        """Remove and return one registered tool."""

        normalized_name = self._validated_name(name)

        try:
            return self._tools.pop(normalized_name)
        except KeyError as exc:
            raise ToolRegistryError(
                f"tool is not registered: "
                f"{normalized_name}"
            ) from exc

    def get(
        self,
        name: str,
    ) -> Tool | None:
        """Return one registered tool or None."""

        normalized_name = self._validated_name(name)

        return self._tools.get(normalized_name)

    def require(
        self,
        name: str,
    ) -> Tool:
        """Return one registered tool or raise."""

        normalized_name = self._validated_name(name)
        tool = self._tools.get(normalized_name)

        if tool is None:
            raise ToolRegistryError(
                f"tool is not registered: "
                f"{normalized_name}"
            )

        return tool

    def contains(
        self,
        name: str,
    ) -> bool:
        """Return whether a tool is registered."""

        normalized_name = self._validated_name(name)

        return normalized_name in self._tools

    def names(self) -> list[str]:
        """Return registered tool names in sorted order."""

        return sorted(self._tools)

    def count(self) -> int:
        """Return the number of registered tools."""

        return len(self._tools)

    @staticmethod
    def _validated_name(
        name: str,
    ) -> str:
        """Validate and normalize one tool name."""

        normalized_name = name.strip()

        if not normalized_name:
            raise ToolRegistryError(
                "tool name must not be blank"
            )

        return normalized_name
