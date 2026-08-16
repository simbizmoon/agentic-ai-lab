"""Write AIRA research results as Markdown and JSON."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.schemas.research_pipeline import (
    SingleResearchPipelineResult,
)


@dataclass(frozen=True)
class ResearchResultPaths:
    """Paths created for one research execution."""

    execution_dir: Path
    report_path: Path
    result_path: Path


class ResearchResultWriteError(RuntimeError):
    """Raised when private research artifacts cannot be persisted safely."""


EXECUTION_DIRECTORY_MODE = 0o700
RESEARCH_RESULT_FILE_MODE = 0o600


class ResearchResultWriter:
    """Persist one completed research result."""

    def write(
        self,
        result: SingleResearchPipelineResult,
        *,
        output_dir: Path,
        execution_id: str,
    ) -> ResearchResultPaths:
        """Write private Markdown and JSON without overwriting a run."""

        normalized_execution_id = self._validate_execution_id(execution_id)
        report_text = self._markdown(result)
        payload = result.model_dump(mode="json")
        payload["quality"]["passed"] = result.quality.passed
        result_text = (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )

        root = output_dir.expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise ValueError(f"output path is not a directory: {root}")
        root.mkdir(parents=True, exist_ok=True)
        execution_dir = root / normalized_execution_id

        if execution_dir.is_symlink() or execution_dir.exists():
            raise ValueError(f"execution directory already exists: {execution_dir}")

        try:
            execution_dir.mkdir(mode=EXECUTION_DIRECTORY_MODE)
            os.chmod(execution_dir, EXECUTION_DIRECTORY_MODE)
        except OSError as error:
            try:
                execution_dir.rmdir()
            except OSError:
                pass
            raise ResearchResultWriteError(
                "research execution directory could not be created"
            ) from error

        report_path = execution_dir / "report.md"
        result_path = execution_dir / "result.json"
        self._write_artifacts(
            execution_dir=execution_dir,
            artifacts=((report_path, report_text), (result_path, result_text)),
        )
        return ResearchResultPaths(
            execution_dir=execution_dir,
            report_path=report_path,
            result_path=result_path,
        )

    @staticmethod
    def _validate_execution_id(execution_id: str) -> str:
        if not isinstance(execution_id, str):
            raise TypeError("execution_id must be a string")
        normalized = execution_id.strip()
        path = Path(normalized)
        if not normalized:
            raise ValueError("execution_id must not be blank")
        if (
            normalized in {".", ".."}
            or path.is_absolute()
            or "/" in normalized
            or "\\" in normalized
            or path.parts != (normalized,)
        ):
            raise ValueError("execution_id must be one safe path component")
        return normalized

    def _write_artifacts(
        self,
        *,
        execution_dir: Path,
        artifacts: tuple[tuple[Path, str], ...],
    ) -> None:
        temp_paths: list[Path] = []
        installed_paths: list[Path] = []
        try:
            for target, text in artifacts:
                temp_paths.append(
                    self._prepare_temp_file(
                        execution_dir=execution_dir, target=target, text=text
                    )
                )
            for target, _text in artifacts:
                self._validate_final_target(target)
            for (target, _text), temp_path in zip(artifacts, temp_paths, strict=True):
                os.replace(temp_path, target)
                installed_paths.append(target)
            self._fsync_directory(execution_dir)
        except (OSError, ResearchResultWriteError) as error:
            self._cleanup_failed_write(
                execution_dir=execution_dir,
                temp_paths=temp_paths,
                installed_paths=installed_paths,
            )
            if isinstance(error, ResearchResultWriteError):
                raise
            raise ResearchResultWriteError(
                "research result artifacts could not be written"
            ) from error

    @staticmethod
    def _prepare_temp_file(*, execution_dir: Path, target: Path, text: str) -> Path:
        temp_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=execution_dir,
                prefix=f".{target.name}.",
                suffix=".tmp",
            ) as temp_file:
                temp_path = Path(temp_file.name)
                os.fchmod(temp_file.fileno(), RESEARCH_RESULT_FILE_MODE)
                temp_file.write(text)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            return temp_path
        except OSError:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    @staticmethod
    def _validate_final_target(target: Path) -> None:
        if target.is_symlink() or target.exists():
            raise ResearchResultWriteError("research result artifact target is unsafe")

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    @staticmethod
    def _cleanup_failed_write(
        *,
        execution_dir: Path,
        temp_paths: list[Path],
        installed_paths: list[Path],
    ) -> None:
        for path in (*temp_paths, *installed_paths):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            execution_dir.rmdir()
        except OSError:
            pass

    @staticmethod
    def _markdown(
        result: SingleResearchPipelineResult,
    ) -> str:
        """Render the final report as readable Markdown."""

        report = result.report
        quality = result.quality
        lines = [
            f"# {report.title}",
            "",
            "## Executive Summary",
            "",
            report.executive_summary,
            "",
        ]

        for section in report.ordered_sections():
            lines.extend(
                [
                    f"## {section.title}",
                    "",
                    section.content,
                    "",
                ]
            )

        lines.extend(
            [
                "## Sources",
                "",
            ]
        )

        for citation in report.citations:
            lines.extend(
                [
                    (f"- **{citation.label}** [{citation.title}]({citation.url})"),
                    f"  - {citation.excerpt}",
                ]
            )

        lines.extend(
            [
                "",
                "## Quality",
                "",
                f"- Overall score: {quality.overall_score:.2f}",
                f"- Quality level: {quality.quality_level.value}",
                (f"- Passed: {'yes' if quality.passed else 'no'}"),
                f"- Claims: {report.claim_count}",
                f"- Citations: {report.citation_count}",
                f"- Sources: {report.source_count}",
            ]
        )

        if quality.issues:
            lines.extend(
                [
                    "",
                    "### Quality Issues",
                    "",
                ]
            )

            for issue in quality.issues:
                lines.append(f"- [{issue.severity.value}] {issue.message}")

        return "\n".join(lines).rstrip() + "\n"
