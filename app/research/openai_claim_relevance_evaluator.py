"""OpenAI-backed semantic relevance evaluation for research claims."""

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
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceBatchJudgment,
    ClaimRelevanceJudgment,
)
from app.services.structured_analysis import has_refusal
from app.services.text_generation import (
    TokenUsage,
    extract_token_usage,
)

CLAIM_RELEVANCE_INSTRUCTIONS = """
Evaluate only how relevant the supplied claim is to the supplied research
question and objective.

Use only:
- the research question;
- the research objective;
- the claim.

Do not use outside knowledge.
Do not search for additional information.
Do not evaluate whether the claim is factually true.
Do not evaluate whether evidence supports the claim.
Do not repair or expand the claim by inference.

Core policy:

The task is to judge how much the claim itself contributes to constructing
the requested answer.

Treat the research question as the user's core intent.
Treat the objective as the requested answer scope, perspective, or method.
A claim should be directly_relevant only when it materially satisfies both.

First identify what kind of answer is requested, for example:
- cause or explanation;
- mechanism;
- method or procedure;
- comparison or distinction;
- control or prevention;
- evaluation or measurement;
- requirement or constraint.

Then judge whether the claim provides that requested answer type.

Choose exactly one relevance_level:

directly_relevant:
The claim itself provides a substantive answer unit that directly satisfies
an important part of both the research question and the objective.
It does not need to answer the entire request. A narrow claim can still be
directly_relevant when it directly answers one important requested subpart.

partially_relevant:
The claim does not itself provide the requested answer, but it supplies
information that is materially useful for constructing or understanding that
answer, such as a necessary condition, relevant constraint, meaningful
background, comparison baseline, prerequisite, measurement signal, or closely
connected secondary factor.

partially_relevant requires more than topical similarity. The claim must have
real explanatory value in the final answer.

A comparison baseline can be partially_relevant when it establishes a shared
reference point that is materially useful for explaining the requested
difference, even though it does not itself state the difference.

A measurement or observability signal can be partially_relevant when that
measurement is a practical prerequisite for implementing or evaluating the
requested control. Mere reporting or analytics that are not needed for the
requested control should remain irrelevant.

irrelevant:
The claim does not materially contribute to constructing the requested answer.
A claim can be about the same product, entity, domain, safety area, or
workflow and still be irrelevant when it addresses a different capability,
stage, purpose, or answer type.

Important distinctions:

- Same topic, product, entity, or domain alone is not enough for partial
  relevance.
- If the question asks for a cause, a mitigation is not the cause.
- If the question asks for a method, a benefit is not the method.
- If the question asks for prevention or access control, post-hoc auditing is
  not itself a preventive or access-control mechanism.
- If the question asks for a comparison, stating only a shared property does
  not provide the comparison. However, a shared property can still be
  partially_relevant when it establishes a meaningful comparison baseline.
- If the question asks for an evaluation method, change tracking or version
  storage alone is not an evaluation method.
- If the question asks for a control or bounded-execution mechanism,
  observability alone is not the control. However, measurement can be
  partially_relevant when it is materially required to implement or evaluate
  that control.
- If a claim answers the broad question but misses a narrowing requirement in
  the objective, prefer partially_relevant rather than directly_relevant.
- Broadly useful context that is not materially needed to construct the
  requested answer should be irrelevant, not partially_relevant.
- A claim can be fully supported by evidence and still be irrelevant to the
  user's research request.

Also return relevance_score from 0.0 to 1.0 as a diagnostic signal.
Do not use the score as a substitute for relevance_level.
The category is the policy judgment; the score is diagnostic only.

Explain the judgment briefly in rationale.
List specific relevance problems in issues.
""".strip()

CLAIM_RELEVANCE_BATCH_INSTRUCTIONS = (
    CLAIM_RELEVANCE_INSTRUCTIONS
    + """

Batch evaluation rules:
- Evaluate every supplied claim item independently under the same policy.
- Return exactly one result for every supplied item_id.
- Copy each supplied item_id exactly; do not invent, omit, or duplicate IDs.
- Do not let one claim item change the judgment of another item.
""".rstrip()
)


class ResponsesParseResource(Protocol):
    """Subset of Responses API required by this evaluator."""

    def parse(
        self,
        **kwargs: Any,
    ) -> Any:
        """Return one parsed Responses API result."""


class ClaimRelevanceOpenAIClient(Protocol):
    """Injected client exposing Responses parsing."""

    responses: ResponsesParseResource


@dataclass(frozen=True)
class ClaimRelevanceEvaluationResult:
    """One claim relevance evaluation with execution metadata."""

    judgment: ClaimRelevanceJudgment
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


