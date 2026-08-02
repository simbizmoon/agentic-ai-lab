from app.exceptions import (
    ActiveAuthenticationKeyNotFoundError,
    AgenticAILabError,
    ArchiveAuthenticationExportError,
    ArchiveAuthenticationFilenameMismatchError,
    ArchiveAuthenticationFormatVersionMismatchError,
    ArchiveAuthenticationMetadataMismatchError,
    ArchiveAuthenticationReadError,
    ArchiveAuthenticityError,
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
    ExecutionBudgetError,
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
    MissingArchiveSigningPrivateKeyError,
    MissingAuthenticationKeyError,
    MissingAuthenticationKeyringError,
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
    ReportAuthenticityError,
    ReportAuthenticityMismatchError,
    ReportBundleDigestMismatchError,
    ReportBundleError,
    ReportBundleExportError,
    ReportBundleManifestValidationError,
    ReportBundleMetadataMismatchError,
    ReportBundleReadError,
    ReportExportError,
    ReportExportWriteError,
    ReportIntegrityError,
    ReportIntegrityMismatchError,
    ReportIntegrityReadError,
    RootSignatureTrustError,
    RootSigningKeyIdError,
    RootSigningKeyMismatchError,
    SchemaCompatibilityError,
    SchemaDowngradeError,
    SchemaMigrationError,
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
    SigningKeyManifestValidationError,
    StructuredAnalysisError,
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
    TimeBudgetExceededError,
    TokenBudgetExceededError,
    UnexpectedReportArchiveMemberError,
    UnknownArchiveSigningKeyError,
    UnknownAuthenticationKeyError,
    UnsafeReportArchiveMemberError,
    UnsupportedAuditSchemaError,
    UnsupportedSchemaVersionError,
)


def test_structured_analysis_error_inherits_from_project_error() -> None:
    assert issubclass(StructuredAnalysisError, AgenticAILabError)


def test_concrete_structured_analysis_errors_inherit_from_base_error() -> None:
    for exception_type in (
        StructuredResponseIncompleteError,
        StructuredResponseRefusalError,
        StructuredResponseParseError,
        StructuredResponseStatusError,
        StructuredResponseValidationError,
    ):
        assert issubclass(exception_type, StructuredAnalysisError)


def test_concrete_structured_analysis_errors_are_distinct_classes() -> None:
    exception_types = {
        StructuredResponseIncompleteError,
        StructuredResponseRefusalError,
        StructuredResponseParseError,
        StructuredResponseStatusError,
        StructuredResponseValidationError,
    }

    assert len(exception_types) == 5


def test_structured_response_validation_error_stores_default_metadata() -> None:
    error = StructuredResponseValidationError(
        "validation failed",
        elapsed_seconds=0.25,
    )

    assert str(error) == "validation failed"
    assert error.elapsed_seconds == 0.25
    assert error.attempts == 1


def test_structured_response_validation_error_stores_attempt_count() -> None:
    error = StructuredResponseValidationError(
        "validation failed",
        elapsed_seconds=0.75,
        attempts=2,
    )

    assert error.elapsed_seconds == 0.75
    assert error.attempts == 2


def test_execution_budget_error_inherits_from_project_error() -> None:
    assert issubclass(ExecutionBudgetError, AgenticAILabError)


def test_concrete_budget_errors_inherit_from_budget_error() -> None:
    for exception_type in (
        AttemptBudgetExceededError,
        TokenBudgetExceededError,
        TimeBudgetExceededError,
    ):
        assert issubclass(exception_type, ExecutionBudgetError)


def test_concrete_budget_errors_are_distinct_classes() -> None:
    exception_types = {
        AttemptBudgetExceededError,
        TokenBudgetExceededError,
        TimeBudgetExceededError,
    }

    assert len(exception_types) == 3


def test_audit_log_error_inherits_from_project_error() -> None:
    assert issubclass(AuditLogError, AgenticAILabError)


def test_audit_log_read_errors_inherit_from_audit_log_error() -> None:
    for exception_type in (
        AuditLogReadError,
        AuditLogParseError,
        UnsupportedAuditSchemaError,
        InvalidAuditEventError,
        AuditReportValidationError,
    ):
        assert issubclass(exception_type, AuditLogError)


def test_concrete_audit_log_read_errors_are_distinct_classes() -> None:
    exception_types = {
        AuditLogReadError,
        AuditLogParseError,
        UnsupportedAuditSchemaError,
        InvalidAuditEventError,
        AuditReportValidationError,
    }

    assert len(exception_types) == 5


def test_schema_compatibility_error_inherits_from_project_error() -> None:
    assert issubclass(SchemaCompatibilityError, AgenticAILabError)


