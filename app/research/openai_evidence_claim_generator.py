"""OpenAI structured-output generator for evidence-backed claim proposals."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.schemas.generated_claim_proposal import (
    GeneratedClaimProposal,
    GeneratedClaimProposalBatch,
)
from app.schemas.research_evidence import ResearchEvidence
from app.services.structured_analysis import has_refusal
from app.services.text_generation import (
    TokenUsage,
    extract_token_usage,
)

GENERATIVE_CLAIM_INSTRUCTIONS = """
Rewrite the supplied evidence as one concise factual research claim.

Use only the supplied evidence.
Do not use outside knowledge.
Do not add facts that are absent from the evidence.
Preserve quantities, conditions, exceptions, scope, uncertainty, and modality.
Do not strengthen words such as may, can, some, several, or sometimes into
always, all, only, must, or never.
Do not turn association or correlation into causation.
Do not invent identifiers, citations, sources, document references, or metadata.

Return:
- text: one factual claim that faithfully restates the evidence meaning.
- rationale: a brief explanation of why the claim stays within the evidence.

The claim may paraphrase the evidence and should not merely copy wording when
a faithful concise reformulation is possible.
""".strip()

GENERATIVE_CLAIM_BATCH_INSTRUCTIONS = (
    GENERATIVE_CLAIM_INSTRUCTIONS
    + """

