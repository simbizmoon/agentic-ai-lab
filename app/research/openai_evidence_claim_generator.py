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


class OpenAIEvidenceClaimGeneratorError(RuntimeError):
    """Raised when a structured claim proposal cannot be generated."""


@dataclass(frozen=True)
class GeneratedClaimProposalResult:
    """One generated proposal plus provider execution metadata."""

    proposal: GeneratedClaimProposal
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAIEvidenceClaimGenerator:
    """Generate one meaning-only claim proposal from one evidence item."""

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
            raise OpenAIEvidenceClaimGeneratorError(
                "OpenAI claim proposal failed schema validation"
            ) from exc
        except Exception as exc:
            raise OpenAIEvidenceClaimGeneratorError(
                "OpenAI claim proposal request failed"
            ) from exc

        elapsed_seconds = max(
            0.0,
            time.perf_counter() - start_time,
        )

        status = getattr(response, "status", None)

        if status == "incomplete":
            raise OpenAIEvidenceClaimGeneratorError(
                "OpenAI claim proposal response was incomplete"
            )

        if status != "completed":
            raise OpenAIEvidenceClaimGeneratorError(
                "OpenAI claim proposal response was not completed"
            )

        if has_refusal(response):
            raise OpenAIEvidenceClaimGeneratorError(
                "OpenAI refused the claim proposal request"
            )

        proposal = getattr(
            response,
            "output_parsed",
            None,
        )

        if proposal is None:
            raise OpenAIEvidenceClaimGeneratorError(
                "OpenAI claim proposal response was empty"
            )

        if not isinstance(
            proposal,
            GeneratedClaimProposal,
        ):
            raise OpenAIEvidenceClaimGeneratorError(
                "OpenAI claim proposal response has invalid type"
            )

        return GeneratedClaimProposalResult(
            proposal=proposal,
            response_id=response.id,
            request_id=getattr(
                response,
                "_request_id",
                None,
            ),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
