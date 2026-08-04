"""Application service for idempotency and duplicate prevention."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Self
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.application.idempotency_record import (
    ApplicationIdempotencyFailure,
    ApplicationIdempotencyRecord,
    ApplicationIdempotencyStatus,
)
from app.application.idempotency_repository import (
    ApplicationIdempotencyRepository,
)
from app.application.idempotency_service_error import (
    ApplicationIdempotencyConflictError,
    ApplicationIdempotencyInProgressError,
    ApplicationIdempotencyRetryNotAllowedError,
    ApplicationIdempotencyServiceError,
)


class ApplicationIdempotencyStartRequest(BaseModel):
    """Request to begin an idempotent operation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    workspace_id: str
    operation: str
    idempotency_key: str
    payload: JsonValue
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate idempotency request text."""

        for field_name, value in {
            "workspace_id": self.workspace_id,
            "operation": self.operation,
            "idempotency_key": self.idempotency_key,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class ApplicationIdempotencyStartResult(BaseModel):
    """Result of beginning an idempotent operation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    record: ApplicationIdempotencyRecord
    execute_operation: bool
    reused_result: JsonValue | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate start-result consistency."""

        if self.execute_operation:
            if (
                self.record.status
                is not ApplicationIdempotencyStatus.IN_PROGRESS
            ):
                raise ValueError(
                    "executable start result requires "
                    "in-progress record"
                )

            if self.reused_result is not None:
                raise ValueError(
                    "executable start result must not contain "
                    "reused_result"
                )
        else:
            if (
                self.record.status
                is not ApplicationIdempotencyStatus.SUCCEEDED
            ):
                raise ValueError(
                    "reused start result requires "
                    "succeeded record"
                )

            if self.reused_result is None:
                raise ValueError(
                    "reused start result requires reused_result"
                )

        return self


class ApplicationIdempotencyService:
    """Coordinate idempotent application operations."""

    def __init__(
        self,
        *,
        repository: ApplicationIdempotencyRepository,
        clock: Callable[[], datetime],
        record_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._record_id_factory = (
            record_id_factory
            or (lambda: f"idempotency-{uuid4()}")
        )

    def begin(
        self,
        request: ApplicationIdempotencyStartRequest,
        *,
        allow_retry_after_failure: bool = True,
    ) -> ApplicationIdempotencyStartResult:
        """Begin or reuse one idempotent operation."""

        fingerprint = self.fingerprint(request.payload)

        existing = self._repository.find(
            workspace_id=request.workspace_id,
            operation=request.operation,
            idempotency_key=request.idempotency_key,
        )

        if existing is None:
            now = self._now()

            created = self._repository.create(
                ApplicationIdempotencyRecord(
                    idempotency_record_id=self._new_record_id(),
                    workspace_id=request.workspace_id,
                    operation=request.operation,
                    idempotency_key=request.idempotency_key,
                    request_fingerprint=fingerprint,
                    status=ApplicationIdempotencyStatus.IN_PROGRESS,
                    created_at=now,
                    updated_at=now,
                    metadata=dict(request.metadata),
                )
            )

            return ApplicationIdempotencyStartResult(
                record=created,
                execute_operation=True,
            )

        self._require_matching_fingerprint(
            existing,
            fingerprint=fingerprint,
        )

        if existing.status is ApplicationIdempotencyStatus.SUCCEEDED:
            return ApplicationIdempotencyStartResult(
                record=existing,
                execute_operation=False,
                reused_result=existing.result,
            )

        if (
            existing.status
            is ApplicationIdempotencyStatus.IN_PROGRESS
        ):
            raise ApplicationIdempotencyInProgressError(
                "idempotent operation is already in progress"
            )

        if not allow_retry_after_failure:
            raise ApplicationIdempotencyRetryNotAllowedError(
                "failed idempotent operation cannot be retried"
            )

        now = self._now()

        restarted = ApplicationIdempotencyRecord(
            **existing.model_dump(
                exclude={
                    "status",
                    "failure",
                    "completed_at",
                    "updated_at",
                    "record_version",
                }
            ),
            status=ApplicationIdempotencyStatus.IN_PROGRESS,
            updated_at=now,
            record_version=existing.record_version + 1,
        )

        persisted = self._repository.update(
            restarted,
            expected_version=existing.record_version,
        )

        return ApplicationIdempotencyStartResult(
            record=persisted,
            execute_operation=True,
        )

    def succeed(
        self,
        *,
        idempotency_record_id: str,
        result: JsonValue,
    ) -> ApplicationIdempotencyRecord:
        """Persist a successful operation result."""

        stored = self._repository.require(
            idempotency_record_id
        )

        if (
            stored.status
            is not ApplicationIdempotencyStatus.IN_PROGRESS
        ):
            raise ApplicationIdempotencyServiceError(
                "only in-progress operation may succeed"
            )

        now = self._now()

        succeeded = ApplicationIdempotencyRecord(
            **stored.model_dump(
                exclude={
                    "status",
                    "result",
                    "updated_at",
                    "completed_at",
                    "record_version",
                }
            ),
            status=ApplicationIdempotencyStatus.SUCCEEDED,
            result=result,
            updated_at=now,
            completed_at=now,
            record_version=stored.record_version + 1,
        )

        return self._repository.update(
            succeeded,
            expected_version=stored.record_version,
        )

    def fail(
        self,
        *,
        idempotency_record_id: str,
        code: str,
        message: str,
        retryable: bool,
    ) -> ApplicationIdempotencyRecord:
        """Persist a failed operation result."""

        stored = self._repository.require(
            idempotency_record_id
        )

        if (
            stored.status
            is not ApplicationIdempotencyStatus.IN_PROGRESS
        ):
            raise ApplicationIdempotencyServiceError(
                "only in-progress operation may fail"
            )

        now = self._now()

        failed = ApplicationIdempotencyRecord(
            **stored.model_dump(
                exclude={
                    "status",
                    "failure",
                    "updated_at",
                    "completed_at",
                    "record_version",
                }
            ),
            status=ApplicationIdempotencyStatus.FAILED,
            failure=ApplicationIdempotencyFailure(
                code=code,
                message=message,
                retryable=retryable,
            ),
            updated_at=now,
            completed_at=now,
            record_version=stored.record_version + 1,
        )

        return self._repository.update(
            failed,
            expected_version=stored.record_version,
        )

    @staticmethod
    def fingerprint(payload: JsonValue) -> str:
        """Return a stable SHA-256 request fingerprint."""

        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _require_matching_fingerprint(
        record: ApplicationIdempotencyRecord,
        *,
        fingerprint: str,
    ) -> None:
        """Reject reuse of a key with different input."""

        if record.request_fingerprint != fingerprint:
            raise ApplicationIdempotencyConflictError(
                "idempotency key was reused with "
                "a different request payload"
            )

    def _now(self) -> datetime:
        """Return a timezone-aware application timestamp."""

        value = self._clock()

        if value.tzinfo is None:
            raise ApplicationIdempotencyServiceError(
                "clock must return timezone-aware datetime"
            )

        return value

    def _new_record_id(self) -> str:
        """Return one nonblank record ID."""

        value = self._record_id_factory()

        if not value.strip():
            raise ApplicationIdempotencyServiceError(
                "idempotency record ID factory returned "
                "blank value"
            )

        return value
