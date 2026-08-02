from app.exceptions import (
    AgenticAILabError,
    AttemptBudgetExceededError,
    AuditLogError,
    AuditLogParseError,
    AuditLogReadError,
    AuditReportValidationError,
    AuthenticationExportError,
    AuthenticationFilenameMismatchError,
    ChecksumExportError,
    ChecksumFilenameMismatchError,
    ExecutionBudgetError,
    InvalidAuditEventError,
    InvalidAuthenticationFormatError,
    InvalidAuthenticationKeyError,
    InvalidAuthenticationKeyIdError,
    InvalidChecksumFormatError,
    InvalidMigrationRegistryError,
    InvalidReportExportPathError,
    InvalidSchemaVersionError,
    MissingAuthenticationKeyError,
    MissingSchemaMigrationError,
    ReportAuthenticationReadError,
    ReportAuthenticityError,
    ReportAuthenticityMismatchError,
    ReportExportError,
    ReportExportWriteError,
    ReportIntegrityError,
    ReportIntegrityMismatchError,
    ReportIntegrityReadError,
    SchemaCompatibilityError,
    SchemaDowngradeError,
    SchemaMigrationError,
    SchemaMigrationStepError,
    StructuredAnalysisError,
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