def test_schema_compatibility_error_is_distinct_class() -> None:
    exception_types = {
        SchemaCompatibilityError,
        AuditLogError,
        AuditReportValidationError,
        InvalidAuditEventError,
    }

    assert len(exception_types) == 4


def test_schema_migration_error_inherits_from_project_error() -> None:
    assert issubclass(SchemaMigrationError, AgenticAILabError)


def test_concrete_schema_migration_errors_inherit_from_base_error() -> None:
    for exception_type in (
        InvalidSchemaVersionError,
        UnsupportedSchemaVersionError,
        SchemaDowngradeError,
        InvalidMigrationRegistryError,
        MissingSchemaMigrationError,
        SchemaMigrationStepError,
    ):
        assert issubclass(exception_type, SchemaMigrationError)


def test_concrete_schema_migration_errors_are_distinct_classes() -> None:
    exception_types = {
        InvalidSchemaVersionError,
        UnsupportedSchemaVersionError,
        SchemaDowngradeError,
        InvalidMigrationRegistryError,
        MissingSchemaMigrationError,
        SchemaMigrationStepError,
    }

    assert len(exception_types) == 6


def test_report_export_error_inherits_from_project_error() -> None:
    assert issubclass(ReportExportError, AgenticAILabError)


def test_concrete_report_export_errors_inherit_from_base_error() -> None:
    for exception_type in (
        InvalidReportExportPathError,
        ReportExportWriteError,
    ):
        assert issubclass(exception_type, ReportExportError)


def test_concrete_report_export_errors_are_distinct_classes() -> None:
    exception_types = {
        ReportExportError,
        InvalidReportExportPathError,
        ReportExportWriteError,
    }

    assert len(exception_types) == 3


def test_report_integrity_error_inherits_from_project_error() -> None:
    assert issubclass(ReportIntegrityError, AgenticAILabError)


def test_concrete_report_integrity_errors_inherit_from_base_error() -> None:
    for exception_type in (
        ReportIntegrityReadError,
        InvalidChecksumFormatError,
        ChecksumFilenameMismatchError,
        ReportIntegrityMismatchError,
        ChecksumExportError,
    ):
        assert issubclass(exception_type, ReportIntegrityError)


def test_concrete_report_integrity_errors_are_distinct_classes() -> None:
    exception_types = {
        ReportIntegrityError,
        ReportIntegrityReadError,
        InvalidChecksumFormatError,
        ChecksumFilenameMismatchError,
        ReportIntegrityMismatchError,
        ChecksumExportError,
    }

    assert len(exception_types) == 6


def test_report_authenticity_error_inherits_from_project_error() -> None:
    assert issubclass(ReportAuthenticityError, AgenticAILabError)


def test_concrete_report_authenticity_errors_inherit_from_base_error() -> None:
    for exception_type in (
        MissingAuthenticationKeyError,
        InvalidAuthenticationKeyError,
        InvalidAuthenticationKeyIdError,
        ReportAuthenticationReadError,
        InvalidAuthenticationFormatError,
        AuthenticationFilenameMismatchError,
        UnknownAuthenticationKeyError,
        ReportAuthenticityMismatchError,
        AuthenticationExportError,
    ):
        assert issubclass(exception_type, ReportAuthenticityError)


def test_concrete_report_authenticity_errors_are_distinct_classes() -> None:
    exception_types = {
        ReportAuthenticityError,
        MissingAuthenticationKeyError,
        InvalidAuthenticationKeyError,
        InvalidAuthenticationKeyIdError,
        ReportAuthenticationReadError,
        InvalidAuthenticationFormatError,
        AuthenticationFilenameMismatchError,
        UnknownAuthenticationKeyError,
        ReportAuthenticityMismatchError,
        AuthenticationExportError,
    }

    assert len(exception_types) == 10


def test_authentication_keyring_error_inherits_from_authenticity_error() -> None:
    assert issubclass(AuthenticationKeyringError, ReportAuthenticityError)


def test_concrete_authentication_keyring_errors_inherit_from_keyring_error() -> None:
    for exception_type in (
        MissingAuthenticationKeyringError,
        InvalidAuthenticationKeyringError,
        DuplicateAuthenticationKeyIdError,
        ActiveAuthenticationKeyNotFoundError,
    ):
        assert issubclass(exception_type, AuthenticationKeyringError)


def test_concrete_authentication_keyring_errors_are_distinct_classes() -> None:
    exception_types = {
        AuthenticationKeyringError,
        MissingAuthenticationKeyringError,
        InvalidAuthenticationKeyringError,
        DuplicateAuthenticationKeyIdError,
        ActiveAuthenticationKeyNotFoundError,
        UnknownAuthenticationKeyError,
    }

    assert len(exception_types) == 6



def test_authentication_trust_error_inherits_from_authenticity_error() -> None:
    assert issubclass(AuthenticationTrustError, ReportAuthenticityError)


