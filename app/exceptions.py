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
