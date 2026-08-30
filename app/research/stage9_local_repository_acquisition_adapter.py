"""Bounded local-repository evidence acquisition for Stage 9 development cases."""

from __future__ import annotations

import re
from pathlib import Path

from app.research.stage9_development_acquisition_router import (
    Stage9ChannelAcquisitionResult,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateStatus,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSection,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionChannel,
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequest,
)
from app.schemas.stage9_evaluation_manifest import Stage9EvaluationDomain

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.ASCII)
_HEADING_PATTERN = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_STOP_WORDS = frozenset({"and", "between", "differ", "do", "how", "original", "the"})
_MAXIMUM_FILE_BYTES = 512_000


class Stage9LocalRepositoryAcquisitionError(RuntimeError):
    """Local evidence could not be read within the locked safety boundary."""


class Stage9LocalRepositoryAcquisitionAdapter:
    """Select question-matching Markdown sections from explicitly allowed files."""

    def __init__(
        self,
        *,
        repository_root: Path,
        maximum_file_bytes: int = _MAXIMUM_FILE_BYTES,
    ) -> None:
        root = repository_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("repository_root must be a directory")
        if maximum_file_bytes < 1 or maximum_file_bytes > _MAXIMUM_FILE_BYTES:
            raise ValueError("maximum_file_bytes is outside the safe boundary")
        self._root = root
        self._maximum_file_bytes = maximum_file_bytes

    def acquire(
        self,
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
    ) -> Stage9ChannelAcquisitionResult:
        if channel is not Stage9AcquisitionChannel.LOCAL_REPOSITORY:
            raise ValueError("local adapter only accepts local_repository")
        if request.domain is not Stage9EvaluationDomain.CROSS_SOURCE:
            raise ValueError("local adapter requires the cross_source domain")

        filenames = self._filenames_from_question(request.question)
        query_tokens = self._query_tokens(request.question)
        selected: list[tuple[str, str, int]] = []
        for filename in filenames:
            text = self._read_allowed_file(filename)
            for section in self._sections(text):
                overlap = len(query_tokens.intersection(self._query_tokens(section)))
                if overlap:
                    selected.append((filename, section, overlap))

        selected.sort(key=lambda item: (-item[2], item[0], item[1]))
        maximum = min(request.budget.maximum_evidence_items, 4)
        selected = selected[:maximum]
        if not selected:
            return self._no_evidence(request=request, channel=channel)
        return self._available(
            request=request,
            channel=channel,
            selected=selected,
        )

    @staticmethod
    def _filenames_from_question(question: str) -> tuple[str, ...]:
        normalized = question.casefold()
        filenames: list[str] = []
        if "roadmap" in normalized:
            filenames.append("ROADMAP.md")
        if "decision" in normalized or "decisions" in normalized:
            filenames.append("DECISIONS.md")
        if not filenames:
            raise Stage9LocalRepositoryAcquisitionError(
                "question does not explicitly name an allowed repository document"
            )
        return tuple(filenames)

    @staticmethod
    def _query_tokens(value: str) -> set[str]:
        return {
            token
            for token in _TOKEN_PATTERN.findall(value.casefold())
            if len(token) >= 3 and token not in _STOP_WORDS
        }

    def _read_allowed_file(self, filename: str) -> str:
        path = self._root / filename
        if path.is_symlink():
            raise Stage9LocalRepositoryAcquisitionError(
                "repository evidence file must not be a symbolic link"
            )
        resolved = path.resolve(strict=True)
        if resolved.parent != self._root or not resolved.is_file():
            raise Stage9LocalRepositoryAcquisitionError(
                "repository evidence path escaped the allowed root"
            )
        size = resolved.stat().st_size
        if size < 1 or size > self._maximum_file_bytes:
            raise Stage9LocalRepositoryAcquisitionError(
                "repository evidence file exceeded the byte boundary"
            )
        try:
            return resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise Stage9LocalRepositoryAcquisitionError(
                "repository evidence file was not strict UTF-8"
            ) from error

    @staticmethod
    def _sections(text: str) -> tuple[str, ...]:
        starts = [match.start() for match in _HEADING_PATTERN.finditer(text)]
        return tuple(
            text[start:end].strip()
            for start, end in zip(starts, (*starts[1:], len(text)), strict=True)
            if text[start:end].strip()
        )

    def _available(
        self,
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
        selected: list[tuple[str, str, int]],
    ) -> Stage9ChannelAcquisitionResult:
        task_id = f"{request.request_id}-local-repository"
        content_parts: list[str] = []
        ranges: list[tuple[int, int, str, int]] = []
        cursor = 0
        for filename, excerpt, overlap in selected:
            if content_parts:
                cursor += 2
            start = cursor
            content_parts.append(excerpt)
            cursor += len(excerpt)
            ranges.append((start, cursor, filename, overlap))
        content = "\n\n".join(content_parts)
        source_id = f"local-repository-{request.case_id}"
        document_id = f"local-repository-{request.case_id}-document"
        candidate = ResearchSourceCandidate(
            source_id=source_id,
            request_id=request.request_id,
            task_id=task_id,
            query_id=f"{request.request_id}-explicit-local-document",
            title="AIRA repository evidence selected from the case question",
            url="https://local.repository.invalid/stage9-evidence",
            source_type=ResearchSourceType.OFFICIAL_DOCUMENTATION,
            snippet=selected[0][1][:240],
            publisher="AIRA local repository",
            rank=1,
            status=ResearchSourceCandidateStatus.READ,
            metadata={
                "repository_root": str(self._root),
                "selection_basis": "question_token_overlap",
                "golden_evidence_supplied": "false",
            },
        )
        sections = [
            ResearchSourceDocumentSection(
                section_id=f"{document_id}-section-{index:02d}",
                heading=excerpt.splitlines()[0],
                content=excerpt,
                order=index,
                start_character=start,
                end_character=end,
                metadata={
                    "local_filename": filename,
                    "matched_query_tokens": str(overlap),
                },
            )
            for index, ((_, excerpt, _), (start, end, filename, overlap)) in enumerate(
                zip(selected, ranges, strict=True), start=1
            )
        ]
        document = ResearchSourceDocument(
            document_id=document_id,
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=ResearchSourceContentType.MARKDOWN,
            content=content,
            language="ko-en",
            sections=sections,
            word_count=len(content.split()),
            character_count=len(content),
            reader="stage9-bounded-local-repository-adapter-v1",
            metadata={"selected_sections": str(len(sections))},
        )
        evidence = [
            ResearchEvidence(
                evidence_id=f"{section.section_id}-evidence",
                request_id=request.request_id,
                task_id=task_id,
                source_id=source_id,
                document_id=document_id,
                section_id=section.section_id,
                excerpt=section.content,
                start_character=section.start_character,
                end_character=section.end_character,
                evidence_type=ResearchEvidenceType.OTHER,
                stance=ResearchEvidenceStance.NEUTRAL,
                relevance_score=1.0,
                confidence_score=1.0,
                rationale="Deterministic token overlap with the evaluation question.",
                metadata=dict(section.metadata),
            )
            for section in sections
        ]
        return Stage9ChannelAcquisitionResult(
            request_id=request.request_id,
            channel=channel,
            status=Stage9AcquisitionStatus.EVIDENCE_AVAILABLE,
            evidence_set=ResearchEvidenceSet(
                request_id=request.request_id,
                document_set=ResearchSourceDocumentSet(
                    request_id=request.request_id,
                    documents=[document],
                ),
                evidence=evidence,
            ),
            provider_requests=0,
            external_requests=0,
        )

    @staticmethod
    def _no_evidence(
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
    ) -> Stage9ChannelAcquisitionResult:
        return Stage9ChannelAcquisitionResult(
            request_id=request.request_id,
            channel=channel,
            status=Stage9AcquisitionStatus.NO_EVIDENCE,
            evidence_set=ResearchEvidenceSet(
                request_id=request.request_id,
                document_set=ResearchSourceDocumentSet(
                    request_id=request.request_id,
                    documents=[],
                ),
                evidence=[],
            ),
            provider_requests=0,
            external_requests=0,
        )