Batch generation rules:
- Process every supplied evidence item independently.
- Produce exactly one claim proposal for every supplied item_id.
- Copy each supplied item_id exactly; do not invent, omit, or duplicate IDs.
- Do not combine evidence items into a synthesized cross-item claim.
- Do not let one evidence item add facts to another item's claim.
""".rstrip()
)


class OpenAIEvidenceClaimGeneratorError(RuntimeError):
    """Base error for OpenAI evidence-backed claim generation."""


class StructuredClaimGenerationError(
    OpenAIEvidenceClaimGeneratorError
):
    """Raised for unusable structured claim-generation output."""


class ClaimGenerationProviderError(
    OpenAIEvidenceClaimGeneratorError
):
    """Raised when the provider request itself fails."""


@dataclass(frozen=True)
class GeneratedClaimProposalResult:
    """One generated proposal plus provider execution metadata."""

    proposal: GeneratedClaimProposal
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


@dataclass(frozen=True)
class GeneratedClaimProposalBatchResult:
    """Batched proposals with shared provider execution metadata."""

    proposals: dict[str, GeneratedClaimProposal]
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAIEvidenceClaimGenerator:
    """Generate meaning-only claim proposals from evidence."""

    def __init__(
        self,
        *,
        client: OpenAI,
        model: str,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")

        self._client = client
        self._model = model

    @property
    def model(self) -> str:
        """Return the configured OpenAI model."""

        return self._model

    def generate_batch(
        self,
        evidence_items: list[tuple[str, ResearchEvidence]],
    ) -> GeneratedClaimProposalBatchResult:
        """Generate independent proposals in one structured request."""

        if not evidence_items:
            raise ValueError("evidence_items must not be empty")

        cleaned_items: list[dict[str, str]] = []
        normalized_ids: list[str] = []

        for item_id, evidence in evidence_items:
            cleaned_id = item_id.strip()
            if not cleaned_id:
                raise ValueError("batch item_id must not be blank")

            normalized_ids.append(cleaned_id.casefold())
            cleaned_items.append(
                {
                    "item_id": cleaned_id,
                    "evidence_type": evidence.evidence_type.value,
                    "excerpt": evidence.excerpt,
                }
            )

        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("batch item IDs must be unique")

        start_time = time.perf_counter()

        try:
            response: Any = self._client.responses.parse(
                model=self._model,
                instructions=GENERATIVE_CLAIM_BATCH_INSTRUCTIONS,
                input=json.dumps(
                    {"evidence_items": cleaned_items},
                    ensure_ascii=False,
                ),
                text_format=GeneratedClaimProposalBatch,
                store=False,
            )
        except ValidationError as exc:
            raise StructuredClaimGenerationError(
                "OpenAI batched claim proposal failed schema validation"
            ) from exc
        except Exception as exc:
            raise ClaimGenerationProviderError(
                "OpenAI batched claim proposal request failed"
            ) from exc

        elapsed_seconds = max(
            0.0,
            time.perf_counter() - start_time,
        )

        status = getattr(response, "status", None)

        if status == "incomplete":
            raise StructuredClaimGenerationError(
                "OpenAI batched claim proposal response was incomplete"
            )

        if status != "completed":
            raise StructuredClaimGenerationError(
                "OpenAI batched claim proposal response was not completed"
            )

        if has_refusal(response):
            raise StructuredClaimGenerationError(
                "OpenAI refused the batched claim proposal request"
            )

        parsed = getattr(response, "output_parsed", None)

        if parsed is None:
            raise StructuredClaimGenerationError(
                "OpenAI batched claim proposal response was empty"
            )

        if not isinstance(parsed, GeneratedClaimProposalBatch):
            raise StructuredClaimGenerationError(
                "OpenAI batched claim proposal response has invalid type"
            )

        expected_ids = [
            item["item_id"]
            for item in cleaned_items
        ]
        expected_by_folded = {
            item_id.casefold(): item_id
            for item_id in expected_ids
        }
        returned_ids = [
            item.item_id
            for item in parsed.items
        ]
        returned_folded = [
            item_id.casefold()
            for item_id in returned_ids
        ]

        if (
            len(returned_ids) != len(expected_ids)
            or len(set(returned_folded)) != len(returned_folded)
            or set(returned_folded) != set(expected_by_folded)
        ):
            raise StructuredClaimGenerationError(
                "OpenAI batched claim proposal item IDs did not match request"
            )

        proposals = {
            expected_by_folded[
                item.item_id.casefold()
            ]: item.proposal
            for item in parsed.items
        }

        return GeneratedClaimProposalBatchResult(
            proposals=proposals,
            response_id=str(response.id),
            request_id=getattr(
                response,
                "_request_id",
                None,
            ),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )

    def generate(
        self,
        evidence: ResearchEvidence,
    ) -> GeneratedClaimProposalResult:
        """Generate one structured claim proposal."""

        payload = {
            "evidence_type": evidence.evidence_type.value,
            "excerpt": evidence.excerpt,
        }

        start_time = time.perf_counter()

        try:
            response: Any = self._client.responses.parse(
                model=self._model,
                instructions=GENERATIVE_CLAIM_INSTRUCTIONS,
                input=json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
                text_format=GeneratedClaimProposal,
                store=False,
            )
        except ValidationError as exc:
            raise StructuredClaimGenerationError(
                "OpenAI claim proposal failed schema validation"
            ) from exc
        except Exception as exc:
            raise ClaimGenerationProviderError(
                "OpenAI claim proposal request failed"
            ) from exc

        elapsed_seconds = max(
            0.0,
            time.perf_counter() - start_time,
        )

        status = getattr(response, "status", None)

        if status == "incomplete":
            raise StructuredClaimGenerationError(
                "OpenAI claim proposal response was incomplete"
            )

        if status != "completed":
            raise StructuredClaimGenerationError(
                "OpenAI claim proposal response was not completed"
            )

        if has_refusal(response):
            raise StructuredClaimGenerationError(
                "OpenAI refused the claim proposal request"
            )

        proposal = getattr(
            response,
            "output_parsed",
            None,
        )

        if proposal is None:
            raise StructuredClaimGenerationError(
                "OpenAI claim proposal response was empty"
            )

        if not isinstance(
            proposal,
            GeneratedClaimProposal,
        ):
            raise StructuredClaimGenerationError(
                "OpenAI claim proposal response has invalid type"
            )

        return GeneratedClaimProposalResult(
            proposal=proposal,
            response_id=str(response.id),
            request_id=getattr(
                response,
                "_request_id",
                None,
            ),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
