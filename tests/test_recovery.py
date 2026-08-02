from __future__ import annotations

from dataclasses import FrozenInstanceError

import httpx
import openai
import pytest

from app.exceptions import (
    ActiveAuthenticationKeyNotFoundError,
    ArchiveAuthenticationExportError,
    ArchiveAuthenticationFilenameMismatchError,
    ArchiveAuthenticationFormatVersionMismatchError,
    ArchiveAuthenticationMetadataMismatchError,
    ArchiveAuthenticationReadError,
    ArchiveAuthenticityMismatchError,
    ArchiveSignatureArchiveDigestMismatchError,
    ArchiveSignatureError,
    ArchiveSignatureExportError,
    ArchiveSignatureFilenameMismatchError,
    ArchiveSignatureFromFutureError,
    ArchiveSignatureReadError,
    ArchiveSignatureValidationError,
    ArchiveSignatureVerificationError,
    ArchiveSigningKeyFingerprintMismatchError,
    ArchiveSigningKeyNotActiveError,
    ArchiveSigningKeyNotValidError,
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
    BundleReportFilenameMismatchError,
    ChecksumExportError,
    ChecksumFilenameMismatchError,
    DuplicateArchiveSigningKeyIdError,
    DuplicateAuthenticationKeyIdError,
    DuplicateReportArchiveMemberError,
    IncompleteReportBundleError,
    InvalidArchiveAuthenticationFormatError,
    InvalidArchiveSignatureTrustStoreError,
    InvalidArchiveSigningKeyIdError,
    InvalidArchiveSigningPrivateKeyError,
    InvalidAuditEventError,
    InvalidAuthenticationFormatError,
    InvalidAuthenticationKeyError,
    InvalidAuthenticationKeyIdError,
    InvalidAuthenticationKeyringError,
    InvalidAuthenticationTrustStoreError,
    InvalidChecksumFormatError,
    InvalidMigrationRegistryError,
    InvalidReportArchiveError,
    InvalidReportArchiveMemberError,
    InvalidReportArchivePathError,
    InvalidReportExportPathError,
    InvalidRootSigningPrivateKeyError,
    InvalidRootSigningPublicKeyError,
    InvalidSchemaVersionError,
    ManifestTrustStateExportError,
    ManifestTrustStateGenerationConflictError,
    ManifestTrustStateLockError,
    ManifestTrustStatePathError,
    ManifestTrustStateReadError,
    ManifestTrustStateRootMismatchError,
    ManifestTrustStateValidationError,
    MissingArchiveSigningPrivateKeyError,
    MissingAuthenticationKeyError,
    MissingAuthenticationKeyringError,
    MissingManifestTrustStateError,
    MissingReportArchiveMemberError,
    MissingRootSigningPrivateKeyError,
    MissingRootSigningPublicKeyError,
    MissingSchemaMigrationError,
    MultipleActiveAuthenticationKeysError,
    NoActiveAuthenticationKeyError,
    RejectedArchiveSigningKeyError,
    RejectedAuthenticationKeyError,
    ReportArchiveDigestMismatchError,
    ReportArchiveError,
    ReportArchiveExportError,
    ReportArchiveMetadataMismatchError,
    ReportArchiveReadError,
    ReportArchiveSizeLimitError,
    ReportAuthenticationReadError,
    ReportAuthenticityMismatchError,
    ReportBundleDigestMismatchError,
    ReportBundleError,
    ReportBundleExportError,
    ReportBundleManifestValidationError,
    ReportBundleMetadataMismatchError,
    ReportBundleReadError,
    ReportExportWriteError,
    ReportIntegrityMismatchError,
    ReportIntegrityReadError,
    RootSignatureTrustError,
    RootSigningKeyIdError,
    RootSigningKeyMismatchError,
    RootTransitionTransparencyConflictError,
    SchemaCompatibilityError,
    SchemaDowngradeError,
    SchemaMigrationStepError,
    SigningKeyManifestDigestMismatchError,
    SigningKeyManifestError,
    SigningKeyManifestExpiredError,
    SigningKeyManifestExportError,
    SigningKeyManifestFromFutureError,
    SigningKeyManifestMetadataMismatchError,
    SigningKeyManifestNotYetValidError,
    SigningKeyManifestReadError,
    SigningKeyManifestRollbackError,
    SigningKeyManifestSignatureVerificationError,
    SigningKeyManifestTransparencyConflictError,
    SigningKeyManifestValidationError,
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
    TimeBudgetExceededError,
    TokenBudgetExceededError,
    TransparencyLogConflictError,
    TransparencyLogDivergenceError,
    TransparencyLogReadError,
    TransparencyLogStateExportError,
    TransparencyLogStateMismatchError,
    TransparencyLogStateReadError,
    TransparencyLogStateValidationError,
    TransparencyLogValidationError,
    TransparencyLogWriteError,
    UnexpectedReportArchiveMemberError,
    UnknownArchiveSigningKeyError,
    UnknownAuthenticationKeyError,
    UnloggedRootTransitionError,
    UnloggedSigningKeyManifestError,
    UnsafeReportArchiveMemberError,
    UnsupportedAuditSchemaError,
    UnsupportedSchemaVersionError,
)
from app.recovery import RecoveryAction, RecoveryDecision, decide_recovery

