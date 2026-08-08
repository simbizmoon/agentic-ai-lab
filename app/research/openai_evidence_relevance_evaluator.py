"""OpenAI-backed semantic relevance evaluation for evidence passages."""

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
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceBatchJudgment,
    EvidenceRelevanceJudgment,
)
from app.services.structured_analysis import has_refusal
from app.services.text_generation import (
    TokenUsage,
    extract_token_usage,
)

EVIDENCE_RELEVANCE_INSTRUCTIONS = """
Evaluate only how relevant the supplied evidence passage is to the supplied
research question and objective.

Use only:
- the research question;
- the research objective;
- the evidence passage.

Do not use outside knowledge.
Do not search for additional information.
Do not evaluate whether the passage is factually true.
Do not evaluate source authority or credibility.
Do not invent missing facts or repair the passage by inference.

Core policy:

The task is to judge whether the passage is useful source material for
constructing the requested answer.

Treat the research question as the user's core intent.
Treat the objective as the requested answer scope, perspective, or method.

First identify what kind of answer is requested, for example:
- cause or explanation;
- mechanism;
- method or procedure;
- comparison or distinction;
- control or prevention;
- evaluation or measurement;
- requirement or constraint.

Then judge whether the passage provides evidence that can materially support
that requested answer type.

Choose exactly one relevance_level:

directly_relevant:
The passage contains substantive information that directly addresses an
important part of both the research question and objective. The passage need
not answer the entire request. A definition, mechanism step, concrete method,
specific condition, or directly responsive example can be directly_relevant
when it materially supports a requested answer part.

partially_relevant:
The passage does not directly provide the requested answer part, but it
contains materially useful evidence for constructing or understanding that
answer, such as a prerequisite, constraint, meaningful comparison baseline,
definition, measurement signal, implementation context, or closely connected
secondary factor.

partially_relevant requires more than topical similarity. The passage must
have real evidentiary value for constructing the requested answer.

irrelevant:
The passage does not materially contribute evidence for constructing the
requested answer. A passage can mention the same product, entity, domain,
workflow, or terminology and still be irrelevant when it addresses a
different capability, stage, purpose, or answer type.

Important distinctions:

- Same topic, product, entity, or domain alone is not enough for partial
  relevance.
- If the question asks for a mechanism, high-level product positioning alone
  is not the mechanism.
- If the question asks for a cause, a mitigation is not the cause.
- If the question asks for a method, a benefit is not the method.
- If the question asks for prevention or access control, post-hoc auditing is
  not itself preventive evidence.
- If the question asks for a comparison, a shared property alone does not
  establish the requested distinction, though a meaningful comparison
  baseline can be partially_relevant.
- If the question asks for an evaluation method, storage or change tracking
  alone is not the evaluation method.
- If the question asks for a control or bounded-execution mechanism,
  observability alone is not the control, though a necessary measurement
  signal can be partially_relevant.
- For prevention, authorization, limits, or other control questions,
  distinguish inputs and measurements from enforcement. Identity, policy
  inputs, counters, usage records, threshold comparisons, or other signals
  can be materially useful prerequisites, but they are not by themselves a
  directly_relevant control unless the passage also describes a decision or
  enforcement action that can allow, deny, block, stop, restrict, or otherwise
  change execution.
- A necessary mechanism step is not automatically directly_relevant when the
  requested answer type specifically requires control or enforcement.
- Terminology does not need to match exactly. Semantically equivalent wording,
  paraphrases, synonyms, and implementation-specific terms can still be
  directly_relevant.
- Do not downgrade a passage merely because it is concise or is one step of a
  larger mechanism.
- Do not promote a passage merely because it contains many query keywords.

Also return relevance_score from 0.0 to 1.0 as a diagnostic signal.
Do not use the score as a substitute for relevance_level.
The category is the policy judgment; the score is diagnostic only.

Explain the judgment briefly in rationale.
List specific relevance problems in issues.
""".strip()

EVIDENCE_RELEVANCE_BATCH_INSTRUCTIONS = (
    EVIDENCE_RELEVANCE_INSTRUCTIONS
    + """

Batch evaluation rules:
- Evaluate every supplied evidence item independently under the same policy.
- Return exactly one result for every supplied item_id.
- Copy each supplied item_id exactly; do not invent, omit, or duplicate IDs.
- Do not let the content of one evidence item change the judgment of another.
""".rstrip()
)


class ResponsesParseResource(Protocol):
    """Subset of Responses API required by this evaluator."""

    def parse(
        self,
        **kwargs: Any,
    ) -> Any:
        """Return one parsed Responses API result."""


class EvidenceRelevanceOpenAIClient(Protocol):
    """Injected client exposing Responses parsing."""

    responses: ResponsesParseResource


@dataclass(frozen=True)
class EvidenceRelevanceEvaluationResult:
    """One evidence relevance evaluation with execution metadata."""

    judgment: EvidenceRelevanceJudgment
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


