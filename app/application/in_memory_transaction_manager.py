"""In-memory application transaction manager."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock
from typing import Any

from app.application.transaction import (
    ApplicationTransactionalResource,
)
from app.application.transaction_error import (
    ApplicationNestedTransactionError,
    ApplicationTransactionRollbackError,
)


class InMemoryApplicationTransactionManager:
    """Coordinate atomic changes across in-memory resources."""

    def __init__(
        self,
        *,
        resources: list[
            ApplicationTransactionalResource[Any]
        ],
    ) -> None:
        if not resources:
            raise ValueError(
                "transaction manager requires at least "
                "one resource"
            )

        if len({id(resource) for resource in resources}) != len(
            resources
        ):
            raise ValueError(
                "transaction resources must be unique"
            )

        self._resources = tuple(resources)
        self._lock = RLock()
        self._active = False

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit normally or restore every resource on error."""

        with self._lock:
            if self._active:
                raise ApplicationNestedTransactionError(
                    "nested application transaction is not "
                    "supported"
                )

            self._active = True

            snapshots = [
                resource.snapshot_state()
                for resource in self._resources
            ]

            try:
                yield
            except BaseException as original_error:
                rollback_errors: list[BaseException] = []

                for resource, snapshot in reversed(
                    list(zip(
                        self._resources,
                        snapshots,
                        strict=True,
                    ))
                ):
                    try:
                        resource.restore_state(snapshot)
                    except Exception as rollback_error:  # noqa: BLE001
                        # Transactional resources may expose
                        # different rollback exception types.
                        rollback_errors.append(rollback_error)

                if rollback_errors:
                    raise ApplicationTransactionRollbackError(
                        "application transaction rollback failed"
                    ) from original_error

                raise
            finally:
                self._active = False
