"""Safely remove expired planning-agent trace archives."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from app.memory.clock import Clock, SystemClock
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionPolicy,
    AgentTraceRetentionResult,
)


class AgentTraceRetentionError(RuntimeError):
    """Raised when trace retention cannot be completed."""


class AgentTraceRetentionService:
    """Apply age and file-count limits to trace archives."""

    _TRACE_SUFFIXES: ClassVar[frozenset[str]] = frozenset(
        {
            ".json",
            ".txt",
            ".md",
        }
    )

    def __init__(
        self,
        *,
        output_directory: Path,
        clock: Clock | None = None,
    ) -> None:
        self._output_directory = (
            output_directory
            .expanduser()
            .resolve()
        )
        self._clock = clock or SystemClock()

    @property
    def output_directory(self) -> Path:
        """Return the configured archive directory."""

        return self._output_directory

    def apply(
        self,
        policy: AgentTraceRetentionPolicy,
    ) -> AgentTraceRetentionResult:
        """Apply one retention policy."""

        files = self._trace_files()

        eligible = self._eligible_files(
            files=files,
            policy=policy,
        )

        deleted_paths: list[Path] = []

        if not policy.dry_run:
            for path in eligible:
                self._delete_file(path)
                deleted_paths.append(path)

        deleted_count = len(deleted_paths)

        return AgentTraceRetentionResult(
            output_directory=self.output_directory,
            scanned_file_count=len(files),
            eligible_file_count=len(eligible),
            deleted_file_count=deleted_count,
            retained_file_count=(
                len(files) - deleted_count
            ),
            dry_run=policy.dry_run,
            eligible_paths=eligible,
            deleted_paths=deleted_paths,
        )

    def _trace_files(self) -> list[Path]:
        """Return safe archive files ordered oldest first."""

        if not self.output_directory.exists():
            return []

        if not self.output_directory.is_dir():
            raise AgentTraceRetentionError(
                "trace output path is not a directory"
            )

        files = [
            path.resolve()
            for path in self.output_directory.iterdir()
            if self._is_trace_file(path)
        ]

        return sorted(
            files,
            key=lambda path: (
                path.stat().st_mtime,
                path.name,
            ),
        )

    def _is_trace_file(self, path: Path) -> bool:
        """Return whether a path is a safe trace file."""

        if path.is_symlink():
            return False

        if not path.is_file():
            return False

        if path.suffix.lower() not in self._TRACE_SUFFIXES:
            return False

        resolved = path.resolve()

        return resolved.parent == self.output_directory

    def _eligible_files(
        self,
        *,
        files: list[Path],
        policy: AgentTraceRetentionPolicy,
    ) -> list[Path]:
        """Return the union of age and count candidates."""

        eligible: set[Path] = set()

        if policy.maximum_age_days is not None:
            cutoff = self._clock.now() - timedelta(
                days=policy.maximum_age_days
            )

            for path in files:
                modified_at = datetime.fromtimestamp(
                    path.stat().st_mtime,
                    tz=UTC,
                )

                if modified_at < cutoff:
                    eligible.add(path)

        if (
            policy.maximum_file_count is not None
            and len(files) > policy.maximum_file_count
        ):
            excess_count = (
                len(files)
                - policy.maximum_file_count
            )
            eligible.update(files[:excess_count])

        return [
            path
            for path in files
            if path in eligible
        ]

    def _delete_file(self, path: Path) -> None:
        """Delete one file after repeating safety checks."""

        resolved = path.resolve()

        if resolved.parent != self.output_directory:
            raise AgentTraceRetentionError(
                "refusing to delete file outside "
                "trace output directory"
            )

        if resolved.is_symlink():
            raise AgentTraceRetentionError(
                "refusing to delete symbolic link"
            )

        if not resolved.is_file():
            raise AgentTraceRetentionError(
                "retention target is not a file"
            )

        if (
            resolved.suffix.lower()
            not in self._TRACE_SUFFIXES
        ):
            raise AgentTraceRetentionError(
                "retention target is not a trace file"
            )

        resolved.unlink()
