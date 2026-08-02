"""Project-specific exception hierarchy."""


class AgenticAILabError(Exception):
    """Base exception for Agentic AI Lab errors."""


class StructuredAnalysisError(AgenticAILabError):
    """Base exception for structured analysis errors."""


class StructuredResponseIncompleteError(StructuredAnalysisError):
    """Raised when a structured response is incomplete."""


class StructuredResponseRefusalError(StructuredAnalysisError):
    """Raised when a structured response contains a refusal."""


class StructuredResponseParseError(StructuredAnalysisError):
    """Raised when a structured response cannot be parsed."""


class StructuredResponseStatusError(StructuredAnalysisError):
    """Raised when a structured response has an unexpected status."""


class StructuredResponseValidationError(StructuredAnalysisError):
    """Raised when a structured response fails schema validation."""

    def __init__(
        self,
        message: str,
        *,
        elapsed_seconds: float = 0.0,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.elapsed_seconds = elapsed_seconds
        self.attempts = attempts


class ExecutionBudgetError(AgenticAILabError):
    """Base exception for execution budget errors."""


class AttemptBudgetExceededError(ExecutionBudgetError):
    """Raised when the execution attempt budget is exceeded."""


class TokenBudgetExceededError(ExecutionBudgetError):
    """Raised when the recorded token budget is exceeded."""


class TimeBudgetExceededError(ExecutionBudgetError):
    """Raised when the execution time budget is exceeded."""


class AuditLogError(AgenticAILabError):
    """Raised when an audit log event cannot be written."""


class AuditLogReadError(AuditLogError):
    """Raised when an audit log cannot be read."""


class AuditLogParseError(AuditLogError):
    """Raised when an audit log line is not valid JSON."""


class UnsupportedAuditSchemaError(AuditLogError):
    """Raised when an audit log event uses an unsupported schema."""


class InvalidAuditEventError(AuditLogError):
    """Raised when an audit log event is structurally invalid."""


class AuditReportValidationError(AuditLogError):
    """Raised when an audit report output contract is invalid."""


class SchemaCompatibilityError(AgenticAILabError):
    """Raised when a published schema contract changes unexpectedly."""


class SchemaMigrationError(AgenticAILabError):
    """Base exception for schema migration errors."""


class InvalidSchemaVersionError(SchemaMigrationError):
    """Raised when a schema version is invalid."""


class UnsupportedSchemaVersionError(SchemaMigrationError):
    """Raised when a schema version is no longer supported."""


class SchemaDowngradeError(SchemaMigrationError):
    """Raised when a downgrade migration is requested."""


class InvalidMigrationRegistryError(SchemaMigrationError):
    """Raised when a migration registry is structurally invalid."""


class MissingSchemaMigrationError(SchemaMigrationError):
    """Raised when a required migration step is not registered."""


class SchemaMigrationStepError(SchemaMigrationError):
    """Raised when a migration step fails or returns an invalid result."""


class ReportExportError(AgenticAILabError):
    """Base exception for audit report export errors."""


class InvalidReportExportPathError(ReportExportError):
    """Raised when an audit report export path is invalid."""


class ReportExportWriteError(ReportExportError):
    """Raised when an audit report cannot be written safely."""


class ReportIntegrityError(AgenticAILabError):
    """Base exception for audit report integrity errors."""


class ReportIntegrityReadError(ReportIntegrityError):
    """Raised when an audit report or checksum cannot be read."""


class InvalidChecksumFormatError(ReportIntegrityError):
    """Raised when a checksum sidecar has an invalid format."""


class ChecksumFilenameMismatchError(ReportIntegrityError):
    """Raised when a checksum sidecar references a different report filename."""


class ReportIntegrityMismatchError(ReportIntegrityError):
    """Raised when an audit report checksum does not match."""


class ChecksumExportError(ReportIntegrityError):
    """Raised when a checksum sidecar cannot be written safely."""


class ReportAuthenticityError(AgenticAILabError):
    """Base exception for audit report authenticity errors."""


class MissingAuthenticationKeyError(ReportAuthenticityError):
    """Raised when an authentication key is missing."""


class InvalidAuthenticationKeyError(ReportAuthenticityError):
    """Raised when an authentication key is invalid."""


class InvalidAuthenticationKeyIdError(ReportAuthenticityError):
    """Raised when an authentication key ID is invalid."""




class AuthenticationTrustError(ReportAuthenticityError):
    """Base exception for authentication trust policy errors."""


class AuthenticationKeyringError(AuthenticationTrustError):
    """Base exception for authentication keyring configuration errors."""


class MissingAuthenticationKeyringError(AuthenticationKeyringError):
    """Raised when an authentication keyring is missing."""


class InvalidAuthenticationKeyringError(AuthenticationKeyringError):
    """Raised when an authentication keyring is invalid."""


class DuplicateAuthenticationKeyIdError(AuthenticationKeyringError):
    """Raised when authentication key IDs are duplicated."""


class ActiveAuthenticationKeyNotFoundError(AuthenticationKeyringError):
    """Raised when the active authentication key is not registered."""


class InvalidAuthenticationTrustStoreError(AuthenticationTrustError):
    """Raised when an authentication trust store is invalid."""


class NoActiveAuthenticationKeyError(AuthenticationTrustError):
    """Raised when no key is active for signing at the requested time."""


class MultipleActiveAuthenticationKeysError(AuthenticationTrustError):
    """Raised when more than one key is active for signing."""


class AuthenticationKeyNotValidAtSigningTimeError(AuthenticationTrustError):
    """Raised when a key was not valid at authentication time."""


class RejectedAuthenticationKeyError(AuthenticationTrustError):
    """Raised when trust policy rejects an authentication key."""


class AuthenticationFromFutureError(AuthenticationTrustError):
    """Raised when authenticated_at is too far in the future."""


class ReportAuthenticationReadError(ReportAuthenticityError):
    """Raised when an authentication sidecar or report cannot be read."""


class InvalidAuthenticationFormatError(ReportAuthenticityError):
    """Raised when an authentication sidecar has an invalid format."""


class AuthenticationFilenameMismatchError(ReportAuthenticityError):
    """Raised when an authentication sidecar references a different report."""


class UnknownAuthenticationKeyError(ReportAuthenticityError):
    """Raised when an authentication key ID is not available."""


class ReportAuthenticityMismatchError(ReportAuthenticityError):
    """Raised when an authentication code does not match."""


class AuthenticationExportError(ReportAuthenticityError):
    """Raised when an authentication sidecar cannot be written safely."""


class ReportBundleError(AgenticAILabError):
    """Base exception for audit report bundle errors."""


class ReportBundleManifestValidationError(ReportBundleError):
    """Raised when a bundle manifest contract is invalid."""


class ReportBundleReadError(ReportBundleError):
    """Raised when a bundle manifest cannot be read."""


class ReportBundleExportError(ReportBundleError):
    """Raised when a bundle manifest cannot be written safely."""


class IncompleteReportBundleError(ReportBundleError):
    """Raised when a required bundle file is missing."""


class BundleReportFilenameMismatchError(ReportBundleError):
    """Raised when a manifest references a different report filename."""


class ReportBundleDigestMismatchError(ReportBundleError):
    """Raised when a bundle file digest does not match the manifest."""


class ReportBundleMetadataMismatchError(ReportBundleError):
    """Raised when bundle metadata is inconsistent with verified files."""
