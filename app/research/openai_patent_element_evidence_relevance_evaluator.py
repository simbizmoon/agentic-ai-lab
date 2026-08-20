"""OpenAI-backed technical relevance evaluation for patent claim elements."""

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
from app.schemas.evidence_relevance_judgment import EvidenceRelevanceJudgment
from app.services.structured_analysis import has_refusal
from app.services.text_generation import TokenUsage, extract_token_usage

PATENT_ELEMENT_EVIDENCE_RELEVANCE_INSTRUCTIONS = """
Evaluate only the technical relevance of the supplied prior-art evidence
excerpt to the supplied patent claim element.

Use only:
- the patent claim element text;
- the prior-art evidence excerpt.

Do not use outside knowledge.
Do not search for additional information.
Do not repair or supplement either text by inference.
Do not evaluate source authority, credibility, priority, family status, or
legal status.

The task is technical relevance mapping only.

Choose exactly one relevance_level:

directly_relevant:
The evidence excerpt expressly or semantically describes the same technical
feature, function, condition, relationship, or combination represented by the
claim element closely enough to be directly useful for later technical
comparison.

partially_relevant:
The evidence excerpt contains materially useful technical information related
to the claim element, but does not directly describe the whole technical
feature, function, condition, relationship, or combination represented by the
claim element.

irrelevant:
The evidence excerpt does not materially help compare the technical content of
the claim element. Shared vocabulary, field, component names, or broad purpose
alone are not enough.

Important rules:
- Compare technical meaning, not keyword overlap.
- Semantically equivalent wording can be directly relevant even when wording
  differs.
- Do not treat a broad component mention as directly relevant when the claim
  element requires a specific function, condition, relationship, or
  combination that the evidence does not describe.
- Do not treat implementation context alone as direct relevance when the
  claimed technical relationship is absent.
- Do not infer missing structure, function, timing, causation, control logic,
  or relationships.
- Evaluate only the supplied element against the supplied excerpt.
- Do not evaluate the remainder of the patent claim.
- Do not determine whether the evidence fully covers a patent claim.
- Do not make novelty, anticipation, obviousness, inventive-step, validity,
  invalidity, infringement, freedom-to-operate, essentiality, claim-scope,
  dependency, or other legal conclusions.
- "directly_relevant" is a technical mapping label only. It does not mean that
  a patent claim is anticipated, lacks novelty, is invalid, or is infringed.
- "partially_relevant" is not a legal finding of partial anticipation or
  obviousness.
- "irrelevant" does not establish patentability or validity.

Also return relevance_score from 0.0 to 1.0 as a diagnostic signal.
The categorical relevance_level is the policy judgment; the score is
diagnostic only.

Explain the technical comparison briefly in rationale.
List concrete technical gaps or mismatches in issues.
""".strip()


class PatentElementEvidenceResponsesResource(Protocol):
    """Minimal Responses resource required by this evaluator."""

    def parse(self, **kwargs: Any) -> Any: ...


class PatentElementEvidenceOpenAIClient(Protocol):
    """Minimal injected OpenAI client contract."""

    responses: PatentElementEvidenceResponsesResource


class PatentElementEvidenceProviderError(RuntimeError):
    """Raised when the external technical-relevance request fails."""


@dataclass(frozen=True)
class PatentElementEvidenceRelevanceResult:
    """One technical relevance judgment plus provider execution metadata."""

    judgment: EvidenceRelevanceJudgment
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAIPatentElementEvidenceRelevanceEvaluator:
    """Judge one prior-art excerpt against one patent claim element."""

    def __init__(
        self,
        *,
        client: PatentElementEvidenceOpenAIClient,
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

    def evaluate(
        self,
        *,
        element_text: str,
        evidence_excerpt: str,
    ) -> PatentElementEvidenceRelevanceResult:
        """Evaluate technical relevance for one element/evidence pair."""

        cleaned_element = element_text.strip()
        cleaned_evidence = evidence_excerpt.strip()

        if not cleaned_element:
            raise ValueError("element_text must not be blank")
        if not cleaned_evidence:
            raise ValueError("evidence_excerpt must not be blank")

        payload = {
            "claim_element": cleaned_element,
            "prior_art_evidence": cleaned_evidence,
        }

        start_time = time.perf_counter()

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=PATENT_ELEMENT_EVIDENCE_RELEVANCE_INSTRUCTIONS,
                input=json.dumps(payload, ensure_ascii=False),
                text_format=EvidenceRelevanceJudgment,
                store=False,
            )
        except ValidationError as exc:
            elapsed_seconds = max(0.0, time.perf_counter() - start_time)
            raise StructuredResponseValidationError(
                "OpenAI patent element/evidence response failed schema validation",
                elapsed_seconds=elapsed_seconds,
                attempts=1,
            ) from exc
        except Exception as exc:
            raise PatentElementEvidenceProviderError(
                "OpenAI patent element/evidence relevance request failed"
            ) from exc

        elapsed_seconds = max(0.0, time.perf_counter() - start_time)
        status = getattr(response, "status", None)

        if status == "incomplete":
            raise StructuredResponseIncompleteError(
                "OpenAI patent element/evidence response was incomplete"
            )

        if status != "completed":
            raise StructuredResponseStatusError(
                "OpenAI patent element/evidence response was not completed"
            )

        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused patent element/evidence relevance evaluation"
            )

        parsed = getattr(response, "output_parsed", None)

        if parsed is None:
            raise StructuredResponseParseError(
                "OpenAI patent element/evidence response was empty"
            )

        if not isinstance(parsed, EvidenceRelevanceJudgment):
            raise StructuredResponseParseError(
                "OpenAI patent element/evidence response has invalid type"
            )

        return PatentElementEvidenceRelevanceResult(
            judgment=parsed,
            response_id=str(response.id),
            request_id=getattr(response, "_request_id", None),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
