"""Allowlisted official-web acquisition for Stage 9 development evaluation."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
_BLOCK_PATTERN = re.compile(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", re.DOTALL)
_MAXIMUM_DOCUMENT_BYTES = 512_000
_STOP_WORDS = frozenset(
    {"and", "are", "bounded", "relevant", "research", "the", "to", "which"}
)


class Stage9OfficialWebDocument(BaseModel):
    """One exact document returned by a bounded official-domain provider."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    url: str
    title: str
    content: str
    retrieved_at: str
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        for name in ("url", "title", "content", "retrieved_at"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be blank")
        expected = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if self.response_sha256 != expected:
            raise ValueError("response_sha256 must match exact UTF-8 content")
        return self


class Stage9OfficialWebProvider(Protocol):
    """One-call provider boundary; implementation must honor allowed domains."""

    def acquire(
        self,
        *,
        query: str,
        allowed_domains: tuple[str, ...],
        maximum_results: int,
    ) -> tuple[Stage9OfficialWebDocument, ...]: ...


class Stage9OfficialWebAcquisitionError(RuntimeError):
    """Official-web evidence violated its identity or boundedness contract."""


class Stage9OfficialWebAcquisitionAdapter:
    """Acquire only question-authorized official documents in one provider call."""

    def __init__(self, *, provider: Stage9OfficialWebProvider) -> None:
        self._provider = provider

    def acquire(
        self,
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
    ) -> Stage9ChannelAcquisitionResult:
        if channel is not Stage9AcquisitionChannel.OFFICIAL_WEB:
            raise ValueError("official adapter only accepts official_web")
        if request.domain is not Stage9EvaluationDomain.GENERAL_TECHNICAL:
            raise ValueError("official adapter requires general_technical domain")

        allowed_domains = self._domains_from_question(request.question)
        maximum_results = min(request.budget.maximum_documents, 2)
        documents = self._provider.acquire(
            query=self._provider_query(request.question),
            allowed_domains=allowed_domains,
            maximum_results=maximum_results,
        )
        if not isinstance(documents, tuple):
            raise Stage9OfficialWebAcquisitionError(
                "official provider must return a tuple"
            )
        if len(documents) > maximum_results:
            raise Stage9OfficialWebAcquisitionError(
                "official provider exceeded the result boundary"
            )
        for document in documents:
            if not isinstance(document, Stage9OfficialWebDocument):
                raise Stage9OfficialWebAcquisitionError(
                    "official provider returned an invalid document"
                )
            self._validate_domain(document.url, allowed_domains)
            if len(document.content.encode("utf-8")) > _MAXIMUM_DOCUMENT_BYTES:
                raise Stage9OfficialWebAcquisitionError(
                    "official document exceeded the byte boundary"
                )

        if not documents:
            return self._no_evidence(request=request, channel=channel)
        return self._convert(
            request=request,
            channel=channel,
            documents=documents,
        )

    @staticmethod
    def _provider_query(question: str) -> str:
        normalized = question.casefold()
        if re.search(r"\bnist\b", normalized):
            domain_lock = "site:nist.gov"
            if re.search(r"\bgai\b", normalized) or (
                "generative artificial intelligence" in normalized
            ):
                return (
                    f"{question} NIST Generative Artificial Intelligence "
                    f"risk management profile suggested actions {domain_lock}"
                )
            return f"{question} {domain_lock}"
        return question

    @staticmethod
    def _domains_from_question(question: str) -> tuple[str, ...]:
        normalized = question.casefold()
        domains: list[str] = []
        if re.search(r"\bnist\b", normalized):
            domains.append("nist.gov")
        if re.search(r"\bopenai\b", normalized):
            domains.append("openai.com")
        if not domains:
            raise Stage9OfficialWebAcquisitionError(
                "question does not name a supported official authority"
            )
        return tuple(domains)

    @staticmethod
    def _validate_domain(url: str, allowed_domains: tuple[str, ...]) -> None:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not any(
            host == domain or host.endswith(f".{domain}") for domain in allowed_domains
        ):
            raise Stage9OfficialWebAcquisitionError(
                "official document URL was outside the allowlist"
            )

    @staticmethod
    def _query_tokens(value: str) -> set[str]:
        return {
            token
            for token in _TOKEN_PATTERN.findall(value.casefold())
            if len(token) >= 3 and token not in _STOP_WORDS
        }

    def _convert(
        self,
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
        documents: tuple[Stage9OfficialWebDocument, ...],
    ) -> Stage9ChannelAcquisitionResult:
        query_tokens = self._query_tokens(request.question)
        research_documents: list[ResearchSourceDocument] = []
        evidence: list[ResearchEvidence] = []
        maximum_evidence = min(request.budget.maximum_evidence_items, 4)

        for rank, item in enumerate(documents, start=1):
            if len(evidence) >= maximum_evidence:
                break
            blocks = tuple(
                match.group(0).strip()
                for match in _BLOCK_PATTERN.finditer(item.content)
            )
            scored = [
                (
                    len(query_tokens.intersection(self._query_tokens(block))),
                    position,
                    block,
                )
                for position, block in enumerate(blocks)
            ]
            scored = [value for value in scored if value[0] > 0]
            scored.sort(key=lambda value: (-value[0], value[1]))
            selected = scored[: maximum_evidence - len(evidence)]
            if not selected:
                continue

            identity = hashlib.sha256(item.url.encode("utf-8")).hexdigest()[:16]
            source_id = f"official-web-{identity}"
            document_id = f"official-web-document-{identity}"
            task_id = f"{request.request_id}-official-web"
            content = "\n\n".join(value[2] for value in selected)
            candidate = ResearchSourceCandidate(
                source_id=source_id,
                request_id=request.request_id,
                task_id=task_id,
                query_id=f"{request.request_id}-official-domain-query",
                title=item.title,
                url=item.url,
                source_type=ResearchSourceType.GOVERNMENT,
                snippet=selected[0][2][:240],
                publisher=urlsplit(item.url).hostname,
                rank=rank,
                status=ResearchSourceCandidateStatus.READ,
                metadata={
                    "retrieved_at": item.retrieved_at,
                    "response_sha256": item.response_sha256,
                    "golden_source_supplied": "false",
                },
            )
            document = ResearchSourceDocument(
                document_id=document_id,
                candidate=candidate,
                status=ResearchSourceDocumentStatus.READ,
                content_type=ResearchSourceContentType.TEXT,
                content=content,
                language="en",
                word_count=len(content.split()),
                character_count=len(content),
                reader="stage9-bounded-official-web-adapter-v1",
                metadata={
                    "original_response_sha256": item.response_sha256,
                    "selected_blocks": str(len(selected)),
                },
            )
            research_documents.append(document)
            cursor = 0
            for _, original_position, block in selected:
                start = content.find(block, cursor)
                end = start + len(block)
                cursor = end
                evidence.append(
                    ResearchEvidence(
                        evidence_id=(
                            f"{document_id}-block-{original_position + 1:03d}"
                        ),
                        request_id=request.request_id,
                        task_id=task_id,
                        source_id=source_id,
                        document_id=document_id,
                        excerpt=block,
                        start_character=start,
                        end_character=end,
                        evidence_type=ResearchEvidenceType.OTHER,
                        stance=ResearchEvidenceStance.NEUTRAL,
                        relevance_score=1.0,
                        confidence_score=1.0,
                        rationale=(
                            "Question-token overlap in an allowlisted official document."
                        ),
                        metadata={
                            "original_block_position": str(original_position + 1),
                            "response_sha256": item.response_sha256,
                        },
                    )
                )

        if not evidence:
            return self._no_evidence(request=request, channel=channel)
        evidence_set = ResearchEvidenceSet(
            request_id=request.request_id,
            document_set=ResearchSourceDocumentSet(
                request_id=request.request_id,
                documents=research_documents,
            ),
            evidence=evidence,
        )
        return Stage9ChannelAcquisitionResult(
            request_id=request.request_id,
            channel=channel,
            status=Stage9AcquisitionStatus.EVIDENCE_AVAILABLE,
            evidence_set=evidence_set,
            provider_requests=1,
            external_requests=1,
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
            provider_requests=1,
            external_requests=1,
        )
