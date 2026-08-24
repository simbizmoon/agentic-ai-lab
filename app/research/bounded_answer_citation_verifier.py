"""Bounded semantic verification of parsed answer citation pairs."""

from __future__ import annotations

import re
import time
from typing import Protocol

from app.budget import (
    BudgetUsage,
    ExecutionBudget,
    ensure_can_start_attempt,
    ensure_within_budget,
    record_attempt,
)
from app.exceptions import (
    ExecutionBudgetError,
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)
from app.research.deterministic_answer_citation_parser import (
    DeterministicAnswerCitationParser,
)
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationBatchEvaluationResult,
    SemanticCitationEvaluationResult,
)
from app.schemas.answer_citation_validation import (
    AnswerCitationPairValidation,
    AnswerCitationValidationRequest,
    AnswerCitationValidationResult,
    AnswerCitationValidationStatus,
    AnswerCitationValidationUsage,
    AnswerStatement,
    CitationPairEvaluationState,
)
from app.schemas.retrieval_result import RetrievalResult

_MARKER_PATTERN = re.compile(r"\[[A-Za-z]\d+\]")
_BATCH_FALLBACK_ERRORS = (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)


class SemanticCitationEvaluatorProtocol(Protocol):
    def evaluate(
        self, *, claim_text: str, evidence_excerpt: str
    ) -> SemanticCitationEvaluationResult: ...


