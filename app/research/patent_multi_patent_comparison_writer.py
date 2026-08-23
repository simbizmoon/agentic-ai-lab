"""Safely persist deterministic patent comparison artifacts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.research.patent_multi_patent_comparison_formatter import (
    DeterministicPatentMultiPatentComparisonFormatter,
)
from app.schemas.patent_multi_patent_comparison import PatentMultiPatentComparison

PATENT_COMPARISON_DIRECTORY_MODE = 0o700
PATENT_COMPARISON_FILE_MODE = 0o600


@dataclass(frozen=True)
class PatentMultiPatentComparisonArtifactPaths:
    """Paths created for one persisted patent comparison."""

    execution_dir: Path
    markdown_path: Path
    json_path: Path


class PatentMultiPatentComparisonWriteError(RuntimeError):
    """Raised when private comparison artifacts cannot be persisted safely."""


class PatentMultiPatentComparisonWriter:
    """Persist one Step 4F comparison as private Markdown and JSON files."""

    def __init__(
        self,
        *,
        formatter: DeterministicPatentMultiPatentComparisonFormatter | None = None,
    ) -> None:
        self._formatter = (
            formatter or DeterministicPatentMultiPatentComparisonFormatter()
        )

    def write(
        self,
        comparison: PatentMultiPatentComparison,
        *,
        output_dir: Path,
        execution_id: str,
    ) -> PatentMultiPatentComparisonArtifactPaths:
        """Create a new private execution directory without overwriting a run."""

        if not isinstance(comparison, PatentMultiPatentComparison):
            raise TypeError("comparison must be a PatentMultiPatentComparison")
        if not isinstance(output_dir, Path):
            raise TypeError("output_dir must be a Path")

        normalized_execution_id = self._validate_execution_id(execution_id)
        formatted = self._formatter.format(comparison)

        root = output_dir.expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise ValueError(f"output path is not a directory: {root}")
        root.mkdir(parents=True, exist_ok=True)
        execution_dir = root / normalized_execution_id

        if execution_dir.is_symlink() or execution_dir.exists():
            raise ValueError(f"execution directory already exists: {execution_dir}")

        try:
            execution_dir.mkdir(mode=PATENT_COMPARISON_DIRECTORY_MODE)
            os.chmod(execution_dir, PATENT_COMPARISON_DIRECTORY_MODE)
        except OSError as error:
            try:
                execution_dir.rmdir()
            except OSError:
                pass
            raise PatentMultiPatentComparisonWriteError(
                "patent comparison execution directory could not be created"
            ) from error

        markdown_path = execution_dir / "comparison.md"
        json_path = execution_dir / "comparison.json"
        self._write_artifacts(
            execution_dir=execution_dir,
            artifacts=(
                (markdown_path, formatted.markdown),
                (json_path, formatted.json_text),
            ),
        )
        return PatentMultiPatentComparisonArtifactPaths(
            execution_dir=execution_dir,
            markdown_path=markdown_path,
            json_path=json_path,
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
                        execution_dir=execution_dir,
                        target=target,
                        text=text,
                    )
                )
            for target, _text in artifacts:
                self._validate_final_target(target)
            for (target, _text), temp_path in zip(
                artifacts,
                temp_paths,
                strict=True,
            ):
                os.replace(temp_path, target)
                installed_paths.append(target)
            self._fsync_directory(execution_dir)
        except (OSError, PatentMultiPatentComparisonWriteError) as error:
            self._cleanup_failed_write(
                execution_dir=execution_dir,
                temp_paths=temp_paths,
                installed_paths=installed_paths,
            )
            if isinstance(error, PatentMultiPatentComparisonWriteError):
                raise
            raise PatentMultiPatentComparisonWriteError(
                "patent comparison artifacts could not be written"
            ) from error

    @staticmethod
    def _prepare_temp_file(
        *,
        execution_dir: Path,
        target: Path,
        text: str,
    ) -> Path:
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
                os.fchmod(temp_file.fileno(), PATENT_COMPARISON_FILE_MODE)
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
            raise PatentMultiPatentComparisonWriteError(
                "patent comparison artifact target is unsafe"
            )

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
