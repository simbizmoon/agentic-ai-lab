from __future__ import annotations

from dataclasses import FrozenInstanceError

import httpx
import openai
import pytest

from app.exceptions import (
    ActiveAuthenticationKeyNotFoundError,
    AttemptBudgetExceededError,
    AuditLogError,
    AuditLogParseError,
    AuditLogReadError,
    AuditReportValidationError,
    AuthenticationExportError,
    AuthenticationFilenameMismatchError,
    AuthenticationFromFutureError,
    AuthenticationKeyNotValidAtSigningTimeError,
    AuthenticationKeyringError,
    AuthenticationTrustError,
    ChecksumExportError,
    ChecksumFilenameMismatchError,
    DuplicateAuthenticationKeyIdError,
    InvalidAuditEventError,
    InvalidAuthenticationFormatError,
    InvalidAuthenticationKeyError,
    InvalidAuthenticationKeyIdError,
    InvalidAuthenticationKeyringError,
    InvalidAuthenticationTrustStoreError,
    InvalidChecksumFormatError,
    InvalidMigrationRegistryError,
    InvalidReportExportPathError,
    InvalidSchemaVersionError,
    MissingAuthenticationKeyError,
    MissingAuthenticationKeyringError,
    MissingSchemaMigrationError,
    MultipleActiveAuthenticationKeysError,
    NoActiveAuthenticationKeyError,
    RejectedAuthenticationKeyError,
    ReportAuthenticationReadError,
    ReportAuthenticityMismatchError,
    ReportExportWriteError,
    ReportIntegrityMismatchError,
    ReportIntegrityReadError,
    SchemaCompatibilityError,
    SchemaDowngradeError,
    SchemaMigrationStepError,
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
    TimeBudgetExceededError,
    TokenBudgetExceededError,
    UnknownAuthenticationKeyError,
    UnsupportedAuditSchemaError,
    UnsupportedSchemaVersionError,
)
from app.recovery import RecoveryAction, RecoveryDecision, decide_recovery

SENSITIVE_TEXT = "sk-test-sensitive-user-input"
PRIVATE_HMAC_SECRET = "PRIVATE-HMAC-SECRET"
PRIVATE_KEYRING_SECRET = "PRIVATE-KEYRING-SECRET"
PRIVATE_TRUST_SECRET = "PRIVATE-TRUST-ERROR"


def make_request() -> httpx.Request:
    return httpx.Request("POST", "https://example.test/responses")


def make_http_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=make_request())


def make_status_error(error_type: type[openai.APIStatusError]) -> openai.APIStatusError:
    return error_type(
        SENSITIVE_TEXT,
        response=make_http_response(500),
        body={"error": SENSITIVE_TEXT},
    )


def assert_decision(
    error: BaseException,
    *,
    retryable: bool,
    action: RecoveryAction,
) -> None:
    decision = decide_recovery(error)

    assert decision.retryable is retryable
    assert decision.action is action
    assert decision.reason
    assert SENSITIVE_TEXT not in decision.reason
    assert PRIVATE_HMAC_SECRET not in decision.reason
    assert PRIVATE_KEYRING_SECRET not in decision.reason
    assert PRIVATE_TRUST_SECRET not in decision.reason


def test_recovery_action_string_values() -> None:
    assert RecoveryAction.RETRY_LATER.value == "retry_later"
    assert RecoveryAction.MODIFY_REQUEST.value == "modify_request"
    assert RecoveryAction.FIX_CONFIGURATION.value == "fix_configuration"
    assert RecoveryAction.HUMAN_REVIEW.value == "human_review"
    assert RecoveryAction.ABORT.value == "abort"


def test_recovery_decision_is_frozen() -> None:
    decision = RecoveryDecision(
        retryable=False,
        action=RecoveryAction.ABORT,
        reason="stable reason",
    )

    with pytest.raises(FrozenInstanceError):
        decision.retryable = True


