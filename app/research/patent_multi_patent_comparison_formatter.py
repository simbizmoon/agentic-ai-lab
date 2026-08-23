"""Deterministic JSON and Markdown formatting for patent comparisons."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.schemas.patent_multi_patent_comparison import PatentMultiPatentComparison


@dataclass(frozen=True)
class PatentMultiPatentComparisonFormats:
    """Two deterministic, in-memory representations of one comparison."""

    markdown: str
    json_text: str


class DeterministicPatentMultiPatentComparisonFormatter:
    """Format an existing Step 4F artifact without adding new judgments."""

    def format(
        self,
        comparison: PatentMultiPatentComparison,
    ) -> PatentMultiPatentComparisonFormats:
        if not isinstance(comparison, PatentMultiPatentComparison):
            raise TypeError("comparison must be a PatentMultiPatentComparison")

        return PatentMultiPatentComparisonFormats(
            markdown=self._markdown(comparison),
            json_text=(
                json.dumps(
                    comparison.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            ),
        )

    def _markdown(self, comparison: PatentMultiPatentComparison) -> str:
        lines = [
            "# Patent Multi-Patent Technical Comparison",
            "",
            f"- Target publication: {comparison.target_publication_number}",
            f"- Target DOCDB identity: {comparison.target_publication_docdb}",
            f"- Target source: {comparison.target_source_endpoint}",
            "- Prior-art publication axis: "
            + (
                ", ".join(comparison.prior_art_publications)
                if comparison.prior_art_publications
                else "None"
            ),
            "",
        ]

        for claim_set in comparison.claim_sets:
            lines.extend([f"## Claim Set — {claim_set.language}", ""])
            for claim in claim_set.claims:
                lines.extend(
                    [
                        (
                            f"### Claim {claim.claim_number} "
                            f"(provider position {claim.provider_position})"
                        ),
                        "",
                        "Original claim:",
                        "",
                    ]
                )
                self._append_exact_text(lines, claim.original_claim_text)

                for row in claim.rows:
                    lines.extend(
                        [
                            (
                                f"#### Row {row.row_number} — "
                                f"Element {row.element_number}"
                            ),
                            "",
                            "Element text:",
                            "",
                        ]
                    )
                    self._append_exact_text(lines, row.element_text)

                    if not row.publications:
                        lines.extend(["No mapped evidence.", ""])
                        continue

                    for publication in row.publications:
                        lines.extend(
                            [
                                f"##### Publication {publication.publication_number}",
                                "",
                            ]
                        )
                        for index, evaluation in enumerate(
                            publication.evaluations,
                            start=1,
                        ):
                            judgment = evaluation.judgment
                            lines.extend(
                                [
                                    f"###### Evaluation {index}",
                                    "",
                                    f"- Evidence ID: {evaluation.evidence_id}",
                                    f"- Source ID: {evaluation.source_id}",
                                    f"- Document ID: {evaluation.document_id}",
                                    (
                                        "- Character range: "
                                        f"{evaluation.start_character}:"
                                        f"{evaluation.end_character}"
                                    ),
                                    (
                                        "- Technical relevance: "
                                        f"{judgment.relevance_level.value} "
                                        f"({judgment.relevance_score:.3f})"
                                    ),
                                    f"- Rationale: {judgment.rationale}",
                                ]
                            )
                            if judgment.issues:
                                lines.extend(["- Issues:", ""])
                                lines.extend(
                                    f"  - {issue}" for issue in judgment.issues
                                )
                                lines.append("")
                            else:
                                lines.extend(["- Issues: None", ""])

                            lines.extend(["Excerpt:", ""])
                            self._append_exact_text(lines, evaluation.excerpt)

        lines.extend(
            [
                "## Scope Notice",
                "",
                comparison.scope_notice,
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _append_exact_text(lines: list[str], text: str) -> None:
        fence = DeterministicPatentMultiPatentComparisonFormatter._fence(text)
        lines.extend([fence, text, fence, ""])

    @staticmethod
    def _fence(text: str) -> str:
        longest_run = 0
        current_run = 0
        for character in text:
            if character == "`":
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 0
        return "`" * max(3, longest_run + 1)
