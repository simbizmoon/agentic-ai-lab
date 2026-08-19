"""OpenAI structured-output adapter for patent claim-element decomposition."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError

from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimElementSelection,
)
from app.schemas.patent_claims import PatentClaim
from app.services.structured_analysis import has_refusal
from app.services.text_generation import TokenUsage, extract_token_usage

PATENT_CLAIM_ELEMENT_DECOMPOSITION_INSTRUCTIONS = """
Decompose the supplied patent claim into ordered technical elements.

Rules:
- Use only the supplied patent claim text.
- Do not add technical facts, components, functions, conditions, relationships,
  terminology, synonyms, or assumptions that are absent from the claim.
- Preserve the technical meaning, conditions, relationships, exceptions,
  modality, and scope expressed by the claim.
- Keep the elements in the same logical order as the source claim.
- Each element should represent one coherent technical limitation or
  relationship that can later be compared with technical evidence.
- Do not split purely on punctuation or conjunctions when doing so would break
  the technical relationship expressed by the claim.
- Prefer wording from the source claim. Do not translate the claim into another
  language.
- Return element_number values starting at 1 and increasing contiguously.
- Do not classify the claim as independent or dependent.
- Do not infer dependency on another claim or add material from another claim.
- Do not make novelty, anticipation, obviousness, validity, infringement,
  freedom-to-operate, essentiality, or other legal conclusions.
- Do not identify any element as essential, inventive, novel, conventional, or
  legally limiting.
- Return only the structured decomposition.
""".strip()


class PatentClaimElementResponsesResource(Protocol):
    """Minimal Responses resource required by this adapter."""

    def parse(self, **kwargs: Any) -> Any: ...


class PatentClaimElementOpenAIClient(Protocol):
    """Minimal injected OpenAI client contract."""

    responses: PatentClaimElementResponsesResource


class PatentClaimElementProviderError(RuntimeError):
    """Raised when the external claim-decomposition request fails."""


@dataclass(frozen=True)
class PatentClaimElementDecompositionResult:
    """One claim decomposition plus provider execution metadata."""

    decomposition: PatentClaimDecomposition
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAIPatentClaimElementDecomposer:
    """Decompose one parsed patent claim with one structured request."""

    def __init__(
        self,
        *,
        client: PatentClaimElementOpenAIClient,
        model: str,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")

        self._client = client
        self._model = model

    @property
    def model(self) -> str:
        """Return the configured provider model."""

        return self._model

    def decompose(
        self,
        claim: PatentClaim,
    ) -> PatentClaimElementDecompositionResult:
        """Return ordered technical elements bound to the supplied source claim."""

        payload = {
            "claim_number": claim.claim_number,
            "provider_position": claim.provider_position,
            "claim_text": claim.text,
        }

        start_time = time.perf_counter()

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=PATENT_CLAIM_ELEMENT_DECOMPOSITION_INSTRUCTIONS,
                input=json.dumps(payload, ensure_ascii=False),
                text_format=PatentClaimElementSelection,
                store=False,
            )
        except ValidationError as exc:
            elapsed_seconds = max(0.0, time.perf_counter() - start_time)
            raise StructuredResponseValidationError(
                "OpenAI patent claim-element response failed schema validation",
                elapsed_seconds=elapsed_seconds,
                attempts=1,
            ) from exc
        except Exception as exc:
            raise PatentClaimElementProviderError(
                "OpenAI patent claim-element request failed"
            ) from exc

        elapsed_seconds = max(0.0, time.perf_counter() - start_time)
        status = getattr(response, "status", None)

        if status == "incomplete":
            raise StructuredResponseIncompleteError(
                "OpenAI patent claim-element response was incomplete"
            )

        if status != "completed":
            raise StructuredResponseStatusError(
                "OpenAI patent claim-element response was not completed"
            )

        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused patent claim-element decomposition"
            )

        parsed = getattr(response, "output_parsed", None)

        if parsed is None:
            raise StructuredResponseParseError(
                "OpenAI patent claim-element response was empty"
            )

        if not isinstance(parsed, PatentClaimElementSelection):
            raise StructuredResponseParseError(
                "OpenAI patent claim-element response has invalid type"
            )

        try:
            decomposition = PatentClaimDecomposition(
                claim_number=claim.claim_number,
                provider_position=claim.provider_position,
                original_claim_text=claim.text,
                elements=parsed.elements,
            )
        except ValidationError as exc:
            raise StructuredResponseValidationError(
                "OpenAI patent claim-element output could not be bound "
                "to the source claim",
                elapsed_seconds=elapsed_seconds,
                attempts=1,
            ) from exc

        return PatentClaimElementDecompositionResult(
            decomposition=decomposition,
            response_id=str(response.id),
            request_id=getattr(response, "_request_id", None),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