SENSITIVE_TEXT = "sk-test-sensitive-user-input"
PRIVATE_HMAC_SECRET = "PRIVATE-HMAC-SECRET"
PRIVATE_KEYRING_SECRET = "PRIVATE-KEYRING-SECRET"
PRIVATE_TRUST_SECRET = "PRIVATE-TRUST-ERROR"
PRIVATE_BUNDLE_SECRET = "PRIVATE-BUNDLE-ERROR"
PRIVATE_ARCHIVE_SECRET = "PRIVATE-ARCHIVE-ERROR"
PRIVATE_SIGNATURE_SECRET = "PRIVATE-ARCHIVE-SECRET"
PRIVATE_ROOT_SECRET = "PRIVATE-ROOT-SECRET"
PRIVATE_MANIFEST_SECRET = "PRIVATE-MANIFEST-SECRET"
PRIVATE_MANIFEST_STATE_SECRET = "PRIVATE-MANIFEST-STATE-SECRET"
PRIVATE_TRANSPARENCY_SECRET = "PRIVATE-TRANSPARENCY-LOG"


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
    assert PRIVATE_BUNDLE_SECRET not in decision.reason
    assert PRIVATE_ARCHIVE_SECRET not in decision.reason
    assert PRIVATE_SIGNATURE_SECRET not in decision.reason
    assert PRIVATE_ROOT_SECRET not in decision.reason
    assert PRIVATE_MANIFEST_SECRET not in decision.reason
    assert PRIVATE_TRANSPARENCY_SECRET not in decision.reason


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

        (ArchiveSignatureError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (MissingArchiveSigningPrivateKeyError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (InvalidArchiveSigningPrivateKeyError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (InvalidArchiveSigningKeyIdError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (InvalidArchiveSignatureTrustStoreError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (DuplicateArchiveSigningKeyIdError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (UnknownArchiveSigningKeyError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSigningKeyNotActiveError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSigningKeyNotValidError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (RejectedArchiveSigningKeyError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSignatureFromFutureError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSigningKeyFingerprintMismatchError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSignatureReadError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSignatureValidationError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSignatureFilenameMismatchError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSignatureArchiveDigestMismatchError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSignatureVerificationError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (ArchiveSignatureExportError(PRIVATE_SIGNATURE_SECRET), False, RecoveryAction.ABORT),
        (RootSignatureTrustError(PRIVATE_ROOT_SECRET), False, RecoveryAction.ABORT),
        (MissingRootSigningPrivateKeyError(PRIVATE_ROOT_SECRET), False, RecoveryAction.ABORT),
        (InvalidRootSigningPrivateKeyError(PRIVATE_ROOT_SECRET), False, RecoveryAction.ABORT),
        (MissingRootSigningPublicKeyError(PRIVATE_ROOT_SECRET), False, RecoveryAction.ABORT),
        (InvalidRootSigningPublicKeyError(PRIVATE_ROOT_SECRET), False, RecoveryAction.ABORT),
        (RootSigningKeyIdError(PRIVATE_ROOT_SECRET), False, RecoveryAction.ABORT),
        (RootSigningKeyMismatchError(PRIVATE_ROOT_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestReadError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestValidationError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestExportError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestSignatureVerificationError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestDigestMismatchError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestMetadataMismatchError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestRollbackError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestExpiredError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestNotYetValidError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (SigningKeyManifestFromFutureError(PRIVATE_MANIFEST_SECRET), False, RecoveryAction.ABORT),
        (ReportArchiveError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (InvalidReportArchivePathError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (ReportArchiveExportError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (ReportArchiveReadError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (InvalidReportArchiveError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (UnsafeReportArchiveMemberError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (DuplicateReportArchiveMemberError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (UnexpectedReportArchiveMemberError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (MissingReportArchiveMemberError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (ReportArchiveSizeLimitError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (InvalidReportArchiveMemberError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (ReportArchiveDigestMismatchError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (ReportArchiveMetadataMismatchError(PRIVATE_ARCHIVE_SECRET), False, RecoveryAction.ABORT),
        (ReportBundleError(PRIVATE_BUNDLE_SECRET), False, RecoveryAction.ABORT),
        (ReportBundleManifestValidationError(PRIVATE_BUNDLE_SECRET), False, RecoveryAction.ABORT),
        (ReportBundleReadError(PRIVATE_BUNDLE_SECRET), False, RecoveryAction.ABORT),
        (ReportBundleExportError(PRIVATE_BUNDLE_SECRET), False, RecoveryAction.ABORT),
        (IncompleteReportBundleError(PRIVATE_BUNDLE_SECRET), False, RecoveryAction.ABORT),
        (BundleReportFilenameMismatchError(PRIVATE_BUNDLE_SECRET), False, RecoveryAction.ABORT),
        (ReportBundleDigestMismatchError(PRIVATE_BUNDLE_SECRET), False, RecoveryAction.ABORT),
        (ReportBundleMetadataMismatchError(PRIVATE_BUNDLE_SECRET), False, RecoveryAction.ABORT),
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



@pytest.mark.parametrize(
    "error",
    [
        ArchiveAuthenticationReadError("PRIVATE-ARCHIVE-SECRET"),
        InvalidArchiveAuthenticationFormatError("PRIVATE-ARCHIVE-SECRET"),
        ArchiveAuthenticationFilenameMismatchError("PRIVATE-ARCHIVE-SECRET"),
        ArchiveAuthenticationFormatVersionMismatchError("PRIVATE-ARCHIVE-SECRET"),
        ArchiveAuthenticityMismatchError("PRIVATE-ARCHIVE-SECRET"),
        ArchiveAuthenticationExportError("PRIVATE-ARCHIVE-SECRET"),
        ArchiveAuthenticationMetadataMismatchError("PRIVATE-ARCHIVE-SECRET"),
    ],
)
def test_archive_authenticity_errors_are_abort_without_secret(error: BaseException) -> None:
    decision = decide_recovery(error)

    assert decision.retryable is False
    assert decision.action is RecoveryAction.ABORT
    assert decision.reason
    assert "PRIVATE-ARCHIVE-SECRET" not in decision.reason
    assert "key-1" not in decision.reason


@pytest.mark.parametrize(
    "error",
    [
        MissingRootSigningPrivateKeyError(PRIVATE_ROOT_SECRET),
        InvalidRootSigningPrivateKeyError(PRIVATE_ROOT_SECRET),
        MissingRootSigningPublicKeyError(PRIVATE_ROOT_SECRET),
        InvalidRootSigningPublicKeyError(PRIVATE_ROOT_SECRET),
        RootSigningKeyIdError(PRIVATE_ROOT_SECRET),
        RootSigningKeyMismatchError(PRIVATE_ROOT_SECRET),
    ],
)
def test_root_signature_trust_errors_are_abort_without_secret(error: BaseException) -> None:
    decision = decide_recovery(error)

    assert decision.retryable is False
    assert decision.action is RecoveryAction.ABORT
    assert decision.reason
    assert PRIVATE_ROOT_SECRET not in decision.reason


@pytest.mark.parametrize(
    "error",
    [
        SigningKeyManifestReadError(PRIVATE_MANIFEST_SECRET),
        SigningKeyManifestValidationError(PRIVATE_MANIFEST_SECRET),
        SigningKeyManifestExportError(PRIVATE_MANIFEST_SECRET),
        SigningKeyManifestSignatureVerificationError(PRIVATE_MANIFEST_SECRET),
        SigningKeyManifestDigestMismatchError(PRIVATE_MANIFEST_SECRET),
        SigningKeyManifestMetadataMismatchError(PRIVATE_MANIFEST_SECRET),
        SigningKeyManifestRollbackError(PRIVATE_MANIFEST_SECRET),
        SigningKeyManifestExpiredError(PRIVATE_MANIFEST_SECRET),
        SigningKeyManifestNotYetValidError(PRIVATE_MANIFEST_SECRET),
        SigningKeyManifestFromFutureError(PRIVATE_MANIFEST_SECRET),
    ],
)
def test_signing_key_manifest_errors_are_abort_without_secret(error: BaseException) -> None:
    decision = decide_recovery(error)

    assert decision.retryable is False
    assert decision.action is RecoveryAction.ABORT
    assert decision.reason
    assert PRIVATE_MANIFEST_SECRET not in decision.reason


@pytest.mark.parametrize(
    "error",
    [
        ManifestTrustStateReadError(PRIVATE_MANIFEST_STATE_SECRET),
        ManifestTrustStateValidationError(PRIVATE_MANIFEST_STATE_SECRET),
        ManifestTrustStateExportError(PRIVATE_MANIFEST_STATE_SECRET),
        ManifestTrustStateLockError(PRIVATE_MANIFEST_STATE_SECRET),
        MissingManifestTrustStateError(PRIVATE_MANIFEST_STATE_SECRET),
        ManifestTrustStateRootMismatchError(PRIVATE_MANIFEST_STATE_SECRET),
        ManifestTrustStateGenerationConflictError(PRIVATE_MANIFEST_STATE_SECRET),
        ManifestTrustStatePathError(PRIVATE_MANIFEST_STATE_SECRET),
    ],
)
def test_manifest_trust_state_errors_are_abort_without_secret(error: BaseException) -> None:
    decision = decide_recovery(error)

    assert decision.retryable is False
    assert decision.action is RecoveryAction.ABORT
    assert decision.reason
    assert PRIVATE_MANIFEST_STATE_SECRET not in decision.reason


def test_root_transition_error_recovery_is_abort() -> None:
    from app.exceptions import RootTransitionValidationError
    from app.recovery import RecoveryAction, decide_recovery

    decision = decide_recovery(RootTransitionValidationError("PRIVATE-ROOT-ERROR"))

    assert decision.retryable is False
    assert decision.action is RecoveryAction.ABORT
    assert decision.reason
    assert "PRIVATE-ROOT-ERROR" not in decision.reason


def test_root_trust_state_error_recovery_is_abort() -> None:
    from app.exceptions import RootTrustStateValidationError
    from app.recovery import RecoveryAction, decide_recovery

    decision = decide_recovery(RootTrustStateValidationError("PRIVATE-ROOT-STATE"))

    assert decision.retryable is False
    assert decision.action is RecoveryAction.ABORT
    assert decision.reason
    assert "PRIVATE-ROOT-STATE" not in decision.reason


def test_manifest_trust_state_retirement_error_recovery_is_abort() -> None:
    from app.exceptions import ManifestTrustStateRetirementError
    from app.recovery import RecoveryAction, decide_recovery

    decision = decide_recovery(ManifestTrustStateRetirementError("PRIVATE-RETIRED-STATE"))

    assert decision.retryable is False
    assert decision.action is RecoveryAction.ABORT
    assert decision.reason
    assert "PRIVATE-RETIRED-STATE" not in decision.reason


@pytest.mark.parametrize(
    "error",
    [
        TransparencyLogStateReadError(PRIVATE_TRANSPARENCY_SECRET),
        TransparencyLogStateValidationError(PRIVATE_TRANSPARENCY_SECRET),
        TransparencyLogStateExportError(PRIVATE_TRANSPARENCY_SECRET),
        TransparencyLogReadError(PRIVATE_TRANSPARENCY_SECRET),
        TransparencyLogValidationError(PRIVATE_TRANSPARENCY_SECRET),
        TransparencyLogWriteError(PRIVATE_TRANSPARENCY_SECRET),
        TransparencyLogDivergenceError(PRIVATE_TRANSPARENCY_SECRET),
        TransparencyLogStateMismatchError(PRIVATE_TRANSPARENCY_SECRET),
        TransparencyLogConflictError(PRIVATE_TRANSPARENCY_SECRET),
        RootTransitionTransparencyConflictError(PRIVATE_TRANSPARENCY_SECRET),
        SigningKeyManifestTransparencyConflictError(PRIVATE_TRANSPARENCY_SECRET),
        UnloggedRootTransitionError(PRIVATE_TRANSPARENCY_SECRET),
        UnloggedSigningKeyManifestError(PRIVATE_TRANSPARENCY_SECRET),
    ],
)
def test_transparency_log_errors_are_abort_without_secret(error: BaseException) -> None:
    decision = decide_recovery(error)

    assert decision.retryable is False
    assert decision.action is RecoveryAction.ABORT
    assert decision.reason
    assert PRIVATE_TRANSPARENCY_SECRET not in decision.reason
    assert "a" * 64 not in decision.reason
