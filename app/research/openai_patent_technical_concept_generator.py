"""OpenAI structured-output adapter for grounded patent concept selection."""

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
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_technical_concept import (
    PatentTechnicalConceptPlan,
    PatentTechnicalConceptSelection,
)
from app.services.structured_analysis import has_refusal
from app.services.text_generation import TokenUsage, extract_token_usage

PATENT_TECHNICAL_CONCEPT_INSTRUCTIONS = """
Select grounded technical search concepts from the supplied patent research
question and objective.

Rules:
- Return exactly one PRIMARY concept and at most one ALTERNATE concept.
- Every returned term must be copied from wording that already appears in the
  supplied question or objective. Do not invent terminology.
- Select concise technical nouns or technical noun phrases that identify the
  technology, mechanism, component, signal, state, process, or relationship
  being investigated.
- Do not generate synonyms that are absent from the input.
- Do not translate terms into another language.
- Do not generate EPO CQL or any other search-query syntax.
- Do not generate IPC/CPC classification codes.
- Do not invent patent numbers, publication identifiers, applicants, dates, or
  metadata.
- Do not make novelty, anticipation, obviousness, validity, infringement,
  freedom-to-operate, or other legal conclusions.
- Use ALTERNATE only when the input itself contains distinct additional
  technical terminology that would support a separate search concept.
- Generic words such as patent, prior art, relevant, search, identify, explain,
  or research are not technical concepts by themselves.
""".strip()


class PatentTechnicalConceptResponsesResource(Protocol):
    """Minimal Responses resource required by this adapter."""

    def parse(self, **kwargs: Any) -> Any: ...


class PatentTechnicalConceptOpenAIClient(Protocol):
    """Minimal injected OpenAI client contract."""

    responses: PatentTechnicalConceptResponsesResource


class PatentTechnicalConceptProviderError(RuntimeError):
    """Raised when the external concept-generation request fails."""


@dataclass(frozen=True)
class PatentTechnicalConceptGenerationResult:
    """One grounded concept plan with provider execution metadata."""

    plan: PatentTechnicalConceptPlan
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAIPatentTechnicalConceptGenerator:
    """Select grounded patent technical concepts with one structured request."""

    def __init__(
        self,
        *,
        client: PatentTechnicalConceptOpenAIClient,
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

    def generate(
        self,
        request: PatentResearchRequest,
    ) -> PatentTechnicalConceptGenerationResult:
        """Generate one request-bound grounded technical concept plan."""

        payload = {
            "question": request.question,
            "objective": request.objective,
        }

        start_time = time.perf_counter()

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=PATENT_TECHNICAL_CONCEPT_INSTRUCTIONS,
                input=json.dumps(payload, ensure_ascii=False),
                text_format=PatentTechnicalConceptSelection,
                store=False,
            )
        except ValidationError as exc:
            elapsed_seconds = max(0.0, time.perf_counter() - start_time)
            raise StructuredResponseValidationError(
                "OpenAI patent technical concept response failed schema validation",
                elapsed_seconds=elapsed_seconds,
                attempts=1,
            ) from exc
        except Exception as exc:
            raise PatentTechnicalConceptProviderError(
                "OpenAI patent technical concept request failed"
            ) from exc

        elapsed_seconds = max(0.0, time.perf_counter() - start_time)
        status = getattr(response, "status", None)

        if status == "incomplete":
            raise StructuredResponseIncompleteError(
                "OpenAI patent technical concept response was incomplete"
            )

        if status != "completed":
            raise StructuredResponseStatusError(
                "OpenAI patent technical concept response was not completed"
            )

        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused patent technical concept selection"
            )

        parsed = getattr(response, "output_parsed", None)

        if parsed is None:
            raise StructuredResponseParseError(
                "OpenAI patent technical concept response was empty"
            )

        if not isinstance(parsed, PatentTechnicalConceptSelection):
            raise StructuredResponseParseError(
                "OpenAI patent technical concept response has invalid type"
            )

        try:
            plan = PatentTechnicalConceptPlan(
                request=request,
                concepts=parsed.concepts,
            )
        except ValidationError as exc:
            raise StructuredResponseValidationError(
                "OpenAI patent technical concept output was not grounded "
                "in the request",
                elapsed_seconds=elapsed_seconds,
                attempts=1,
            ) from exc

        return PatentTechnicalConceptGenerationResult(
            plan=plan,
            response_id=str(response.id),
            request_id=getattr(response, "_request_id", None),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
