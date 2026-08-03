"""Safely write exported planning-agent traces to files."""

from __future__ import annotations

import re
from pathlib import Path

from app.schemas.agent_trace_export import (
    AgentTraceExportResult,
)
from app.schemas.agent_trace_file import (
    AgentTraceFileWriteRequest,
    AgentTraceFileWriteResult,
)


class AgentTraceFileWriterError(RuntimeError):
    """Base error for trace file writing."""


class AgentTraceFileAlreadyExistsError(
    AgentTraceFileWriterError
):
    """Raised when a target exists and overwrite is disabled."""


class AgentTraceInvalidFileNameError(
    AgentTraceFileWriterError
):
    """Raised when a custom file name is unsafe."""


class AgentTraceFileWriter:
    """Write trace exports inside one configured directory."""

    _SAFE_FILE_NAME = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
    )

    def __init__(
        self,
        *,
        output_directory: Path,
    ) -> None:
        resolved = output_directory.expanduser().resolve()

        self._output_directory = resolved

    @property
    def output_directory(self) -> Path:
        """Return the configured absolute output directory."""

        return self._output_directory

    def write(
        self,
        *,
        export: AgentTraceExportResult,
        request: AgentTraceFileWriteRequest | None = None,
    ) -> AgentTraceFileWriteResult:
        """Write one trace export to disk."""

        options = request or AgentTraceFileWriteRequest()
        file_name = self._resolve_file_name(
            export=export,
            requested_file_name=options.file_name,
        )
        target = self._safe_target(file_name)

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        existed = target.exists()

        if existed and not options.overwrite:
            raise AgentTraceFileAlreadyExistsError(
                f"trace export already exists: {target.name}"
            )

        encoded = export.content.encode("utf-8")
        target.write_bytes(encoded)

        return AgentTraceFileWriteResult(
            trace_id=export.trace_id,
            format=export.format,
            path=target,
            byte_count=len(encoded),
            overwritten=existed,
        )

    def _resolve_file_name(
        self,
        *,
        export: AgentTraceExportResult,
        requested_file_name: str | None,
    ) -> str:
        """Return a validated output file name."""

        if requested_file_name is None:
            trace_component = self._sanitize_trace_id(
                export.trace_id
            )
            return (
                f"{trace_component}"
                f"{export.file_extension}"
            )

        file_name = requested_file_name.strip()

        self._validate_file_name(file_name)

        if Path(file_name).suffix:
            if (
                Path(file_name).suffix
                != export.file_extension
            ):
                raise AgentTraceInvalidFileNameError(
                    "file extension does not match "
                    "export format"
                )
            return file_name

        return f"{file_name}{export.file_extension}"

    def _safe_target(self, file_name: str) -> Path:
        """Return a target guaranteed to remain in root."""

        self._validate_file_name(file_name)

        target = (
            self.output_directory / file_name
        ).resolve()

        if target.parent != self.output_directory:
            raise AgentTraceInvalidFileNameError(
                "target path escapes output directory"
            )

        return target

    @classmethod
    def _validate_file_name(
        cls,
        file_name: str,
    ) -> None:
        """Reject path separators and unsafe file names."""

        if not file_name:
            raise AgentTraceInvalidFileNameError(
                "file name must not be blank"
            )

        if file_name in {".", ".."}:
            raise AgentTraceInvalidFileNameError(
                "file name is not allowed"
            )

        if Path(file_name).name != file_name:
            raise AgentTraceInvalidFileNameError(
                "file name must not contain a path"
            )

        if not cls._SAFE_FILE_NAME.fullmatch(file_name):
            raise AgentTraceInvalidFileNameError(
                "file name contains unsafe characters"
            )

    @staticmethod
    def _sanitize_trace_id(trace_id: str) -> str:
        """Convert a trace identifier into a safe file stem."""

        sanitized = re.sub(
            r"[^A-Za-z0-9._-]+",
            "-",
            trace_id.strip(),
        ).strip("._-")

        if not sanitized:
            raise AgentTraceInvalidFileNameError(
                "trace_id cannot produce a safe file name"
            )

        return sanitized