def test_authentication_keyring_error_inherits_from_trust_error() -> None:
    assert issubclass(AuthenticationKeyringError, AuthenticationTrustError)


def test_concrete_authentication_trust_errors_inherit_from_trust_error() -> None:
    for exception_type in (
        InvalidAuthenticationTrustStoreError,
        DuplicateAuthenticationKeyIdError,
        NoActiveAuthenticationKeyError,
        MultipleActiveAuthenticationKeysError,
        AuthenticationKeyNotValidAtSigningTimeError,
        RejectedAuthenticationKeyError,
        AuthenticationFromFutureError,
    ):
        assert issubclass(exception_type, AuthenticationTrustError)


def test_concrete_authentication_trust_errors_are_distinct_classes() -> None:
    exception_types = {
        AuthenticationTrustError,
        InvalidAuthenticationTrustStoreError,
        DuplicateAuthenticationKeyIdError,
        NoActiveAuthenticationKeyError,
        MultipleActiveAuthenticationKeysError,
        AuthenticationKeyNotValidAtSigningTimeError,
        RejectedAuthenticationKeyError,
        AuthenticationFromFutureError,
        AuthenticationKeyringError,
    }

    assert len(exception_types) == 9




def test_report_bundle_error_inherits_from_project_error() -> None:
    assert issubclass(ReportBundleError, AgenticAILabError)


def test_concrete_report_bundle_errors_inherit_from_base_error() -> None:
    for exception_type in (
        ReportBundleManifestValidationError,
        ReportBundleReadError,
        ReportBundleExportError,
        IncompleteReportBundleError,
        BundleReportFilenameMismatchError,
        ReportBundleDigestMismatchError,
        ReportBundleMetadataMismatchError,
    ):
        assert issubclass(exception_type, ReportBundleError)


def test_concrete_report_bundle_errors_are_distinct_classes() -> None:
    exception_types = {
        ReportBundleError,
        ReportBundleManifestValidationError,
        ReportBundleReadError,
        ReportBundleExportError,
        IncompleteReportBundleError,
        BundleReportFilenameMismatchError,
        ReportBundleDigestMismatchError,
        ReportBundleMetadataMismatchError,
    }

    assert len(exception_types) == 8

def test_report_archive_error_inherits_from_project_error() -> None:
    assert issubclass(ReportArchiveError, AgenticAILabError)


def test_concrete_report_archive_errors_inherit_from_archive_error() -> None:
    for exception_type in (
        InvalidReportArchivePathError,
        ReportArchiveExportError,
        ReportArchiveReadError,
        InvalidReportArchiveError,
        UnsafeReportArchiveMemberError,
        DuplicateReportArchiveMemberError,
        UnexpectedReportArchiveMemberError,
        MissingReportArchiveMemberError,
        ReportArchiveSizeLimitError,
        InvalidReportArchiveMemberError,
        ReportArchiveDigestMismatchError,
        ReportArchiveMetadataMismatchError,
    ):
        assert issubclass(exception_type, ReportArchiveError)


def test_concrete_report_archive_errors_are_distinct_classes() -> None:
    exception_types = {
        ReportArchiveError,
        InvalidReportArchivePathError,
        ReportArchiveExportError,
        ReportArchiveReadError,
        InvalidReportArchiveError,
        UnsafeReportArchiveMemberError,
        DuplicateReportArchiveMemberError,
        UnexpectedReportArchiveMemberError,
        MissingReportArchiveMemberError,
        ReportArchiveSizeLimitError,
        InvalidReportArchiveMemberError,
        ReportArchiveDigestMismatchError,
        ReportArchiveMetadataMismatchError,
    }

    assert len(exception_types) == 13



def test_archive_authenticity_error_inherits_from_project_error() -> None:
    assert issubclass(ArchiveAuthenticityError, AgenticAILabError)


def test_concrete_archive_authenticity_errors_inherit_from_archive_authenticity_error() -> None:
    for exception_type in (
        ArchiveAuthenticationReadError,
        InvalidArchiveAuthenticationFormatError,
        ArchiveAuthenticationFilenameMismatchError,
        ArchiveAuthenticationFormatVersionMismatchError,
        ArchiveAuthenticityMismatchError,
        ArchiveAuthenticationExportError,
        ArchiveAuthenticationMetadataMismatchError,
    ):
        assert issubclass(exception_type, ArchiveAuthenticityError)


def test_concrete_archive_authenticity_errors_are_distinct_classes() -> None:
    classes = {
        ArchiveAuthenticityError,
        ArchiveAuthenticationReadError,
        InvalidArchiveAuthenticationFormatError,
        ArchiveAuthenticationFilenameMismatchError,
        ArchiveAuthenticationFormatVersionMismatchError,
        ArchiveAuthenticityMismatchError,
        ArchiveAuthenticationExportError,
        ArchiveAuthenticationMetadataMismatchError,
    }

    assert len(classes) == 8


