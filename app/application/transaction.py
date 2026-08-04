"""Application transaction boundary contracts."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol, TypeVar, runtime_checkable

SnapshotT = TypeVar("SnapshotT")


@runtime_checkable
class ApplicationTransactionalResource(
    Protocol[SnapshotT]
):
    """Resource whose state can participate in a transaction."""

    def snapshot_state(self) -> SnapshotT:
        """Return an isolated snapshot of current state."""

    def restore_state(
        self,
        snapshot: SnapshotT,
    ) -> None:
        """Restore a previously captured state snapshot."""


@runtime_checkable
class ApplicationTransactionManager(Protocol):
    """Application-level transaction boundary."""

    def transaction(
        self,
    ) -> AbstractContextManager[None]:
        """Return one transaction context manager."""
