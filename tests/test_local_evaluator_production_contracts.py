"""Production-contract tests for local bounded evaluators."""

from app.research.local_answer_coverage_evaluator import (
    LocalAnswerCoverageEvaluator,
)
from app.research.local_claim_relevance_evaluator import (
    LocalClaimRelevanceEvaluator,
)
from app.research.local_semantic_citation_evaluator import (
    LocalSemanticCitationEvaluator,
)
from app.research.openai_answer_coverage_evaluator import (
    AnswerCoverageEvaluationResult,
)
from app.research.openai_claim_relevance_evaluator import (
    ClaimRelevanceEvaluationResult,
)
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationEvaluationResult,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.answer_coverage_judgment import (
    AnswerCoverageJudgment,
    AnswerCoverageLevel,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceJudgment,
    ClaimRelevanceLevel,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)
from app.services.ollama_client import OllamaGenerateResponse


def generated(response: str) -> OllamaGenerateResponse:
    return OllamaGenerateResponse(
        model="qwen3.5:4b",
        response=response,
        thinking="",
        done=True,
        done_reason="stop",
        total_duration_ns=1_000_000,
        load_duration_ns=10,
        prompt_eval_count=30,
        prompt_eval_duration_ns=100,
        eval_count=10,
        eval_duration_ns=100,
    )


class FakeClient:
    def __init__(self, response: str) -> None:
        self._result = generated(response)

    def generate(self, **_kwargs: object) -> OllamaGenerateResponse:
        return self._result


def test_claim_relevance_returns_production_result_with_usage() -> None:
    judgment = ClaimRelevanceJudgment(
        relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.9,
        rationale="Directly answers the objective.",
        issues=[],
    )
    evaluator = LocalClaimRelevanceEvaluator(
        client=FakeClient(judgment.model_dump_json()),
        model="qwen3.5:4b",
    )

    result = evaluator.evaluate(
        question="What changed?",
        objective="Identify the change.",
        claim_text="The retry limit changed from two to three.",
    )

    assert isinstance(result, ClaimRelevanceEvaluationResult)
    assert result.usage is not None
    assert result.usage.input_tokens == 30
    assert result.usage.output_tokens == 10
    assert result.usage.total_tokens == 40


def test_semantic_citation_returns_production_result_and_decision() -> None:
    judgment = SemanticCitationJudgment(
        support_level=SemanticCitationSupportLevel.PARTIALLY_SUPPORTED,
        entailment_score=0.6,
        rationale="One qualifier is not supported.",
        issues=["missing qualifier"],
    )
    evaluator = LocalSemanticCitationEvaluator(
        client=FakeClient(judgment.model_dump_json()),
        model="qwen3.5:4b",
    )

    result = evaluator.evaluate(
        claim_text="The service always retries failures.",
        evidence_excerpt="The service retries retryable failures.",
    )

    assert isinstance(result, SemanticCitationEvaluationResult)
    assert result.decision is ResearchCitationDecision.NEEDS_REVISION
    assert result.usage is not None
    assert result.usage.total_tokens == 40


def test_answer_coverage_returns_production_result_with_attempts() -> None:
    judgment = AnswerCoverageJudgment(
        coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
        coverage_score=0.6,
        covered_aspects=["measurement"],
        missing_aspects=["enforcement"],
        rationale="The enforcement step is missing.",
    )
    evaluator = LocalAnswerCoverageEvaluator(
        client=FakeClient(judgment.model_dump_json()),
        model="qwen3.5:4b",
    )

    result = evaluator.evaluate(
        question="How is the budget enforced?",
        objective="Explain measurement and enforcement.",
        claims=["Usage is measured after every call."],
    )

    assert isinstance(result, AnswerCoverageEvaluationResult)
    assert result.attempts == 1
    assert result.usage is not None
    assert result.usage.total_tokens == 40
