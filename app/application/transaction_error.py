"""Errors raised by application transaction managers."""

from __future__ import annotations


class ApplicationTransactionError(RuntimeError):
    """Base application transaction error."""


class ApplicationNestedTransactionError(
    ApplicationTransactionError
):
    """Raised when a nested transaction is attempted."""


class ApplicationTransactionRollbackError(
    ApplicationTransactionError
):
    """Raised when transaction rollback cannot complete."""
