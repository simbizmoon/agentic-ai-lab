"""Errors raised by research-agent message bus implementations."""

from __future__ import annotations


class ResearchAgentMessageBusError(ValueError):
    """Base error raised by a research-agent message bus."""


class ResearchAgentMessageAlreadyExistsError(
    ResearchAgentMessageBusError
):
    """Raised when a message ID has already been published."""


class ResearchAgentMessageNotFoundError(
    ResearchAgentMessageBusError
):
    """Raised when a requested message does not exist."""


class ResearchAgentDeliveryNotFoundError(
    ResearchAgentMessageBusError
):
    """Raised when a requested delivery does not exist."""


class ResearchAgentDeliveryAccessError(
    ResearchAgentMessageBusError
):
    """Raised when an agent cannot access a delivery."""


class ResearchAgentDeliveryStateError(
    ResearchAgentMessageBusError
):
    """Raised when a delivery state transition is invalid."""
