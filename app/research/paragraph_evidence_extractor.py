"""Deterministic query-aware paragraph evidence extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.research.research_evidence_extractor import ResearchEvidenceExtractor
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionResult,
    ResearchEvidenceExtractionStatus,
)
from app.schemas.research_source_document import ResearchSourceDocument

_WORD_PATTERN = re.compile(r"[A-Za-z0-9가-힣]{3,}")
_GENERIC_QUERY_TERMS = {
    "openai", "official", "documentation", "overview", "explain",
    "using", "concise", "authoritative", "evidence", "api",
}
_CODE_MARKERS = (
    "authorization:", "api_key", "import ", "curl ", "requests.post",
    "client.responses", "functionname", "functionparameters",
    "createfunctiontool", "openai.newclient", "responses.toolparam",
    "#pragma ", "using system.",
)
_INDEX_MARKERS = (
    "llms.txt", "documentation index",
    "markdown versions of documentation pages", "table of contents",
)
_EXECUTION_MARKERS = (
    "execute the code with", "run the code with", "save the code as",
    "in a few moments, you should see",
)
_OPINION_MARKERS = (
    "i think", "i feel", "my feelings", "i haven't tried",
    "i went ahead", "does it seem", "not really",
)


@dataclass(frozen=True)
class _Chunk:
    start: int
    end: int
    text: str
    score: float


class ParagraphEvidenceExtractor(ResearchEvidenceExtractor):
    """Select concise evidence tied to the originating search query."""

    def __init__(
        self,
        *,
        maximum_evidence: int = 3,
        maximum_characters: int = 1_200,
        minimum_characters: int = 80,
        minimum_score: float = 0.22,
    ) -> None:
        if maximum_evidence < 1:
            raise ValueError("maximum_evidence must be greater than zero")
        if maximum_characters < 200:
            raise ValueError("maximum_characters must be at least 200")
        if minimum_characters < 1:
            raise ValueError("minimum_characters must be greater than zero")
        if minimum_characters > maximum_characters:
            raise ValueError(
                "minimum_characters must not exceed maximum_characters"
            )
        if not 0 <= minimum_score <= 1:
            raise ValueError("minimum_score must be between zero and one")

        self._maximum_evidence = maximum_evidence
        self._maximum_characters = maximum_characters
        self._minimum_characters = minimum_characters
        self._minimum_score = minimum_score

    @property
    def name(self) -> str:
        return "query-aware-paragraph-live-document"

    def extract(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchEvidenceExtractionResult:
        chunks = [
            chunk
            for chunk in self._candidate_chunks(document)
            if chunk.score >= self._minimum_score
        ]
        selected = sorted(
            sorted(
                chunks,
                key=lambda chunk: (-chunk.score, chunk.start, chunk.end),
            )[: self._maximum_evidence],
            key=lambda chunk: (chunk.start, chunk.end),
        )
        evidence = [
            self._evidence(document=document, chunk=chunk, position=position)
            for position, chunk in enumerate(selected, start=1)
        ]
        return ResearchEvidenceExtractionResult(
            document=document,
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
                if evidence
                else ResearchEvidenceExtractionStatus.NO_EVIDENCE
            ),
            extractor=self.name,
            evidence=evidence,
            duration_ms=0,
            metadata={
                "mode": "query-aware-paragraph-selection",
                "candidate_chunk_count": str(len(chunks)),
                "selected_chunk_count": str(len(evidence)),
            },
        )

    def _candidate_chunks(
        self,
        document: ResearchSourceDocument,
    ) -> list[_Chunk]:
        content = document.content
        query_terms, reference_terms = self._reference_terms(document)
        chunks: list[_Chunk] = []

        for match in re.finditer(
            r"\S(?:.*?\S)?(?=\n\s*\n|\Z)",
            content,
            flags=re.DOTALL,
        ):
            for start, end in self._split_long_text(
                content=content,
                start=match.start(),
                end=match.end(),
            ):
                text = content[start:end]
                if len(text) < self._minimum_characters:
                    continue
                chunks.append(
                    _Chunk(
                        start=start,
                        end=end,
                        text=text,
                        score=self._score(
                            text,
                            query_terms=query_terms,
                            reference_terms=reference_terms,
                        ),
                    )
                )
        return chunks

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
            target = min(cursor + self._maximum_characters, end)
            if target < end:
                boundary = content.rfind(
                    " ",
                    cursor + self._minimum_characters,
                    target,
                )
                if boundary > cursor:
                    target = boundary
            if target <= cursor:
                target = min(cursor + self._maximum_characters, end)

            part_start = cursor
            while part_start < target and content[part_start].isspace():
                part_start += 1
            part_end = target
            while part_end > part_start and content[part_end - 1].isspace():
                part_end -= 1
            if part_end > part_start:
                ranges.append((part_start, part_end))

            cursor = target
            while cursor < end and content[cursor].isspace():
                cursor += 1
        return ranges

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            match.group(0)
            for match in _WORD_PATTERN.finditer(text.casefold())
        }

    @classmethod
    def _reference_terms(
        cls,
        document: ResearchSourceDocument,
    ) -> tuple[set[str], set[str]]:
        candidate = document.candidate
        query_text = candidate.metadata.get("search_query_text", "")
        query_terms = {
            term
            for term in cls._tokens(query_text)
            if term not in _GENERIC_QUERY_TERMS
        }
        reference_terms = cls._tokens(
            f"{candidate.title} {candidate.snippet}"
        )
        return query_terms, reference_terms

    @classmethod
    def _score(
        cls,
        text: str,
        *,
        query_terms: set[str],
        reference_terms: set[str],
    ) -> float:
        normalized = text.casefold()
        if cls._is_hard_noise(text, normalized=normalized):
            return 0.0

        words = cls._tokens(normalized)
        query_overlap = (
            len(words & query_terms) / max(1, len(query_terms))
            if query_terms
            else 0.0
        )
        reference_overlap = (
            len(words & reference_terms) / max(1, len(reference_terms))
        )
        length_score = min(len(text) / 600, 1.0)
        sentence_score = (
            1.0
            if any(mark in text for mark in (".", "?", "!", "다.", "다"))
            else 0.0
        )

        code_hits = sum(marker in normalized for marker in _CODE_MARKERS)
        index_hits = sum(marker in normalized for marker in _INDEX_MARKERS)
        execution_hits = sum(
            marker in normalized for marker in _EXECUTION_MARKERS
        )
        opinion_hits = sum(
            marker in normalized for marker in _OPINION_MARKERS
        )
        link_ratio = cls._link_list_ratio(text)
        code_structure = cls._code_structure_score(text)
        missing_query_penalty = (
            0.45 if query_terms and query_overlap == 0 else 0.0
        )

        penalty = min(
            1.0,
            0.24 * code_hits
            + 0.34 * index_hits
            + 0.45 * execution_hits
            + 0.22 * opinion_hits
            + 0.62 * link_ratio
            + 0.82 * code_structure
            + missing_query_penalty,
        )

        return max(
            0.0,
            min(
                1.0,
                0.50 * query_overlap
                + 0.20 * reference_overlap
                + 0.18 * length_score
                + 0.12 * sentence_score
                - penalty,
            ),
        )

    @classmethod
    def _is_hard_noise(
        cls,
        text: str,
        *,
        normalized: str,
    ) -> bool:
        stripped = normalized.lstrip()

        if (
            stripped.startswith(("```", "~~~"))
            or "```" in normalized
            or "~~~" in normalized
        ):
            return True

        if any(
            marker in normalized
            for marker in _EXECUTION_MARKERS
        ):
            return True

        if cls._is_navigation_link_fragment(text):
            return True

        if cls._is_simple_code_call(text):
            return True

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        markdown_link_count = sum(
            line.count("](")
            for line in lines
        )
        list_line_count = sum(
            line.startswith(("- ", "* "))
            or bool(re.match(r"^\d+[.)]\s", line))
            for line in lines
        )
        heading_line_count = sum(
            line.startswith("#")
            for line in lines
        )

        if (
            markdown_link_count >= 2
            and list_line_count >= 2
        ):
            return True

        if (
            heading_line_count >= 1
            and markdown_link_count >= 1
            and list_line_count >= 1
        ):
            return True

        if (
            len(lines) == 1
            and (
                lines[0].startswith(("- ", "* "))
                or bool(re.match(r"^\d+[.)]\s", lines[0]))
            )
        ):
            return True

        return cls._code_structure_score(text) >= 0.22

    @staticmethod
    def _is_navigation_link_fragment(text: str) -> bool:
        stripped = text.strip()
        lines = [
            line.strip()
            for line in stripped.splitlines()
            if line.strip()
        ]

        if len(lines) > 2:
            return False

        return (
            "](" in stripped
            and (
                stripped.count("](") >= 1
                or stripped.startswith(("[", "- [", "* ["))
            )
        )

    @staticmethod
    def _is_simple_code_call(text: str) -> bool:
        stripped = text.strip()

        if re.search(
            r"(?m)^\s*(?:var|let|const)\s+"
            r"[A-Za-z_][A-Za-z0-9_]*\s*=\s*"
            r"[A-Za-z_][A-Za-z0-9_.]*\s*\(",
            stripped,
        ):
            return True

        if re.search(
            r"(?m)^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*"
            r"[A-Za-z_][A-Za-z0-9_.]*\s*\(",
            stripped,
        ):
            return True

        if re.search(
            r"(?m)^\s*(?:await\s+foreach|foreach)\s*\(",
            stripped,
        ):
            return True

        return (
            stripped.endswith((");", ")"))
            and stripped.count("(") >= 1
            and stripped.count(")") >= 1
            and len(stripped.splitlines()) <= 6
            and not stripped.endswith((".", "?", "!"))
        )

    @staticmethod
    def _link_list_ratio(text: str) -> float:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return 0.0
        list_like = sum(
            line.startswith(("-", "*", "["))
            or bool(re.match(r"^\d+[.)]\s", line))
            for line in lines
        )
        markdown_links = sum(line.count("](") for line in lines)
        return min(
            1.0,
            (list_like + min(markdown_links, len(lines)))
            / max(1, 2 * len(lines)),
        )

    @staticmethod
    def _code_structure_score(text: str) -> float:
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if not lines:
            return 0.0

        punctuation_hits = sum(
            line.count(symbol)
            for line in lines
            for symbol in ("{", "}", "[", "]", "=>")
        )
        assignment_lines = sum(
            bool(
                re.search(
                    r"(^|\s)[A-Za-z_][A-Za-z0-9_]*\s*[:=]",
                    line,
                )
            )
            for line in lines
        )
        quoted_key_lines = sum(
            bool(re.search(r'["\'][A-Za-z_][^"\']*["\']\s*:', line))
            for line in lines
        )
        call_lines = sum(
            bool(
                re.search(
                    r"\b[A-Za-z_][A-Za-z0-9_.]*\([^)]*\)",
                    line,
                )
            )
            for line in lines
        )
        natural_sentences = sum(
            line.endswith((".", "?", "!"))
            and len(line.split()) >= 6
            for line in lines
        )
        structural_hits = (
            punctuation_hits
            + 2 * assignment_lines
            + 2 * quoted_key_lines
            + call_lines
        )
        raw_score = structural_hits / max(6, 3 * len(lines))
        sentence_relief = min(
            0.35,
            natural_sentences / max(1, len(lines)),
        )
        return max(0.0, min(1.0, raw_score - sentence_relief))

    def _evidence(
        self,
        *,
        document: ResearchSourceDocument,
        chunk: _Chunk,
        position: int,
    ) -> ResearchEvidence:
        candidate = document.candidate
        return ResearchEvidence(
            evidence_id=f"{document.document_id}-evidence-{position:03d}",
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
                "Selected using the originating search query, bounded "
                "paragraphs, and structural noise filtering."
            ),
            metadata={
                "extractor": self.name,
                "selection_rank": str(position),
            },
        )
