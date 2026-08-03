"""Schemas for agent trace alert notification delivery."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlert,
)


class AgentTraceAlertNotificationStatus(StrEnum):
    """Outcome of one alert notification attempt."""

    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


class AgentTraceAlertNotificationRequest(BaseModel):
    """Request to deliver one maintenance alert."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    alert: AgentTraceMaintenanceAlert
    channel: str
    destination: str
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> AgentTraceAlertNotificationRequest:
        """Validate delivery target values."""

        if not self.channel.strip():
            raise ValueError(
                "channel must not be blank"
            )

        if not self.destination.strip():
            raise ValueError(
                "destination must not be blank"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self


class AgentTraceAlertNotificationResult(BaseModel):
    """Result of one alert notification attempt."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    status: AgentTraceAlertNotificationStatus
    channel: str
    destination: str
    message: str
    notification_id: str | None = None

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentTraceAlertNotificationResult:
        """Validate notification-result consistency."""

        required_text = {
            "trace_id": self.trace_id,
            "channel": self.channel,
            "destination": self.destination,
            "message": self.message,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if (
            self.notification_id is not None
            and not self.notification_id.strip()
        ):
            raise ValueError(
                "notification_id must not be blank"
            )

        if (
            self.status
            is AgentTraceAlertNotificationStatus.SENT
            and self.notification_id is None
        ):
            raise ValueError(
                "sent notification requires notification_id"
            )

        if (
            self.status
            is not AgentTraceAlertNotificationStatus.SENT
            and self.notification_id is not None
        ):
            raise ValueError(
                "non-sent notification must not contain "
                "notification_id"
            )

        return self
