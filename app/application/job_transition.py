"""Background job lifecycle transition rules."""

from __future__ import annotations

from typing import ClassVar

from app.application.job_record import (
    ApplicationJobStatus,
)


class ApplicationJobTransitionPolicy:
    """Validate background-job status transitions."""

    _ALLOWED_TRANSITIONS: ClassVar[
        dict[
            ApplicationJobStatus,
            set[ApplicationJobStatus],
        ]
    ] = {
        ApplicationJobStatus.PENDING: {
            ApplicationJobStatus.SCHEDULED,
            ApplicationJobStatus.QUEUED,
            ApplicationJobStatus.CANCELLATION_REQUESTED,
            ApplicationJobStatus.CANCELLED,
        },
        ApplicationJobStatus.SCHEDULED: {
            ApplicationJobStatus.QUEUED,
            ApplicationJobStatus.CANCELLATION_REQUESTED,
            ApplicationJobStatus.CANCELLED,
        },
        ApplicationJobStatus.QUEUED: {
            ApplicationJobStatus.LEASED,
            ApplicationJobStatus.CANCELLATION_REQUESTED,
            ApplicationJobStatus.CANCELLED,
        },
        ApplicationJobStatus.LEASED: {
            ApplicationJobStatus.RUNNING,
            ApplicationJobStatus.QUEUED,
            ApplicationJobStatus.FAILED,
            ApplicationJobStatus.CANCELLATION_REQUESTED,
            ApplicationJobStatus.CANCELLED,
        },
        ApplicationJobStatus.RUNNING: {
            ApplicationJobStatus.SUCCEEDED,
            ApplicationJobStatus.FAILED,
            ApplicationJobStatus.RETRY_SCHEDULED,
            ApplicationJobStatus.CANCELLATION_REQUESTED,
            ApplicationJobStatus.CANCELLED,
            ApplicationJobStatus.DEAD_LETTERED,
        },
        ApplicationJobStatus.RETRY_SCHEDULED: {
            ApplicationJobStatus.QUEUED,
            ApplicationJobStatus.CANCELLATION_REQUESTED,
            ApplicationJobStatus.CANCELLED,
        },
        ApplicationJobStatus.CANCELLATION_REQUESTED: {
            ApplicationJobStatus.CANCELLED,
            ApplicationJobStatus.SUCCEEDED,
            ApplicationJobStatus.FAILED,
            ApplicationJobStatus.DEAD_LETTERED,
        },
        ApplicationJobStatus.SUCCEEDED: set(),
        ApplicationJobStatus.FAILED: set(),
        ApplicationJobStatus.CANCELLED: set(),
        ApplicationJobStatus.DEAD_LETTERED: set(),
    }

    @classmethod
    def can_transition(
        cls,
        *,
        current: ApplicationJobStatus,
        target: ApplicationJobStatus,
    ) -> bool:
        """Return whether one transition is allowed."""

        return target in cls._ALLOWED_TRANSITIONS[current]

    @classmethod
    def require_transition(
        cls,
        *,
        current: ApplicationJobStatus,
        target: ApplicationJobStatus,
    ) -> None:
        """Raise when the transition is forbidden."""

        if not cls.can_transition(
            current=current,
            target=target,
        ):
            raise ValueError(
                "job status transition is not allowed: "
                f"{current.value} -> {target.value}"
            )
