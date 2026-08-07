"""Fixed DEV golden dataset for claim relevance evaluation."""

from __future__ import annotations

from app.schemas.claim_relevance_evaluation import (
    ClaimRelevanceEvaluationCase,
    ClaimRelevanceEvaluationDataset,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceLevel,
)


def build_claim_relevance_golden_dataset(
) -> ClaimRelevanceEvaluationDataset:
    """Build the fixed v1 DEV claim relevance golden dataset."""

    return ClaimRelevanceEvaluationDataset(
        dataset_id="claim-relevance-golden-v1",
        version="1.0.0",
        cases=[
            # -------------------------------------------------
            # Directly relevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="direct-001-core-mechanism",
                question=(
                    "How does the Agents SDK support tool calling?"
                ),
                objective=(
                    "Explain mechanisms for defining, invoking, "
                    "and orchestrating tools."
                ),
                claim=(
                    "Python functions can be exposed as tools by "
                    "using their signatures and docstrings."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly answers the tool-definition mechanism."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="direct-002-subquestion",
                question=(
                    "What safety mechanisms should an AI agent use "
                    "before executing sensitive actions?"
                ),
                objective=(
                    "Explain concrete controls that prevent unsafe "
                    "or unauthorized actions."
                ),
                claim=(
                    "A human approval step can require confirmation "
                    "before a sensitive action is executed."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Answers one important requested safety control."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="direct-003-constraint",
                question=(
                    "How can an agent keep external API spending bounded?"
                ),
                objective=(
                    "Identify execution controls for limiting API cost."
                ),
                claim=(
                    "The runner can stop additional provider calls "
                    "after a configured call budget is exhausted."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly supplies a requested bounded-execution control."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="direct-004-comparison-axis",
                question=(
                    "What is the difference between retrieval and memory "
                    "in an agent system?"
                ),
                objective=(
                    "Contrast their roles in supplying information "
                    "to the agent."
                ),
                claim=(
                    "Retrieval fetches information relevant to the "
                    "current query, while memory preserves information "
                    "from prior interactions for later reuse."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly states the requested conceptual distinction."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="direct-005-failure-mode",
                question=(
                    "Why can an agent enter an infinite tool loop?"
                ),
                objective=(
                    "Explain mechanisms that cause repeated tool execution."
                ),
                claim=(
                    "If the stopping condition is never satisfied, "
                    "the model can repeatedly request another tool call."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly explains a requested loop mechanism."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="direct-006-narrow-but-core",
                question=(
                    "How should an agent record execution traces for debugging?"
                ),
                objective=(
                    "Describe what trace information is useful for "
                    "understanding execution."
                ),
                claim=(
                    "Recording tool names, inputs, outputs, and timestamps "
                    "makes individual execution steps inspectable."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Narrow claim directly answers a core part of the request."
                ),
            ),

            # -------------------------------------------------
            # Partially relevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="partial-001-use-case-example",
                question=(
                    "How does the Agents SDK support tool calling?"
                ),
                objective=(
                    "Explain mechanisms for defining, invoking, "
                    "and orchestrating tools."
                ),
                claim=(
                    "A support agent can inspect a request, call an internal "
                    "system, request a refund approval, and record the result."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Useful use case but does not explain the mechanisms."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="partial-002-background",
                question=(
                    "How can an agent keep external API spending bounded?"
                ),
                objective=(
                    "Identify execution controls for limiting API cost."
                ),
                claim=(
                    "External APIs often charge by request volume "
                    "or consumed tokens."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Relevant motivation, not itself a control mechanism."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="partial-003-adjacent-control",
                question=(
                    "What safety mechanisms should an AI agent use "
                    "before executing sensitive actions?"
                ),
                objective=(
                    "Explain concrete controls that prevent unsafe "
                    "or unauthorized actions."
                ),
                claim=(
                    "Detailed audit logs make it easier to investigate "
                    "sensitive actions after execution."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Relevant safety control, but mainly retrospective."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="partial-004-related-layer",
                question=(
                    "What is the difference between retrieval and memory "
                    "in an agent system?"
                ),
                objective=(
                    "Contrast their roles in supplying information "
                    "to the agent."
                ),
                claim=(
                    "Both retrieval and memory can contribute text that "
                    "is placed into the model context."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Relevant commonality without providing the distinction."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="partial-005-mitigation-not-cause",
                question=(
                    "Why can an agent enter an infinite tool loop?"
                ),
                objective=(
                    "Explain mechanisms that cause repeated tool execution."
                ),
                claim=(
                    "A maximum-step limit can terminate an agent that "
                    "has made too many tool calls."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Relevant mitigation but does not explain the cause."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="partial-006-benefit-not-method",
                question=(
                    "How should an agent record execution traces for debugging?"
                ),
                objective=(
                    "Describe what trace information is useful for "
                    "understanding execution."
                ),
                claim=(
                    "Tracing can reduce the time required to diagnose "
                    "unexpected agent behavior."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Relevant benefit without explaining what to record."
                ),
            ),

            # -------------------------------------------------
            # Irrelevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="irrelevant-001-product-positioning",
                question=(
                    "How does the Agents SDK support tool calling?"
                ),
                objective=(
                    "Explain mechanisms for defining, invoking, "
                    "and orchestrating tools."
                ),
                claim=(
                    "The Agents SDK is suitable for conversational "
                    "and transactional agent workflows."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Same product, but no substantive answer about tools."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="irrelevant-002-same-domain",
                question=(
                    "How can an agent keep external API spending bounded?"
                ),
                objective=(
                    "Identify execution controls for limiting API cost."
                ),
                claim=(
                    "Agent applications can expose a web interface "
                    "for users to submit tasks."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Agent-domain statement unrelated to cost controls."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="irrelevant-003-different-safety-topic",
                question=(
                    "What safety mechanisms should an AI agent use "
                    "before executing sensitive actions?"
                ),
                objective=(
                    "Explain concrete controls that prevent unsafe "
                    "or unauthorized actions."
                ),
                claim=(
                    "Vector databases can retrieve semantically similar "
                    "documents for a model."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Technically related to AI systems but not action safety."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="irrelevant-004-memory-detail",
                question=(
                    "What is the difference between retrieval and memory "
                    "in an agent system?"
                ),
                objective=(
                    "Contrast their roles in supplying information "
                    "to the agent."
                ),
                claim=(
                    "A tool schema may describe a function name "
                    "and its input parameters."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Agent mechanism unrelated to retrieval-memory distinction."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="irrelevant-005-loop-adjacent",
                question=(
                    "Why can an agent enter an infinite tool loop?"
                ),
                objective=(
                    "Explain mechanisms that cause repeated tool execution."
                ),
                claim=(
                    "A model response can contain natural-language text "
                    "for display to a user."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Same execution context but unrelated to repeated calls."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="irrelevant-006-debugging-adjacent",
                question=(
                    "How should an agent record execution traces for debugging?"
                ),
                objective=(
                    "Describe what trace information is useful for "
                    "understanding execution."
                ),
                claim=(
                    "A deployment can run inside a containerized environment."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Engineering context unrelated to trace contents."
                ),
            ),
        ],
    )
