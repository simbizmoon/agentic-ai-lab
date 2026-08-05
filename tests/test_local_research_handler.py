"""Tests for the default local research handler."""

from __future__ import annotations

import io
import json
from pathlib import Path

from app.research.local_research_handler import (
    LocalResearchHandler,
)


def test_handler_runs_pipeline_and_writes_results(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.md"
    source.write_text(
        (
            "# Grounded Research\n\n"
            "Grounded research connects claims to "
            "traceable evidence."
        ),
        encoding="utf-8",
    )
    stdout = io.StringIO()
    handler = LocalResearchHandler(
        id_factory=lambda: "handler-001",
        stdout=stdout,
    )

    status = handler(
        (
            "How does grounded research connect claims "
            "to evidence?"
        ),
        (
            "Explain how claims are connected to "
            "traceable evidence."
        ),
        (source,),
        tmp_path / "reports",
    )

    execution_dir = tmp_path / "reports" / "handler-001"
    report_path = execution_dir / "report.md"
    result_path = execution_dir / "result.json"

    assert status == 0
    assert report_path.is_file()
    assert result_path.is_file()
    assert "AIRA report:" in stdout.getvalue()
    assert "AIRA result:" in stdout.getvalue()

    payload = json.loads(
        result_path.read_text(encoding="utf-8")
    )
    assert payload["workspace"]["request"]["request_id"] == (
        "handler-001"
    )
