"""Pure recovery policy decisions for handled errors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import openai

from app.exceptions import (
    ArchiveAuthenticityError,
    ArchiveSignatureError,
    AttemptBudgetExceededError,
    AuditLogError,
    AuditReportValidationError,
    AuthenticationKeyringError,
    AuthenticationTrustError,
    ManifestTrustStateError,
    ReportArchiveError,
    ReportAuthenticityError,
    ReportBundleError,
    ReportExportError,
    ReportIntegrityError,
    RootSignatureTrustError,
    SchemaCompatibilityError,
    SchemaMigrationError,
    SigningKeyManifestError,
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
    TimeBudgetExceededError,
    TokenBudgetExceededError,
)


class RecoveryAction(str, Enum):
    RETRY_LATER = "retry_later"
    MODIFY_REQUEST = "modify_request"
    FIX_CONFIGURATION = "fix_configuration"
    HUMAN_REVIEW = "human_review"
    ABORT = "abort"


@dataclass(frozen=True)
class RecoveryDecision:
    retryable: bool
    action: RecoveryAction
    reason: str


def decide_recovery(error: BaseException) -> RecoveryDecision:
    """Return the recommended recovery policy for an error."""

    if isinstance(error, openai.AuthenticationError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.FIX_CONFIGURATION,
            reason="OpenAI authentication configuration must be fixed.",
        )

    if isinstance(error, openai.PermissionDeniedError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.FIX_CONFIGURATION,
            reason="OpenAI permission configuration must be fixed.",
        )

    if isinstance(error, openai.BadRequestError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.MODIFY_REQUEST,
            reason="The OpenAI request must be corrected before retrying.",
        )

    if isinstance(error, openai.NotFoundError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.FIX_CONFIGURATION,
            reason="The configured OpenAI resource must be fixed.",
        )

    if isinstance(error, openai.RateLimitError):
        return RecoveryDecision(
            retryable=True,
            action=RecoveryAction.RETRY_LATER,
            reason="OpenAI rate limits require retrying later.",
        )

    if isinstance(error, openai.APITimeoutError):
        return RecoveryDecision(
            retryable=True,
            action=RecoveryAction.RETRY_LATER,
            reason="The OpenAI request timed out and may be retried later.",
        )

    if isinstance(error, openai.APIConnectionError):
        return RecoveryDecision(
            retryable=True,
            action=RecoveryAction.RETRY_LATER,
            reason="The OpenAI connection failed and may be retried later.",
        )

    if isinstance(error, openai.InternalServerError):
        return RecoveryDecision(
            retryable=True,
            action=RecoveryAction.RETRY_LATER,
            reason="OpenAI server errors may be retried later.",
        )

    if isinstance(error, StructuredResponseIncompleteError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.MODIFY_REQUEST,
            reason="The structured analysis request should be simplified or modified.",
        )

    if isinstance(error, StructuredResponseRefusalError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.HUMAN_REVIEW,
            reason="The structured analysis refusal requires human review.",
        )

    if isinstance(error, StructuredResponseValidationError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.MODIFY_REQUEST,
            reason="Structured analysis validation failed after correction.",
        )

    if isinstance(error, StructuredResponseParseError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The structured analysis response could not be parsed safely.",
        )

    if isinstance(error, StructuredResponseStatusError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The structured analysis response ended with an unexpected status.",
        )

    if isinstance(error, AttemptBudgetExceededError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="Execution attempt budget was exceeded.",
        )

    if isinstance(error, TokenBudgetExceededError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="Execution recorded token budget was exceeded.",
        )

    if isinstance(error, TimeBudgetExceededError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="Execution elapsed time budget was exceeded.",
        )

    if isinstance(error, AuditReportValidationError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The audit report output contract was invalid.",
        )

    if isinstance(error, AuditLogError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="Structured analysis audit logging failed.",
        )

    if isinstance(error, SchemaCompatibilityError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The published audit report schema contract changed unexpectedly.",
        )

    if isinstance(error, SchemaMigrationError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The schema payload could not be migrated safely.",
        )

    if isinstance(error, ReportExportError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The audit report could not be exported safely.",
        )

    if isinstance(error, ReportIntegrityError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The exported audit report failed an integrity check.",
        )


    if isinstance(error, ManifestTrustStateError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The signing key manifest trust state could not be verified or updated safely.",
        )

    if isinstance(error, SigningKeyManifestError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The archive signing key manifest is invalid, untrusted, or out of date.",
        )

    if isinstance(error, RootSignatureTrustError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The archive signing root key is not configured safely.",
        )

    if isinstance(error, ArchiveSignatureError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The audit report archive signature could not be created or verified safely.",
        )

    if isinstance(error, ArchiveAuthenticityError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The audit report archive could not be authenticated safely.",
        )

    if isinstance(error, ReportArchiveError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The audit report archive is unsafe, incomplete, or inconsistent.",
        )

    if isinstance(error, ReportBundleError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The audit report bundle is incomplete or inconsistent.",
        )

    if isinstance(error, AuthenticationKeyringError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The audit report authentication keyring is not configured safely.",
        )

    if isinstance(error, AuthenticationTrustError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The audit report authentication trust policy rejected the operation.",
        )

    if isinstance(error, ReportAuthenticityError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="The audit report could not be authenticated safely.",
        )

    if isinstance(error, ValueError):
        return RecoveryDecision(
            retryable=False,
            action=RecoveryAction.MODIFY_REQUEST,
            reason="The request input must be modified.",
        )

    return RecoveryDecision(
        retryable=False,
        action=RecoveryAction.ABORT,
        reason="The error is not recoverable by the current policy.",
    )