@pytest.mark.parametrize(
    ("error", "retryable", "action"),
    [
        (ValueError(SENSITIVE_TEXT), False, RecoveryAction.MODIFY_REQUEST),
        (
            make_status_error(openai.AuthenticationError),
            False,
            RecoveryAction.FIX_CONFIGURATION,
        ),
        (
            make_status_error(openai.PermissionDeniedError),
            False,
            RecoveryAction.FIX_CONFIGURATION,
        ),
        (
            make_status_error(openai.BadRequestError),
            False,
            RecoveryAction.MODIFY_REQUEST,
        ),
        (
            make_status_error(openai.NotFoundError),
            False,
            RecoveryAction.FIX_CONFIGURATION,
        ),
        (
            make_status_error(openai.RateLimitError),
            True,
            RecoveryAction.RETRY_LATER,
        ),
        (openai.APITimeoutError(request=make_request()), True, RecoveryAction.RETRY_LATER),
        (
            openai.APIConnectionError(message=SENSITIVE_TEXT, request=make_request()),
            True,
            RecoveryAction.RETRY_LATER,
        ),
        (
            make_status_error(openai.InternalServerError),
            True,
            RecoveryAction.RETRY_LATER,
        ),
        (
            StructuredResponseIncompleteError(SENSITIVE_TEXT),
            False,
            RecoveryAction.MODIFY_REQUEST,
        ),
        (
            StructuredResponseRefusalError(SENSITIVE_TEXT),
            False,
            RecoveryAction.HUMAN_REVIEW,
        ),
        (
            StructuredResponseValidationError(SENSITIVE_TEXT),
            False,
            RecoveryAction.MODIFY_REQUEST,
        ),
        (StructuredResponseParseError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (StructuredResponseStatusError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (AuditLogError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (AuditLogReadError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (AuditLogParseError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (UnsupportedAuditSchemaError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (InvalidAuditEventError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (AuditReportValidationError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (SchemaCompatibilityError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (InvalidSchemaVersionError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (UnsupportedSchemaVersionError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (SchemaDowngradeError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (InvalidMigrationRegistryError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (MissingSchemaMigrationError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (SchemaMigrationStepError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (InvalidReportExportPathError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (ReportExportWriteError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (ReportIntegrityReadError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (InvalidChecksumFormatError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (ChecksumFilenameMismatchError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (ReportIntegrityMismatchError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (ChecksumExportError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (AuthenticationKeyringError(PRIVATE_KEYRING_SECRET), False, RecoveryAction.ABORT),
        (MissingAuthenticationKeyringError(PRIVATE_KEYRING_SECRET), False, RecoveryAction.ABORT),
        (InvalidAuthenticationKeyringError(PRIVATE_KEYRING_SECRET), False, RecoveryAction.ABORT),
        (DuplicateAuthenticationKeyIdError(PRIVATE_KEYRING_SECRET), False, RecoveryAction.ABORT),
        (ActiveAuthenticationKeyNotFoundError(PRIVATE_KEYRING_SECRET), False, RecoveryAction.ABORT),
        (AuthenticationTrustError(PRIVATE_TRUST_SECRET), False, RecoveryAction.ABORT),
        (InvalidAuthenticationTrustStoreError(PRIVATE_TRUST_SECRET), False, RecoveryAction.ABORT),
        (NoActiveAuthenticationKeyError(PRIVATE_TRUST_SECRET), False, RecoveryAction.ABORT),
        (MultipleActiveAuthenticationKeysError(PRIVATE_TRUST_SECRET), False, RecoveryAction.ABORT),
        (AuthenticationKeyNotValidAtSigningTimeError(PRIVATE_TRUST_SECRET), False, RecoveryAction.ABORT),
        (RejectedAuthenticationKeyError(PRIVATE_TRUST_SECRET), False, RecoveryAction.ABORT),
        (AuthenticationFromFutureError(PRIVATE_TRUST_SECRET), False, RecoveryAction.ABORT),
        (MissingAuthenticationKeyError(PRIVATE_HMAC_SECRET), False, RecoveryAction.ABORT),
        (InvalidAuthenticationKeyError(PRIVATE_HMAC_SECRET), False, RecoveryAction.ABORT),
        (InvalidAuthenticationKeyIdError(PRIVATE_HMAC_SECRET), False, RecoveryAction.ABORT),
        (ReportAuthenticationReadError(PRIVATE_HMAC_SECRET), False, RecoveryAction.ABORT),
        (InvalidAuthenticationFormatError(PRIVATE_HMAC_SECRET), False, RecoveryAction.ABORT),
        (AuthenticationFilenameMismatchError(PRIVATE_HMAC_SECRET), False, RecoveryAction.ABORT),
        (UnknownAuthenticationKeyError(PRIVATE_HMAC_SECRET), False, RecoveryAction.ABORT),
        (ReportAuthenticityMismatchError(PRIVATE_HMAC_SECRET), False, RecoveryAction.ABORT),
        (AuthenticationExportError(PRIVATE_HMAC_SECRET), False, RecoveryAction.ABORT),
        (AttemptBudgetExceededError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (TokenBudgetExceededError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (TimeBudgetExceededError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
        (RuntimeError(SENSITIVE_TEXT), False, RecoveryAction.ABORT),
    ],
)
def test_decide_recovery_returns_expected_policy(
    error: BaseException,
    retryable: bool,
    action: RecoveryAction,
) -> None:
    assert_decision(error, retryable=retryable, action=action)
