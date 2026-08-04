"""Application execution lifecycle transition rules."""

from __future__ import annotations

from typing import ClassVar

from app.application.execution_record import (
    ApplicationExecutionStatus,
)


class ApplicationExecutionTransitionPolicy:
    """Validate persistent execution status transitions."""

    _ALLOWED_TRANSITIONS: ClassVar[
        dict[
            ApplicationExecutionStatus,
            set[ApplicationExecutionStatus],
        ]
    ] = {
        ApplicationExecutionStatus.PENDING: {
            ApplicationExecutionStatus.QUEUED,
            ApplicationExecutionStatus.RUNNING,
            ApplicationExecutionStatus
            .CANCELLATION_REQUESTED,
            ApplicationExecutionStatus.CANCELLED,
        },
        ApplicationExecutionStatus.QUEUED: {
            ApplicationExecutionStatus.RUNNING,
            ApplicationExecutionStatus
            .CANCELLATION_REQUESTED,
            ApplicationExecutionStatus.CANCELLED,
            ApplicationExecutionStatus.TIMED_OUT,
        },
        ApplicationExecutionStatus.RUNNING: {
            ApplicationExecutionStatus.SUCCEEDED,
            ApplicationExecutionStatus.FAILED,
            ApplicationExecutionStatus
            .CANCELLATION_REQUESTED,
            ApplicationExecutionStatus.CANCELLED,
            ApplicationExecutionStatus.TIMED_OUT,
        },
        ApplicationExecutionStatus.CANCELLATION_REQUESTED: {
            ApplicationExecutionStatus.CANCELLED,
            ApplicationExecutionStatus.SUCCEEDED,
            ApplicationExecutionStatus.FAILED,
            ApplicationExecutionStatus.TIMED_OUT,
        },
        ApplicationExecutionStatus.SUCCEEDED: set(),
        ApplicationExecutionStatus.FAILED: set(),
        ApplicationExecutionStatus.CANCELLED: set(),
        ApplicationExecutionStatus.TIMED_OUT: set(),
    }

    @classmethod
    def can_transition(
        cls,
        *,
        current: ApplicationExecutionStatus,
        target: ApplicationExecutionStatus,
    ) -> bool:
        """Return whether one status transition is permitted."""

        return target in cls._ALLOWED_TRANSITIONS[current]

    @classmethod
    def require_transition(
        cls,
        *,
        current: ApplicationExecutionStatus,
        target: ApplicationExecutionStatus,
    ) -> None:
        """Raise when a status transition is not permitted."""

        if not cls.can_transition(
            current=current,
            target=target,
        ):
            raise ValueError(
                "execution status transition is not allowed: "
                f"{current.value} -> {target.value}"
            )
