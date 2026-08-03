"""Tests for safe agent trace file writing."""

from pathlib import Path

import pytest

from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
    AgentTraceExportResult,
)
from app.schemas.agent_trace_file import (
    AgentTraceFileWriteRequest,
)
from app.tracing.agent_trace_file_writer import (
    AgentTraceFileAlreadyExistsError,
    AgentTraceFileWriter,
    AgentTraceInvalidFileNameError,
)


def exported_json(
    *,
    trace_id: str = "trace-001",
) -> AgentTraceExportResult:
    """Return one JSON trace export."""

    return AgentTraceExportResult(
        trace_id=trace_id,
        format=AgentTraceExportFormat.JSON,
        content='{"trace_id": "trace-001"}',
        media_type="application/json",
        file_extension=".json",
    )


def test_writer_creates_default_file(
    tmp_path: Path,
) -> None:
    writer = AgentTraceFileWriter(
        output_directory=tmp_path
    )

    result = writer.write(
        export=exported_json()
    )

    assert result.path == (
        tmp_path / "trace-001.json"
    ).resolve()
    assert result.path.read_text(
        encoding="utf-8"
    ) == '{"trace_id": "trace-001"}'
    assert result.overwritten is False


def test_writer_appends_expected_extension(
    tmp_path: Path,
) -> None:
    result = AgentTraceFileWriter(
        output_directory=tmp_path
    ).write(
        export=exported_json(),
        request=AgentTraceFileWriteRequest(
            file_name="custom-trace"
        ),
    )

    assert result.path.name == "custom-trace.json"


def test_writer_rejects_wrong_extension(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        AgentTraceInvalidFileNameError,
        match="extension does not match",
    ):
        AgentTraceFileWriter(
            output_directory=tmp_path
        ).write(
            export=exported_json(),
            request=AgentTraceFileWriteRequest(
                file_name="trace.txt"
            ),
        )


@pytest.mark.parametrize(
    "file_name",
    [
        "../trace.json",
        "nested/trace.json",
        "/tmp/trace.json",
        "trace name.json",
        "..",
    ],
)
def test_writer_rejects_unsafe_file_name(
    tmp_path: Path,
    file_name: str,
) -> None:
    with pytest.raises(
        AgentTraceInvalidFileNameError
    ):
        AgentTraceFileWriter(
            output_directory=tmp_path
        ).write(
            export=exported_json(),
            request=AgentTraceFileWriteRequest(
                file_name=file_name
            ),
        )


def test_writer_does_not_overwrite_by_default(
    tmp_path: Path,
) -> None:
    writer = AgentTraceFileWriter(
        output_directory=tmp_path
    )
    writer.write(export=exported_json())

    with pytest.raises(
        AgentTraceFileAlreadyExistsError,
        match="already exists",
    ):
        writer.write(export=exported_json())


def test_writer_overwrites_when_enabled(
    tmp_path: Path,
) -> None:
    writer = AgentTraceFileWriter(
        output_directory=tmp_path
    )
    target = tmp_path / "trace-001.json"
    target.write_text(
        "old",
        encoding="utf-8",
    )

    result = writer.write(
        export=exported_json(),
        request=AgentTraceFileWriteRequest(
            overwrite=True
        ),
    )

    assert result.overwritten is True
    assert target.read_text(
        encoding="utf-8"
    ) == '{"trace_id": "trace-001"}'


def test_writer_sanitizes_default_trace_id(
    tmp_path: Path,
) -> None:
    result = AgentTraceFileWriter(
        output_directory=tmp_path
    ).write(
        export=exported_json(
            trace_id="trace:customer/001"
        )
    )

    assert result.path.name == (
        "trace-customer-001.json"
    )