@dataclass(frozen=True)
class EvidenceRelevanceBatchEvaluationResult:
    """One batched evidence relevance evaluation with execution metadata."""

    judgments: dict[str, EvidenceRelevanceJudgment]
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAIEvidenceRelevanceEvaluator:
    """Judge one evidence passage against a research request."""

    def __init__(
        self,
        *,
        client: EvidenceRelevanceOpenAIClient,
        model: str,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")

        self._client = client
        self._model = model

    @property
    def model(self) -> str:
        """Return the configured model."""

        return self._model

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        evidence_excerpt: str,
    ) -> EvidenceRelevanceEvaluationResult:
        """Evaluate semantic relevance for one evidence passage."""

        cleaned_question = question.strip()
        cleaned_objective = objective.strip()
        cleaned_evidence = evidence_excerpt.strip()

        if not cleaned_question:
            raise ValueError("question must not be blank")
        if not cleaned_objective:
            raise ValueError("objective must not be blank")
        if not cleaned_evidence:
            raise ValueError("evidence_excerpt must not be blank")

        model_input = json.dumps(
            {
                "question": cleaned_question,
                "objective": cleaned_objective,
                "evidence": cleaned_evidence,
            },
            ensure_ascii=False,
        )

        start_time = time.perf_counter()

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=EVIDENCE_RELEVANCE_INSTRUCTIONS,
                input=model_input,
                text_format=EvidenceRelevanceJudgment,
                store=False,
            )
        except ValidationError as error:
            elapsed_seconds = max(
                0.0,
                time.perf_counter() - start_time,
            )
            raise StructuredResponseValidationError(
                "evidence relevance response failed schema validation",
                elapsed_seconds=elapsed_seconds,
                attempts=1,
            ) from error

        elapsed_seconds = max(
            0.0,
            time.perf_counter() - start_time,
        )

        status = getattr(response, "status", None)

        if status == "incomplete":
            raise StructuredResponseIncompleteError(
                "evidence relevance response was incomplete"
            )

        if status != "completed":
            raise StructuredResponseStatusError(
                "evidence relevance response was not completed"
            )

        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused evidence relevance evaluation"
            )

        judgment = getattr(response, "output_parsed", None)

        if judgment is None:
            raise StructuredResponseParseError(
                "evidence relevance response was empty"
            )

        if not isinstance(judgment, EvidenceRelevanceJudgment):
            raise StructuredResponseParseError(
                "evidence relevance response has invalid type"
            )

        return EvidenceRelevanceEvaluationResult(
            judgment=judgment,
            response_id=str(response.id),
            request_id=getattr(response, "_request_id", None),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )

    def evaluate_batch(
        self,
        *,
        question: str,
        objective: str,
        evidence_items: list[tuple[str, str]],
    ) -> EvidenceRelevanceBatchEvaluationResult:
        """Evaluate multiple local evidence passages in one API request."""

        cleaned_question = question.strip()
        cleaned_objective = objective.strip()

        if not cleaned_question:
            raise ValueError("question must not be blank")
        if not cleaned_objective:
            raise ValueError("objective must not be blank")
        if not evidence_items:
            raise ValueError("evidence_items must not be empty")

        normalized_ids: list[str] = []
        cleaned_items: list[dict[str, str]] = []
        for item_id, evidence_excerpt in evidence_items:
            cleaned_id = item_id.strip()
            cleaned_evidence = evidence_excerpt.strip()
            if not cleaned_id:
                raise ValueError("batch item_id must not be blank")
            if not cleaned_evidence:
                raise ValueError(
                    "batch evidence excerpt must not be blank"
                )
            normalized_ids.append(cleaned_id.casefold())
            cleaned_items.append(
                {
                    "item_id": cleaned_id,
                    "evidence": cleaned_evidence,
                }
            )

        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("batch item IDs must be unique")

        model_input = json.dumps(
            {
                "question": cleaned_question,
                "objective": cleaned_objective,
                "evidence_items": cleaned_items,
            },
            ensure_ascii=False,
        )

        start_time = time.perf_counter()
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=EVIDENCE_RELEVANCE_BATCH_INSTRUCTIONS,
                input=model_input,
                text_format=EvidenceRelevanceBatchJudgment,
                store=False,
            )
        except ValidationError as error:
            elapsed_seconds = max(
                0.0,
                time.perf_counter() - start_time,
            )
            raise StructuredResponseValidationError(
                "batched evidence relevance response failed schema validation",
                elapsed_seconds=elapsed_seconds,
                attempts=1,
            ) from error

        elapsed_seconds = max(
            0.0,
            time.perf_counter() - start_time,
        )
        status = getattr(response, "status", None)

        if status == "incomplete":
            raise StructuredResponseIncompleteError(
                "batched evidence relevance response was incomplete"
            )
        if status != "completed":
            raise StructuredResponseStatusError(
                "batched evidence relevance response was not completed"
            )
        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused batched evidence relevance evaluation"
            )

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise StructuredResponseParseError(
                "batched evidence relevance response was empty"
            )
        if not isinstance(parsed, EvidenceRelevanceBatchJudgment):
            raise StructuredResponseParseError(
                "batched evidence relevance response has invalid type"
            )

        expected_ids = [item["item_id"] for item in cleaned_items]
        expected_by_folded = {
            item_id.casefold(): item_id
            for item_id in expected_ids
        }
        returned_ids = [item.item_id for item in parsed.items]
        returned_folded = [
            item_id.casefold()
            for item_id in returned_ids
        ]
        if (
            len(returned_ids) != len(expected_ids)
            or len(set(returned_folded)) != len(returned_folded)
            or set(returned_folded) != set(expected_by_folded)
        ):
            raise StructuredResponseParseError(
                "batched evidence relevance item IDs did not match the request"
            )

        judgments = {
            expected_by_folded[item.item_id.casefold()]: item.judgment
            for item in parsed.items
        }
        return EvidenceRelevanceBatchEvaluationResult(
            judgments=judgments,
            response_id=str(response.id),
            request_id=getattr(response, "_request_id", None),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
