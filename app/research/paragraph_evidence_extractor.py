"""Deterministic paragraph evidence extraction for live web documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.research.research_evidence_extractor import (
    ResearchEvidenceExtractor,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionResult,
    ResearchEvidenceExtractionStatus,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
)

_WORD_PATTERN = re.compile(r"[A-Za-z0-9가-힣]{3,}")
_CODE_MARKERS = (
    "authorization:",
    "api_key",
    "import ",
    "curl ",
    "requests.post",
    "client.responses",
)


@dataclass(frozen=True)
class _Chunk:
    start: int
    end: int
    text: str
    score: float


class ParagraphEvidenceExtractor(ResearchEvidenceExtractor):
    """Select concise, traceable paragraphs from a live document."""

    def __init__(
        self,
        *,
        maximum_evidence: int = 3,
        maximum_characters: int = 1_200,
        minimum_characters: int = 80,
    ) -> None:
        if maximum_evidence < 1:
            raise ValueError(
                "maximum_evidence must be greater than zero"
            )
        if maximum_characters < 200:
            raise ValueError(
                "maximum_characters must be at least 200"
            )
        if minimum_characters < 1:
            raise ValueError(
                "minimum_characters must be greater than zero"
            )
        if minimum_characters > maximum_characters:
            raise ValueError(
                "minimum_characters must not exceed "
                "maximum_characters"
            )

        self._maximum_evidence = maximum_evidence
        self._maximum_characters = maximum_characters
        self._minimum_characters = minimum_characters

    @property
    def name(self) -> str:
        """Return the extractor name."""

        return "paragraph-live-document"

    def extract(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchEvidenceExtractionResult:
        """Extract selected paragraph chunks from one document."""

        chunks = self._candidate_chunks(document)
        selected = sorted(
            sorted(
                chunks,
                key=lambda chunk: (
                    -chunk.score,
                    chunk.start,
                    chunk.end,
                ),
            )[: self._maximum_evidence],
            key=lambda chunk: (chunk.start, chunk.end),
        )

        evidence = [
            self._evidence(
                document=document,
                chunk=chunk,
                position=position,
            )
            for position, chunk in enumerate(
                selected,
                start=1,
            )
        ]

        return ResearchEvidenceExtractionResult(
            document=document,
            status=ResearchEvidenceExtractionStatus.SUCCEEDED,
            extractor=self.name,
            evidence=evidence,
            duration_ms=0,
            metadata={
                "mode": "paragraph-selection",
                "candidate_chunk_count": str(len(chunks)),
                "selected_chunk_count": str(len(evidence)),
            },
        )

    def _candidate_chunks(
        self,
        document: ResearchSourceDocument,
    ) -> list[_Chunk]:
        content = document.content
        terms = self._reference_terms(document)
        chunks: list[_Chunk] = []

        for match in re.finditer(
            r"\S(?:.*?\S)?(?=\n\s*\n|\Z)",
            content,
            flags=re.DOTALL,
        ):
            start = match.start()
            end = match.end()

            for part_start, part_end in self._split_long_text(
                content=content,
                start=start,
                end=end,
            ):
                part = content[part_start:part_end]
                if len(part) < self._minimum_characters:
                    continue

                chunks.append(
                    _Chunk(
                        start=part_start,
                        end=part_end,
                        text=part,
                        score=self._score(part, terms),
                    )
                )

        if chunks:
            return chunks

        stripped = content.strip()
        if not stripped:
            return []

        start = content.index(stripped)
        end = start + min(
            len(stripped),
            self._maximum_characters,
        )

        return [
            _Chunk(
                start=start,
                end=end,
                text=content[start:end],
                score=0.1,
            )
        ]

    def _split_long_text(
        self,
        *,
        content: str,
        start: int,
        end: int,
    ) -> list[tuple[int, int]]:
        if end - start <= self._maximum_characters:
            return [(start, end)]

        ranges: list[tuple[int, int]] = []
        cursor = start

        while cursor < end:
            target = min(
                cursor + self._maximum_characters,
                end,
            )

            if target < end:
                boundary = content.rfind(
                    " ",
                    cursor + self._minimum_characters,
                    target,
                )
                if boundary > cursor:
                    target = boundary

            if target <= cursor:
                target = min(
                    cursor + self._maximum_characters,
                    end,
                )

            part_start = cursor
            while (
                part_start < target
                and content[part_start].isspace()
            ):
                part_start += 1

            part_end = target
            while (
                part_end > part_start
                and content[part_end - 1].isspace()
            ):
                part_end -= 1

            if part_end > part_start:
                ranges.append((part_start, part_end))

            cursor = target
            while cursor < end and content[cursor].isspace():
                cursor += 1

        return ranges

    @staticmethod
    def _reference_terms(
        document: ResearchSourceDocument,
    ) -> set[str]:
        candidate = document.candidate
        reference = (
            f"{candidate.title} {candidate.snippet}"
        ).casefold()

        return {
            match.group(0)
            for match in _WORD_PATTERN.finditer(reference)
        }

    @staticmethod
    def _score(
        text: str,
        reference_terms: set[str],
    ) -> float:
        normalized = text.casefold()
        words = {
            match.group(0)
            for match in _WORD_PATTERN.finditer(normalized)
        }
        overlap = (
            len(words & reference_terms)
            / max(1, len(reference_terms))
        )
        length_score = min(len(text) / 600, 1.0)
        sentence_score = (
            1.0
            if any(mark in text for mark in (".", "?", "!", "다.", "다"))
            else 0.0
        )
        code_hits = sum(
            marker in normalized
            for marker in _CODE_MARKERS
        )
        code_penalty = min(code_hits * 0.18, 0.54)

        return max(
            0.0,
            min(
                1.0,
                0.45 * length_score
                + 0.40 * overlap
                + 0.15 * sentence_score
                - code_penalty,
            ),
        )

    def _evidence(
        self,
        *,
        document: ResearchSourceDocument,
        chunk: _Chunk,
        position: int,
    ) -> ResearchEvidence:
        candidate = document.candidate

        return ResearchEvidence(
            evidence_id=(
                f"{document.document_id}-evidence-"
                f"{position:03d}"
            ),
            request_id=candidate.request_id,
            task_id=candidate.task_id,
            source_id=candidate.source_id,
            document_id=document.document_id,
            excerpt=chunk.text,
            start_character=chunk.start,
            end_character=chunk.end,
            evidence_type=ResearchEvidenceType.FACT,
            stance=ResearchEvidenceStance.SUPPORTS,
            relevance_score=chunk.score,
            confidence_score=0.8,
            rationale=(
                "Selected from a bounded paragraph chunk "
                "using deterministic relevance and "
                "code-noise heuristics."
            ),
            metadata={
                "extractor": self.name,
                "selection_rank": str(position),
            },
        )
