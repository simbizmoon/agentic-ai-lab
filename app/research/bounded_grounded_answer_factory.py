"""Composition factory for the bounded grounded-answer workflow."""

from __future__ import annotations

from app.rag.grounded_answer_service import OpenAIClientProtocol
from app.research.bounded_answer_citation_verifier import (
    BoundedAnswerCitationVerifier,
    SemanticCitationEvaluatorProtocol,
)
from app.research.bounded_grounded_answer_orchestrator import (
    BoundedGroundedAnswerOrchestrator,
)
from app.research.openai_grounded_answer_generator import (
    OpenAIGroundedAnswerGenerator,
)


def create_bounded_grounded_answer_orchestrator(
    *,
    client: OpenAIClientProtocol,
    model: str,
    citation_evaluator: SemanticCitationEvaluatorProtocol,
) -> BoundedGroundedAnswerOrchestrator:
    """Compose existing generation and Step 8 citation validation adapters."""

    return BoundedGroundedAnswerOrchestrator(
        generator=OpenAIGroundedAnswerGenerator(client=client, model=model),
        citation_verifier=BoundedAnswerCitationVerifier(evaluator=citation_evaluator),
    )
