"""OpenAI-backed semantic citation entailment evaluation."""

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
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)
from app.services.structured_analysis import has_refusal
from app.services.text_generation import (
    TokenUsage,
    extract_token_usage,
)

SEMANTIC_CITATION_INSTRUCTIONS = """
Evaluate only whether the supplied evidence supports the supplied claim.

Use only the claim and evidence provided in the input.
Do not use outside knowledge.
Do not search for additional information.
Do not repair missing evidence by inference.

Pay particular attention to:
- absolute words such as always, never, all, and only;
- quantities and numerical claims;
- causal claims;
- conditions and exceptions;
- entity mismatches;
- claims that are broader or stronger than the evidence.

Choose exactly one support_level:

fully_supported:
The evidence directly supports all important parts of the claim.
Minor wording differences are acceptable when the meaning is preserved.

partially_supported:
The evidence supports the same core subject and predicate as the claim,
but the claim adds, strengthens, or broadens one or more qualifiers,
frequencies, conditions, scopes, quantities, or secondary assertions
that are not fully supported.
The claim could become supported through revision.

unsupported:
The evidence does not provide enough information to establish the core
claim, but it does not explicitly conflict with the claim.

contradicted:
The evidence explicitly states something that cannot be true at the
same time as an important part of the claim.

Important distinctions:

- Do not treat missing information as contradiction.

- Use partially_supported when the same core subject and predicate are
  supported but the claim overstates a qualifier, frequency, condition,
  scope, quantity, or secondary assertion.

- Use unsupported when the evidence leaves a claimed fact unspecified
  or provides evidence about a different subject, predicate, capability,
  or relationship.

- Use contradicted only when the evidence and claim contain assertions
  that are mutually incompatible.

Examples:

Evidence:
"The service may retry failed requests."
Claim:
"The service always retries failed requests."
support_level:
partially_supported

Evidence:
"The timeout is configurable."
Claim:
"The timeout is exactly 30 seconds."
support_level:
unsupported

Evidence:
"The maximum retry count is three."
Claim:
"The maximum retry count is five."
support_level:
contradicted

Also return an entailment_score from 0.0 to 1.0 as a diagnostic signal.
Do not use the score as a substitute for support_level.
1.0 means direct and complete support.
0.0 means no support or direct contradiction.

Explain the judgment briefly in rationale.
List specific support problems in issues.
""".strip()


class ResponsesParseResource(Protocol):
    """Subset of Responses API required by this evaluator."""

    def parse(
        self,
        **kwargs: Any,
    ) -> Any:
        """Return one parsed Responses API result."""


class SemanticCitationOpenAIClient(Protocol):
    """Injected client exposing Responses parsing."""

    responses: ResponsesParseResource


@dataclass(frozen=True)
class SemanticCitationEvaluationResult:
    """One semantic citation evaluation with execution metadata."""

    judgment: SemanticCitationJudgment
    decision: ResearchCitationDecision
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAISemanticCitationEvaluator:
    """Judge claim-to-evidence entailment using structured output."""

    def __init__(
        self,
        *,
        client: SemanticCitationOpenAIClient,
        model: str,
    ) -> None:
        if not model.strip():
            raise ValueError(
                "model must not be blank"
            )

        self._client = client
        self._model = model

    def evaluate(
        self,
        *,
        claim_text: str,
        evidence_excerpt: str,
    ) -> SemanticCitationEvaluationResult:
        """Evaluate semantic support for one claim/evidence pair."""

        cleaned_claim = claim_text.strip()
        cleaned_evidence = evidence_excerpt.strip()

        if not cleaned_claim:
            raise ValueError(
                "claim_text must not be blank"
            )

        if not cleaned_evidence:
            raise ValueError(
                "evidence_excerpt must not be blank"
            )

        model_input = json.dumps(
            {
                "claim": cleaned_claim,
                "evidence": cleaned_evidence,
            },
            ensure_ascii=False,
        )

        start_time = time.perf_counter()

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=(
                    SEMANTIC_CITATION_INSTRUCTIONS
                ),
                input=model_input,
                text_format=SemanticCitationJudgment,
                store=False,
            )
        except ValidationError as error:
            elapsed_seconds = max(
                0.0,
                time.perf_counter() - start_time,
            )
            raise StructuredResponseValidationError(
                "semantic citation response failed "
                "schema validation",
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
                "semantic citation response was incomplete"
            )

        if status != "completed":
            raise StructuredResponseStatusError(
                "semantic citation response was not completed"
            )

        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused semantic citation evaluation"
            )

        judgment = getattr(
            response,
            "output_parsed",
            None,
        )

        if judgment is None:
            raise StructuredResponseParseError(
                "semantic citation response was empty"
            )

        if not isinstance(
            judgment,
            SemanticCitationJudgment,
        ):
            raise StructuredResponseParseError(
                "semantic citation response has invalid type"
            )

        return SemanticCitationEvaluationResult(
            judgment=judgment,
            decision=self.decision_for_judgment(
                judgment
            ),
            response_id=str(response.id),
            request_id=getattr(
                response,
                "_request_id",
                None,
            ),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )

    @staticmethod
    def decision_for_judgment(
        judgment: SemanticCitationJudgment,
    ) -> ResearchCitationDecision:
        """Map semantic support category to a decision."""

        if (
            judgment.support_level
            is SemanticCitationSupportLevel.FULLY_SUPPORTED
        ):
            return ResearchCitationDecision.VERIFIED

        if (
            judgment.support_level
            is SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
        ):
            return (
                ResearchCitationDecision.NEEDS_REVISION
            )

        return ResearchCitationDecision.REJECTED
