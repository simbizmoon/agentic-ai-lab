"""Write AIRA research results as Markdown and JSON."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.schemas.research_pipeline import (
    SingleResearchPipelineResult,
)


@dataclass(frozen=True)
class ResearchResultPaths:
    """Paths created for one research execution."""

    execution_dir: Path
    report_path: Path
    result_path: Path


class ResearchResultWriter:
    """Persist one completed research result."""

    def write(
        self,
        result: SingleResearchPipelineResult,
        *,
        output_dir: Path,
        execution_id: str,
    ) -> ResearchResultPaths:
        """Write Markdown and JSON without overwriting a run."""

        normalized_execution_id = execution_id.strip()

        if not normalized_execution_id:
            raise ValueError("execution_id must not be blank")

        root = output_dir.expanduser().resolve()

        if root.exists() and not root.is_dir():
            raise ValueError(
                f"output path is not a directory: {root}"
            )

        root.mkdir(parents=True, exist_ok=True)
        execution_dir = root / normalized_execution_id

        if execution_dir.exists():
            raise ValueError(
                f"execution directory already exists: "
                f"{execution_dir}"
            )

        execution_dir.mkdir()
        report_path = execution_dir / "report.md"
        result_path = execution_dir / "result.json"

        report_path.write_text(
            self._markdown(result),
            encoding="utf-8",
        )
        result_path.write_text(
            result.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )

        return ResearchResultPaths(
            execution_dir=execution_dir,
            report_path=report_path,
            result_path=result_path,
        )

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
                    (
                        f"- **{citation.label}** "
                        f"[{citation.title}]({citation.url})"
                    ),
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
                (
                    "- Passed: "
                    f"{'yes' if quality.passed else 'no'}"
                ),
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
                lines.append(
                    f"- [{issue.severity.value}] {issue.message}"
                )

        return "\n".join(lines).rstrip() + "\n"
