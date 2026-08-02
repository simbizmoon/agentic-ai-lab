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
