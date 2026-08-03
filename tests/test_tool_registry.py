"""Tests for the explicit local Tool registry."""

from app.tools.document_statistics import (
    DocumentStatisticsInput,
    get_document_statistics,
)
from app.tools.document_statistics_schema import (
    DOCUMENT_STATISTICS_TOOL,
)
from app.tools.tool_registry import (
    TOOL_REGISTRY,
    get_allowed_tool,
)


def test_document_statistics_tool_is_registered() -> None:
    definition = get_allowed_tool(
        "get_document_statistics"
    )

    assert definition is not None
    assert definition.name == "get_document_statistics"
    assert definition.input_model is DocumentStatisticsInput
    assert definition.executor is get_document_statistics
    assert definition.schema is DOCUMENT_STATISTICS_TOOL


def test_document_statistics_tool_is_read_only() -> None:
    definition = TOOL_REGISTRY[
        "get_document_statistics"
    ]

    assert definition.read_only is True
    assert definition.requires_approval is False


def test_unknown_tool_is_not_registered() -> None:
    assert get_allowed_tool("delete_all_files") is None


def test_registry_contains_only_explicitly_allowed_tools() -> None:
    assert set(TOOL_REGISTRY) == {
        "get_document_statistics",
        "extract_document_keywords",
    }


def test_registry_rejects_empty_tool_name() -> None:
    import pytest
    from pydantic import BaseModel

    from app.tools.tool_registry import ToolDefinition

    class FakeInput(BaseModel):
        value: str

    class FakeOutput(BaseModel):
        value: str

    def executor(tool_input: BaseModel) -> BaseModel:
        return FakeOutput(value="ok")

    with pytest.raises(
        ValueError,
        match="tool name must not be empty",
    ):
        ToolDefinition(
            name="   ",
            input_model=FakeInput,
            executor=executor,
            schema={
                "type": "function",
                "name": "   ",
                "parameters": {},
            },
            read_only=True,
            requires_approval=False,
        )


def test_registry_rejects_schema_name_mismatch() -> None:
    import pytest
    from pydantic import BaseModel

    from app.tools.tool_registry import ToolDefinition

    class FakeInput(BaseModel):
        value: str

    class FakeOutput(BaseModel):
        value: str

    def executor(tool_input: BaseModel) -> BaseModel:
        return FakeOutput(value="ok")

    with pytest.raises(
        ValueError,
        match="schema name must match",
    ):
        ToolDefinition(
            name="safe_tool",
            input_model=FakeInput,
            executor=executor,
            schema={
                "type": "function",
                "name": "different_tool",
                "parameters": {},
            },
            read_only=True,
            requires_approval=False,
        )


def test_registry_rejects_unapproved_state_changing_tool() -> None:
    import pytest
    from pydantic import BaseModel

    from app.tools.tool_registry import ToolDefinition

    class FakeInput(BaseModel):
        value: str

    class FakeOutput(BaseModel):
        value: str

    def executor(tool_input: BaseModel) -> BaseModel:
        return FakeOutput(value="ok")

    with pytest.raises(
        ValueError,
        match="state-changing tools must require human approval",
    ):
        ToolDefinition(
            name="dangerous_tool",
            input_model=FakeInput,
            executor=executor,
            schema={
                "type": "function",
                "name": "dangerous_tool",
                "parameters": {},
            },
            read_only=False,
            requires_approval=False,
        )


def test_registry_accepts_approved_state_changing_tool() -> None:
    from pydantic import BaseModel

    from app.tools.tool_registry import ToolDefinition

    class FakeInput(BaseModel):
        value: str

    class FakeOutput(BaseModel):
        value: str

    def executor(tool_input: BaseModel) -> BaseModel:
        return FakeOutput(value="ok")

    definition = ToolDefinition(
        name="approved_change_tool",
        input_model=FakeInput,
        executor=executor,
        schema={
            "type": "function",
            "name": "approved_change_tool",
            "parameters": {},
        },
        read_only=False,
        requires_approval=True,
    )

    assert definition.read_only is False
    assert definition.requires_approval is True


def test_allowed_tool_schemas_come_from_registry() -> None:
    from app.tools.tool_registry import (
        get_allowed_tool_schemas,
    )

    schemas = get_allowed_tool_schemas()

    from app.tools.document_keywords_schema import (
        DOCUMENT_KEYWORDS_TOOL,
    )

    assert schemas == [
        DOCUMENT_STATISTICS_TOOL,
        DOCUMENT_KEYWORDS_TOOL,
    ]


def test_allowed_tool_schema_names_match_registry_keys() -> None:
    from app.tools.tool_registry import (
        get_allowed_tool_schemas,
    )

    schema_names = {
        schema["name"]
        for schema in get_allowed_tool_schemas()
    }

    assert schema_names == set(TOOL_REGISTRY)


def test_document_keywords_tool_is_registered() -> None:
    from app.tools.document_keywords import (
        DocumentKeywordsInput,
        extract_document_keywords,
    )
    from app.tools.document_keywords_schema import (
        DOCUMENT_KEYWORDS_TOOL,
    )

    definition = get_allowed_tool(
        "extract_document_keywords"
    )

    assert definition is not None
    assert definition.input_model is DocumentKeywordsInput
    assert definition.executor is extract_document_keywords
    assert definition.schema is DOCUMENT_KEYWORDS_TOOL
    assert definition.read_only is True
    assert definition.requires_approval is False
