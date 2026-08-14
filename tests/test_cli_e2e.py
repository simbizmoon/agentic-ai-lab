"""Subprocess end-to-end tests for the installed AIRA CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_subprocess_creates_report_and_json(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.md"
    source.write_text(
        (
            "# 근거 기반 연구\n\n"
            "근거 기반 연구는 주장과 증거 및 출처를 "
            "추적 가능하게 연결한다."
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "research",
            "--question",
            (
                "근거 기반 연구는 주장과 증거를 "
                "어떻게 연결하는가?"
            ),
            "--objective",
            (
                "출처와 인용을 사용하여 근거 기반 "
                "연구의 추적 가능성을 설명한다."
            ),
            "--source",
            str(source),
            "--allowed-root",
            str(source.parent),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert "AIRA report:" in completed.stdout
    assert "AIRA result:" in completed.stdout

    execution_dirs = list(output_dir.iterdir())

    assert len(execution_dirs) == 1

    report_path = execution_dirs[0] / "report.md"
    result_path = execution_dirs[0] / "result.json"

    assert report_path.is_file()
    assert result_path.is_file()

    payload = json.loads(
        result_path.read_text(encoding="utf-8")
    )
    execution_id = execution_dirs[0].name

    assert payload["workspace"]["request"]["request_id"] == (
        execution_id
    )
    assert payload["report"]["request_id"] == execution_id
    assert payload["report"]["claim_count"] >= 1
    assert payload["report"]["citation_count"] >= 1