class BoundedAnswerCitationVerifier:
    """Parse an answer and verify every exact statement/citation pair."""

    def __init__(
        self,
        *,
        evaluator: SemanticCitationEvaluatorProtocol,
        parser: DeterministicAnswerCitationParser | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._parser = parser or DeterministicAnswerCitationParser()

    def verify(
        self, *, request: AnswerCitationValidationRequest
    ) -> AnswerCitationValidationResult:
        if not isinstance(request, AnswerCitationValidationRequest):
            raise TypeError("request must be an AnswerCitationValidationRequest")
        statements = self._parser.parse(request=request)
        evidence = {
            citation.citation_id: retrieval
            for citation, retrieval in zip(
                request.context.citations,
                request.evidence_retrievals,
                strict=True,
            )
        }
        specs: list[tuple[str, AnswerStatement, str, str, RetrievalResult]] = []
        for statement in statements:
            claim_text = _MARKER_PATTERN.sub("", statement.text).strip()
            if statement.cited_ids and not claim_text:
                raise ValueError("cited answer statement must contain claim text")
            for citation_id in statement.cited_ids:
                specs.append(
                    (
                        f"pair-{len(specs) + 1:03d}",
                        statement,
                        citation_id,
                        claim_text,
                        evidence[citation_id],
                    )
                )
        if len(specs) > request.budget.maximum_pairs:
            raise ValueError("citation pair count exceeds validation budget")

        budget = ExecutionBudget(
            max_attempts=request.budget.maximum_attempts,
            max_recorded_tokens=request.budget.maximum_recorded_tokens,
            max_elapsed_seconds=request.budget.maximum_elapsed_seconds,
        )
        usage = BudgetUsage()
        pairs: list[AnswerCitationPairValidation] = []
        exhausted = False

        batch_evaluate = getattr(self._evaluator, "evaluate_batch", None)
        if specs and callable(batch_evaluate):
            started = time.perf_counter()
            try:
                ensure_can_start_attempt(budget=budget, usage=usage)
                batch: SemanticCitationBatchEvaluationResult = batch_evaluate(
                    citation_items=[
                        (item_id, claim, retrieval.chunk.text)
                        for item_id, _, _, claim, retrieval in specs
                    ]
                )
                if set(batch.judgments) != {item_id for item_id, *_ in specs}:
                    raise StructuredResponseParseError(
                        "semantic citation batch IDs did not match pairs"
                    )
            except ExecutionBudgetError:
                exhausted = True
            except _BATCH_FALLBACK_ERRORS:
                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=0,
                    elapsed_seconds=max(0.0, time.perf_counter() - started),
                )
            else:
                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=batch.usage.total_tokens if batch.usage else 0,
                    elapsed_seconds=batch.elapsed_seconds,
                )
                try:
                    ensure_within_budget(budget=budget, usage=usage)
                except ExecutionBudgetError:
                    exhausted = True
                pairs = [
                    self._evaluated(
                        statement=statement,
                        citation_id=citation_id,
                        evidence=retrieval,
                        judgment=batch.judgments[item_id],
                        response_id=batch.response_id,
                        request_id=batch.request_id,
                    )
                    for item_id, statement, citation_id, _, retrieval in specs
                ]
                return self._result(request, statements, pairs, usage, exhausted)

        if exhausted:
            pairs = [
                self._unevaluated(statement, retrieval, citation_id)
                for _, statement, citation_id, _, retrieval in specs
            ]
            return self._result(request, statements, pairs, usage, True)

        for index, (_, statement, citation_id, claim, retrieval) in enumerate(specs):
            try:
                ensure_can_start_attempt(budget=budget, usage=usage)
            except ExecutionBudgetError:
                exhausted = True
                for (
                    _,
                    remaining_statement,
                    remaining_id,
                    _,
                    remaining_evidence,
                ) in specs[index:]:
                    pairs.append(
                        self._unevaluated(
                            remaining_statement, remaining_evidence, remaining_id
                        )
                    )
                break
            result = self._evaluator.evaluate(
                claim_text=claim,
                evidence_excerpt=retrieval.chunk.text,
            )
            pairs.append(
                self._evaluated(
                    statement=statement,
                    citation_id=citation_id,
                    evidence=retrieval,
                    judgment=result.judgment,
                    response_id=result.response_id,
                    request_id=result.request_id,
                )
            )
            usage = record_attempt(
                usage=usage,
                recorded_tokens=result.usage.total_tokens if result.usage else 0,
                elapsed_seconds=result.elapsed_seconds,
            )
            try:
                ensure_within_budget(budget=budget, usage=usage)
            except ExecutionBudgetError:
                exhausted = True
                for (
                    _,
                    remaining_statement,
                    remaining_id,
                    _,
                    remaining_evidence,
                ) in specs[index + 1 :]:
                    pairs.append(
                        self._unevaluated(
                            remaining_statement, remaining_evidence, remaining_id
                        )
                    )
                break
        return self._result(request, statements, pairs, usage, exhausted)

    @staticmethod
    def _evaluated(
        *, statement, citation_id, evidence, judgment, response_id, request_id
    ):
        return AnswerCitationPairValidation(
            statement_id=statement.statement_id,
            citation_id=citation_id,
            evidence=evidence,
            evaluation_state=CitationPairEvaluationState.EVALUATED,
            judgment=judgment,
            response_id=response_id,
            request_id=request_id,
        )

    @staticmethod
    def _unevaluated(statement, evidence, citation_id):
        return AnswerCitationPairValidation(
            statement_id=statement.statement_id,
            citation_id=citation_id,
            evidence=evidence,
            evaluation_state=CitationPairEvaluationState.UNEVALUATED,
        )

    @staticmethod
    def _result(request, statements, pairs, usage, exhausted):
        uncited = (
            [item.statement_id for item in statements if not item.cited_ids]
            if request.citation_required
            else []
        )
        unevaluated = sum(
            item.evaluation_state is CitationPairEvaluationState.UNEVALUATED
            for item in pairs
        )
        rejected = any(
            item.judgment is not None
            and item.judgment.support_level.value in {"unsupported", "contradicted"}
            for item in pairs
        )
        status = (
            AnswerCitationValidationStatus.INCOMPLETE
            if unevaluated
            else AnswerCitationValidationStatus.FAILED
            if uncited or rejected
            else AnswerCitationValidationStatus.PASSED
        )
        return AnswerCitationValidationResult(
            request=request,
            statements=statements,
            pairs=pairs,
            uncited_statement_ids=uncited,
            usage=AnswerCitationValidationUsage(
                attempts=usage.attempts,
                recorded_tokens=usage.recorded_tokens,
                elapsed_seconds=usage.elapsed_seconds,
                statement_count=len(statements),
                pair_count=len(pairs),
                evaluated_pair_count=len(pairs) - unevaluated,
                unevaluated_pair_count=unevaluated,
            ),
            budget_exhausted=exhausted,
            status=status,
        )
