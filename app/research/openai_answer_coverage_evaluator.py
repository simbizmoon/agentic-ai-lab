"""OpenAI-backed semantic answer coverage evaluation."""

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
from app.schemas.answer_coverage_judgment import AnswerCoverageJudgment
from app.services.structured_analysis import has_refusal
from app.services.text_generation import TokenUsage, extract_token_usage

ANSWER_COVERAGE_INSTRUCTIONS = """
Evaluate only whether the supplied claim set, taken together, sufficiently
covers the supplied research question and objective.

Use only:
- the research question;
- the research objective;
- the supplied claims.

Do not use outside knowledge.
Do not search for additional information.
Do not evaluate whether claims are factually true.
Do not evaluate whether evidence supports the claims.
Do not repair, expand, or supplement claims by inference.

Core policy:

The task is to judge semantic answer coverage, not individual claim relevance.

First identify the distinct answer requirements that are explicitly or
logically required by the question and objective. These may include, for
example:
- stages of a requested mechanism;
- both sides of a requested comparison;
- required conditions and resulting actions;
- inputs, decisions, enforcement, outputs, or consequences;
- multiple requested subquestions or constraints.

Derive required aspects only from the wording and structure of the supplied
question and objective. Do not invent domain-specific requirements from
outside knowledge.

Then assess the supplied claims as a set.

Choose exactly one coverage_level:

fully_covered:
The claim set substantively covers all important answer requirements that can
be derived from the question and objective. Minor wording differences or
nonessential detail omissions do not reduce full coverage.

partially_covered:
The claim set covers one or more important answer requirements, but at least
one important requirement remains materially missing or underdeveloped.
The answer is useful but incomplete.

insufficient:
The claim set fails to cover most of the important answer requirements, or
only supplies loosely related context without constructing a usable answer.

Important distinctions:

- Several individually relevant claims can still have poor answer coverage if
  they repeat the same aspect.
- One strong claim can still provide only partial coverage when the request
  has multiple important requirements.
- Coverage concerns whether requested aspects are addressed, not whether they
  are true, well-cited, authoritative, or stylistically polished.
- Do not penalize missing information that the question and objective do not
  require.
- Do not infer hidden product behavior, implementation details, best
  practices, or factual expectations from outside knowledge.

Return:
- coverage_level;
- coverage_score from 0.0 to 1.0 as a diagnostic signal only;
- covered_aspects;
- missing_aspects;
- a brief rationale.

The category is the policy judgment; the score is diagnostic only.
""".strip()


class ResponsesParseResource(Protocol):
    """Subset of Responses API required by this evaluator."""

    def parse(self, **kwargs: Any) -> Any:
        """Return one parsed Responses API result."""


class AnswerCoverageOpenAIClient(Protocol):
    """Injected client exposing Responses parsing."""

    responses: ResponsesParseResource


@dataclass(frozen=True)
class AnswerCoverageEvaluationResult:
    """One answer coverage evaluation with execution metadata."""

    judgment: AnswerCoverageJudgment
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAIAnswerCoverageEvaluator:
    """Judge one final claim set against a research request."""

    def __init__(
        self,
        *,
        client: AnswerCoverageOpenAIClient,
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
        claims: list[str],
    ) -> AnswerCoverageEvaluationResult:
        """Evaluate semantic coverage for one complete claim set."""

        cleaned_question = question.strip()
        cleaned_objective = objective.strip()
        cleaned_claims = [claim.strip() for claim in claims]

        if not cleaned_question:
            raise ValueError("question must not be blank")
        if not cleaned_objective:
            raise ValueError("objective must not be blank")
        if not cleaned_claims:
            raise ValueError("claims must not be empty")
        if any(not claim for claim in cleaned_claims):
            raise ValueError("claims must not contain blank values")

        model_input = json.dumps(
            {
                "question": cleaned_question,
                "objective": cleaned_objective,
                "claims": cleaned_claims,
            },
            ensure_ascii=False,
        )

        start_time = time.perf_counter()

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=ANSWER_COVERAGE_INSTRUCTIONS,
                input=model_input,
                text_format=AnswerCoverageJudgment,
                store=False,
            )
        except ValidationError as error:
            elapsed_seconds = max(
                0.0,
                time.perf_counter() - start_time,
            )
            raise StructuredResponseValidationError(
                "answer coverage response failed schema validation",
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
                "answer coverage response was incomplete"
            )

        if status != "completed":
            raise StructuredResponseStatusError(
                "answer coverage response was not completed"
            )

        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused answer coverage evaluation"
            )

        judgment = getattr(response, "output_parsed", None)

        if judgment is None:
            raise StructuredResponseParseError(
                "answer coverage response was empty"
            )

        if not isinstance(judgment, AnswerCoverageJudgment):
            raise StructuredResponseParseError(
                "answer coverage response has invalid type"
            )

        return AnswerCoverageEvaluationResult(
            judgment=judgment,
            response_id=str(response.id),
            request_id=getattr(response, "_request_id", None),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
