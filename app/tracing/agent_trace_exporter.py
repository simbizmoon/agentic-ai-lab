"""Export readable planning-agent trace views."""

from __future__ import annotations

import json
from typing import Any

from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
    AgentTraceExportResult,
)
from app.schemas.agent_trace_summary import (
    AgentTraceSummary,
)
from app.schemas.agent_trace_timeline import (
    AgentTraceTimeline,
)


class AgentTraceExporter:
    """Serialize trace timelines and summaries."""

    def export(
        self,
        *,
        timeline: AgentTraceTimeline,
        summary: AgentTraceSummary,
        format: AgentTraceExportFormat,
    ) -> AgentTraceExportResult:
        """Export one trace in the requested format."""

        self._validate_trace_ids(
            timeline=timeline,
            summary=summary,
        )

        exporters = {
            AgentTraceExportFormat.JSON: (
                self._export_json
            ),
            AgentTraceExportFormat.TEXT: (
                self._export_text
            ),
            AgentTraceExportFormat.MARKDOWN: (
                self._export_markdown
            ),
        }

        content, media_type, file_extension = (
            exporters[format](
                timeline=timeline,
                summary=summary,
            )
        )

        return AgentTraceExportResult(
            trace_id=timeline.trace_id,
            format=format,
            content=content,
            media_type=media_type,
            file_extension=file_extension,
        )

    @staticmethod
    def _validate_trace_ids(
        *,
        timeline: AgentTraceTimeline,
        summary: AgentTraceSummary,
    ) -> None:
        """Ensure both read models represent one trace."""

        if timeline.trace_id != summary.trace_id:
            raise ValueError(
                "timeline and summary trace IDs must match"
            )

    @staticmethod
    def _export_json(
        *,
        timeline: AgentTraceTimeline,
        summary: AgentTraceSummary,
    ) -> tuple[str, str, str]:
        """Return a deterministic JSON export."""

        payload: dict[str, Any] = {
            "summary": summary.model_dump(
                mode="json"
            ),
            "timeline": timeline.model_dump(
                mode="json"
            ),
        }

        content = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

        return (
            content,
            "application/json",
            ".json",
        )

    @staticmethod
    def _export_text(
        *,
        timeline: AgentTraceTimeline,
        summary: AgentTraceSummary,
    ) -> tuple[str, str, str]:
        """Return a human-readable plain-text export."""

        lines = [
            f"Trace: {summary.trace_id}",
            f"Outcome: {summary.outcome.value}",
            f"Duration: {summary.duration_ms} ms",
            f"Attempts: {summary.attempt_count}",
            f"Plans: {summary.plan_count}",
            f"Replans: {summary.replanning_count}",
            (
                "Steps: "
                f"started={summary.step_started_count}, "
                f"completed={summary.step_completed_count}, "
                f"failed={summary.step_failed_count}, "
                f"skipped={summary.step_skipped_count}"
            ),
            (
                "Tools: "
                f"started={summary.tool_started_count}, "
                f"completed={summary.tool_completed_count}, "
                f"failed={summary.tool_failed_count}"
            ),
            f"Final plan: {summary.final_plan_id or '-'}",
            f"Final message: {summary.final_message}",
            "",
            "Timeline",
            "--------",
        ]

        lines.extend(
            AgentTraceExporter._timeline_text_lines(
                timeline
            )
        )

        return (
            "\n".join(lines),
            "text/plain",
            ".txt",
        )

    @staticmethod
    def _export_markdown(
        *,
        timeline: AgentTraceTimeline,
        summary: AgentTraceSummary,
    ) -> tuple[str, str, str]:
        """Return a Markdown trace report."""

        lines = [
            f"# Agent Trace `{summary.trace_id}`",
            "",
            "## Summary",
            "",
            f"- Outcome: `{summary.outcome.value}`",
            f"- Duration: `{summary.duration_ms} ms`",
            f"- Attempts: `{summary.attempt_count}`",
            f"- Plans: `{summary.plan_count}`",
            f"- Replans: `{summary.replanning_count}`",
            (
                "- Steps: "
                f"`{summary.step_completed_count}` completed, "
                f"`{summary.step_failed_count}` failed, "
                f"`{summary.step_skipped_count}` skipped"
            ),
            (
                "- Tools: "
                f"`{summary.tool_completed_count}` completed, "
                f"`{summary.tool_failed_count}` failed"
            ),
            (
                "- Final plan: "
                f"`{summary.final_plan_id or '-'}`"
            ),
            f"- Final message: {summary.final_message}",
            "",
            "## Timeline",
            "",
            "| Seq | Elapsed | Event | Attempt | Plan | Step | Tool | Message |",
            "|---:|---:|---|---:|---|---|---|---|",
        ]

        for item in timeline.items:
            lines.append(
                "| "
                f"{item.sequence} | "
                f"{item.elapsed_ms} ms | "
                f"`{item.event_type.value}` | "
                f"{item.attempt_number or '-'} | "
                f"{item.plan_id or '-'} | "
                f"{item.step_id or '-'} | "
                f"{item.tool_name or '-'} | "
                f"{_escape_markdown(item.message)} |"
            )

        return (
            "\n".join(lines),
            "text/markdown",
            ".md",
        )

    @staticmethod
    def _timeline_text_lines(
        timeline: AgentTraceTimeline,
    ) -> list[str]:
        """Render timeline items as plain-text lines."""

        return [
            (
                f"[{item.sequence:03d}] "
                f"+{item.elapsed_ms}ms "
                f"{item.event_type.value} "
                f"attempt={item.attempt_number or '-'} "
                f"plan={item.plan_id or '-'} "
                f"step={item.step_id or '-'} "
                f"tool={item.tool_name or '-'} "
                f"- {item.message}"
            )
            for item in timeline.items
        ]


def _escape_markdown(value: str) -> str:
    """Escape text used inside a Markdown table cell."""

    return (
        value
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", " ")
    )