def test_archive_signature_error_inherits_from_project_error() -> None:
    assert issubclass(ArchiveSignatureError, AgenticAILabError)


def test_concrete_archive_signature_errors_inherit_from_base_error() -> None:
    for exception_type in (
        MissingArchiveSigningPrivateKeyError,
        InvalidArchiveSigningPrivateKeyError,
        InvalidArchiveSigningKeyIdError,
        InvalidArchiveSignatureTrustStoreError,
        DuplicateArchiveSigningKeyIdError,
        UnknownArchiveSigningKeyError,
        ArchiveSigningKeyNotActiveError,
        ArchiveSigningKeyNotValidError,
        RejectedArchiveSigningKeyError,
        ArchiveSignatureFromFutureError,
        ArchiveSigningKeyFingerprintMismatchError,
        ArchiveSignatureReadError,
        ArchiveSignatureValidationError,
        ArchiveSignatureFilenameMismatchError,
        ArchiveSignatureArchiveDigestMismatchError,
        ArchiveSignatureVerificationError,
        ArchiveSignatureExportError,
    ):
        assert issubclass(exception_type, ArchiveSignatureError)


def test_concrete_archive_signature_errors_are_distinct_classes() -> None:
    exception_types = {
        MissingArchiveSigningPrivateKeyError,
        InvalidArchiveSigningPrivateKeyError,
        InvalidArchiveSigningKeyIdError,
        InvalidArchiveSignatureTrustStoreError,
        DuplicateArchiveSigningKeyIdError,
        UnknownArchiveSigningKeyError,
        ArchiveSigningKeyNotActiveError,
        ArchiveSigningKeyNotValidError,
        RejectedArchiveSigningKeyError,
        ArchiveSignatureFromFutureError,
        ArchiveSigningKeyFingerprintMismatchError,
        ArchiveSignatureReadError,
        ArchiveSignatureValidationError,
        ArchiveSignatureFilenameMismatchError,
        ArchiveSignatureArchiveDigestMismatchError,
        ArchiveSignatureVerificationError,
        ArchiveSignatureExportError,
    }

    assert len(exception_types) == 17


def test_root_signature_trust_error_inherits_from_project_error() -> None:
    assert issubclass(RootSignatureTrustError, AgenticAILabError)


def test_concrete_root_signature_trust_errors_inherit_from_base_error() -> None:
    for exception_type in (
        MissingRootSigningPrivateKeyError,
        InvalidRootSigningPrivateKeyError,
        MissingRootSigningPublicKeyError,
        InvalidRootSigningPublicKeyError,
        RootSigningKeyIdError,
        RootSigningKeyMismatchError,
    ):
        assert issubclass(exception_type, RootSignatureTrustError)


def test_concrete_root_signature_trust_errors_are_distinct_classes() -> None:
    exception_types = {
        RootSignatureTrustError,
        MissingRootSigningPrivateKeyError,
        InvalidRootSigningPrivateKeyError,
        MissingRootSigningPublicKeyError,
        InvalidRootSigningPublicKeyError,
        RootSigningKeyIdError,
        RootSigningKeyMismatchError,
    }

    assert len(exception_types) == 7


def test_signing_key_manifest_error_inherits_from_project_error() -> None:
    assert issubclass(SigningKeyManifestError, AgenticAILabError)


def test_concrete_signing_key_manifest_errors_inherit_from_base_error() -> None:
    for exception_type in (
        SigningKeyManifestReadError,
        SigningKeyManifestValidationError,
        SigningKeyManifestExportError,
        SigningKeyManifestSignatureVerificationError,
        SigningKeyManifestDigestMismatchError,
        SigningKeyManifestMetadataMismatchError,
        SigningKeyManifestRollbackError,
        SigningKeyManifestExpiredError,
        SigningKeyManifestNotYetValidError,
        SigningKeyManifestFromFutureError,
    ):
        assert issubclass(exception_type, SigningKeyManifestError)


def test_concrete_signing_key_manifest_errors_are_distinct_classes() -> None:
    exception_types = {
        SigningKeyManifestError,
        SigningKeyManifestReadError,
        SigningKeyManifestValidationError,
        SigningKeyManifestExportError,
        SigningKeyManifestSignatureVerificationError,
        SigningKeyManifestDigestMismatchError,
        SigningKeyManifestMetadataMismatchError,
        SigningKeyManifestRollbackError,
        SigningKeyManifestExpiredError,
        SigningKeyManifestNotYetValidError,
        SigningKeyManifestFromFutureError,
    }

    assert len(exception_types) == 11
