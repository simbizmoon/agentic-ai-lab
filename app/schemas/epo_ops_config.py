"""Configuration and OAuth token contracts for EPO OPS."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


class EpoOpsConfig(BaseModel):
    """Validated transport configuration for EPO Open Patent Services."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    consumer_key: SecretStr
    consumer_secret: SecretStr
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    maximum_response_bytes: int = Field(
        default=1_000_000,
        ge=1_024,
        le=10_000_000,
    )

    @model_validator(mode="after")
    def validate_credentials(self) -> EpoOpsConfig:
        """Reject credentials which cannot authenticate one OPS application."""

        if not self.consumer_key.get_secret_value().strip():
            raise ValueError("EPO OPS consumer key must not be blank")
        if not self.consumer_secret.get_secret_value().strip():
            raise ValueError("EPO OPS consumer secret must not be blank")
        return self


class EpoOpsAccessToken(BaseModel):
    """Validated secret-safe subset of the documented OPS token response."""

    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)

    access_token: SecretStr
    token_type: str
    expires_in: int = Field(gt=0)

    @field_validator("expires_in", mode="before")
    @classmethod
    def normalize_documented_numeric_string(cls, value: Any) -> Any:
        """Accept the numeric string used by the official OPS response sample."""

        if isinstance(value, str) and value.isascii() and value.isdecimal():
            return int(value)
        return value

    @model_validator(mode="after")
    def validate_token(self) -> EpoOpsAccessToken:
        """Validate the fields needed for bearer authentication."""

        if not self.access_token.get_secret_value().strip():
            raise ValueError("EPO OPS access token must not be blank")
        if self.token_type.casefold() != "bearer":
            raise ValueError("EPO OPS token type must be Bearer")
        return self
