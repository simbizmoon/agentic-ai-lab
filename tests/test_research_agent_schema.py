"""Tests for research-agent identity and role schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
    ResearchAgentStatus,
)


def identity(
    **overrides: object,
) -> ResearchAgentIdentity:
    """Return one valid research-agent identity."""

    values: dict[str, object] = {
        "agent_id": "agent-search-001",
        "name": "Search Specialist",
        "role": ResearchAgentRole.SEARCH_SPECIALIST,
        "description": (
            "Finds relevant research source candidates."
        ),
        "status": ResearchAgentStatus.AVAILABLE,
        "version": "1.0",
        "tags": [
            "research",
            "search",
        ],
        "metadata": {
            "team": "research",
        },
    }
    values.update(overrides)

    return ResearchAgentIdentity.model_validate(
        values
    )


def test_identity_accepts_valid_values() -> None:
    value = identity()

    assert value.agent_id == "agent-search-001"
    assert value.role is (
        ResearchAgentRole.SEARCH_SPECIALIST
    )
    assert value.is_available is True


@pytest.mark.parametrize(
    "field_name",
    [
        "agent_id",
        "name",
        "description",
        "version",
    ],
)
def test_identity_rejects_blank_required_text(
    field_name: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        identity(**{field_name: " "})


def test_identity_rejects_blank_tag() -> None:
    with pytest.raises(
        ValidationError,
        match="tags must not contain blank values",
    ):
        identity(tags=["research", " "])


def test_identity_rejects_duplicate_tags() -> None:
    with pytest.raises(
        ValidationError,
        match="tags must not contain duplicates",
    ):
        identity(
            tags=[
                "research",
                " RESEARCH ",
            ]
        )


def test_identity_rejects_blank_metadata_key() -> None:
    with pytest.raises(
        ValidationError,
        match="metadata keys must not be blank",
    ):
        identity(
            metadata={
                " ": "value",
            }
        )


def test_identity_rejects_blank_metadata_value() -> None:
    with pytest.raises(
        ValidationError,
        match="metadata values must not be blank",
    ):
        identity(
            metadata={
                "team": " ",
            }
        )


def test_identity_reports_unavailable_status() -> None:
    value = identity(
        status=ResearchAgentStatus.BUSY
    )

    assert value.is_available is False


def test_identity_checks_role() -> None:
    value = identity()

    assert value.has_role(
        ResearchAgentRole.SEARCH_SPECIALIST
    )
    assert not value.has_role(
        ResearchAgentRole.QUALITY_REVIEWER
    )


def test_identity_is_frozen() -> None:
    value = identity()

    with pytest.raises(ValidationError):
        value.name = "Changed"