@dataclass(frozen=True)
class ClaimRelevanceBatchEvaluationResult:
    """One batched claim relevance evaluation with shared metadata."""

    judgments: dict[str, ClaimRelevanceJudgment]
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAIClaimRelevanceEvaluator:
    """Judge one claim against a research question and objective."""

    def __init__(
        self,
        *,
        client: ClaimRelevanceOpenAIClient,
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
        claim_text: str,
    ) -> ClaimRelevanceEvaluationResult:
        """Evaluate semantic relevance for one research claim."""

        cleaned_question = question.strip()
        cleaned_objective = objective.strip()
        cleaned_claim = claim_text.strip()

        if not cleaned_question:
            raise ValueError("question must not be blank")
        if not cleaned_objective:
            raise ValueError("objective must not be blank")
        if not cleaned_claim:
            raise ValueError("claim_text must not be blank")

        model_input = json.dumps(
            {
                "question": cleaned_question,
                "objective": cleaned_objective,
                "claim": cleaned_claim,
            },
            ensure_ascii=False,
        )

        start_time = time.perf_counter()

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=CLAIM_RELEVANCE_INSTRUCTIONS,
                input=model_input,
                text_format=ClaimRelevanceJudgment,
                store=False,
            )
        except ValidationError as error:
            elapsed_seconds = max(
                0.0,
                time.perf_counter() - start_time,
            )
            raise StructuredResponseValidationError(
                "claim relevance response failed schema validation",
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
                "claim relevance response was incomplete"
            )

        if status != "completed":
            raise StructuredResponseStatusError(
                "claim relevance response was not completed"
            )

        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused claim relevance evaluation"
            )

        judgment = getattr(
            response,
            "output_parsed",
            None,
        )

        if judgment is None:
            raise StructuredResponseParseError(
                "claim relevance response was empty"
            )

        if not isinstance(
            judgment,
            ClaimRelevanceJudgment,
        ):
            raise StructuredResponseParseError(
                "claim relevance response has invalid type"
            )

        return ClaimRelevanceEvaluationResult(
            judgment=judgment,
            response_id=str(response.id),
            request_id=getattr(
                response,
                "_request_id",
                None,
            ),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
    def evaluate_batch(
        self,
        *,
        question: str,
        objective: str,
        claim_items: list[tuple[str, str]],
    ) -> ClaimRelevanceBatchEvaluationResult:
        """Evaluate multiple claims in one structured API request."""

        cleaned_question = question.strip()
        cleaned_objective = objective.strip()

        if not cleaned_question:
            raise ValueError("question must not be blank")
        if not cleaned_objective:
            raise ValueError("objective must not be blank")
        if not claim_items:
            raise ValueError("claim_items must not be empty")

        normalized_ids: list[str] = []
        cleaned_items: list[dict[str, str]] = []
        for item_id, claim_text in claim_items:
            cleaned_id = item_id.strip()
            cleaned_claim = claim_text.strip()
            if not cleaned_id:
                raise ValueError("batch item_id must not be blank")
            if not cleaned_claim:
                raise ValueError("batch claim text must not be blank")
            normalized_ids.append(cleaned_id.casefold())
            cleaned_items.append(
                {"item_id": cleaned_id, "claim": cleaned_claim}
            )

        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("batch item IDs must be unique")

        model_input = json.dumps(
            {
                "question": cleaned_question,
                "objective": cleaned_objective,
                "claim_items": cleaned_items,
            },
            ensure_ascii=False,
        )

        start_time = time.perf_counter()
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=CLAIM_RELEVANCE_BATCH_INSTRUCTIONS,
                input=model_input,
                text_format=ClaimRelevanceBatchJudgment,
                store=False,
            )
        except ValidationError as error:
            elapsed_seconds = max(
                0.0,
                time.perf_counter() - start_time,
            )
            raise StructuredResponseValidationError(
                "batched claim relevance response failed schema validation",
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
                "batched claim relevance response was incomplete"
            )
        if status != "completed":
            raise StructuredResponseStatusError(
                "batched claim relevance response was not completed"
            )
        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused batched claim relevance evaluation"
            )

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise StructuredResponseParseError(
                "batched claim relevance response was empty"
            )
        if not isinstance(parsed, ClaimRelevanceBatchJudgment):
            raise StructuredResponseParseError(
                "batched claim relevance response has invalid type"
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
                "batched claim relevance item IDs did not match the request"
            )

        judgments = {
            expected_by_folded[item.item_id.casefold()]: item.judgment
            for item in parsed.items
        }
        return ClaimRelevanceBatchEvaluationResult(
            judgments=judgments,
            response_id=str(response.id),
            request_id=getattr(
                response,
                "_request_id",
                None,
            ),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
