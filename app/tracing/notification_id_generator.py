"""Identifier generation for trace alert notifications."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4


class NotificationIdGenerator(ABC):
    """Generate identifiers for delivered notifications."""

    @abstractmethod
    def generate(self) -> str:
        """Return one new notification identifier."""


class UUIDNotificationIdGenerator(
    NotificationIdGenerator
):
    """Generate notification identifiers using UUID4."""

    def generate(self) -> str:
        """Return one UUID-backed notification identifier."""

        return f"notification-{uuid4()}"
