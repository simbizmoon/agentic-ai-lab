"""Blind holdout dataset for claim relevance evaluation."""

from __future__ import annotations

from app.schemas.claim_relevance_evaluation import (
    ClaimRelevanceEvaluationCase,
    ClaimRelevanceEvaluationDataset,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceLevel,
)


def build_claim_relevance_holdout_dataset(
) -> ClaimRelevanceEvaluationDataset:
    """Build the fixed blind v1 claim relevance holdout dataset."""

    return ClaimRelevanceEvaluationDataset(
        dataset_id="claim-relevance-holdout-v1",
        version="1.0.0",
        cases=[
            # -------------------------------------------------
            # Directly relevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="holdout-direct-001-state-persistence",
                question=(
                    "How can a long-running agent resume work after "
                    "a process restart?"
                ),
                objective=(
                    "Explain mechanisms for preserving and restoring "
                    "execution state."
                ),
                claim=(
                    "Persisting the agent's state and step history allows "
                    "a new process to reconstruct where execution stopped."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly explains a persistence-and-resume mechanism."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-direct-002-tool-authorization",
                question=(
                    "How should an agent restrict access to privileged tools?"
                ),
                objective=(
                    "Identify controls that prevent unauthorized tool use."
                ),
                claim=(
                    "A policy check can verify the current principal and "
                    "requested action before a privileged tool is exposed "
                    "or executed."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly supplies an authorization control."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-direct-003-retry-bound",
                question=(
                    "How can an agent recover from transient API failures "
                    "without retrying forever?"
                ),
                objective=(
                    "Describe bounded retry behavior for transient failures."
                ),
                claim=(
                    "A retry policy can cap attempts and apply backoff "
                    "between retries."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly answers the bounded-retry mechanism."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-direct-004-eval-regression",
                question=(
                    "How can an agent team detect that a prompt change "
                    "made behavior worse?"
                ),
                objective=(
                    "Explain an evaluation method for detecting regressions."
                ),
                claim=(
                    "Running the old and new prompt against a fixed "
                    "evaluation dataset allows their results to be compared."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly gives the requested regression-evaluation method."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-direct-005-source-provenance",
                question=(
                    "How should a research agent make a factual answer "
                    "traceable to its sources?"
                ),
                objective=(
                    "Describe provenance needed to connect answer claims "
                    "back to source material."
                ),
                claim=(
                    "Each claim can retain citations that identify the "
                    "evidence record and the source document from which "
                    "that evidence was extracted."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly supplies a claim-to-source provenance mechanism."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-direct-006-multi-agent-handoff",
                question=(
                    "What mechanism lets one specialized agent delegate "
                    "work to another specialized agent?"
                ),
                objective=(
                    "Explain a concrete delegation mechanism between agents."
                ),
                claim=(
                    "A handoff can transfer control and relevant context "
                    "from the current agent to another agent."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description=(
                    "Directly names and explains a delegation mechanism."
                ),
            ),

            # -------------------------------------------------
            # Partially relevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="holdout-partial-001-benefit-not-resume",
                question=(
                    "How can a long-running agent resume work after "
                    "a process restart?"
                ),
                objective=(
                    "Explain mechanisms for preserving and restoring "
                    "execution state."
                ),
                claim=(
                    "Persistent state can make long-running workflows "
                    "more reliable."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Relevant benefit, but no preservation/restoration method."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-partial-002-audit-not-auth",
                question=(
                    "How should an agent restrict access to privileged tools?"
                ),
                objective=(
                    "Identify controls that prevent unauthorized tool use."
                ),
                claim=(
                    "Recording every privileged tool call helps investigators "
                    "review what happened later."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Security-relevant audit control, but not access restriction."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-partial-003-retry-cause-not-policy",
                question=(
                    "How can an agent recover from transient API failures "
                    "without retrying forever?"
                ),
                objective=(
                    "Describe bounded retry behavior for transient failures."
                ),
                claim=(
                    "Temporary network errors can cause otherwise valid "
                    "API requests to fail."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Relevant failure context, but not bounded recovery behavior."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-partial-004-monitoring-not-eval",
                question=(
                    "How can an agent team detect that a prompt change "
                    "made behavior worse?"
                ),
                objective=(
                    "Explain an evaluation method for detecting regressions."
                ),
                claim=(
                    "Production monitoring can reveal increases in errors "
                    "after a new version is deployed."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Related regression signal, but not the requested eval method."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-partial-005-source-list-not-provenance",
                question=(
                    "How should a research agent make a factual answer "
                    "traceable to its sources?"
                ),
                objective=(
                    "Describe provenance needed to connect answer claims "
                    "back to source material."
                ),
                claim=(
                    "A report can include a list of source URLs at the end."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Related source reporting, but does not connect claims "
                    "to specific evidence."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-partial-006-team-benefit-not-handoff",
                question=(
                    "What mechanism lets one specialized agent delegate "
                    "work to another specialized agent?"
                ),
                objective=(
                    "Explain a concrete delegation mechanism between agents."
                ),
                claim=(
                    "Using multiple specialized agents can separate "
                    "responsibilities across a workflow."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Relevant motivation/architecture, but no delegation mechanism."
                ),
            ),

            # -------------------------------------------------
            # Irrelevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="holdout-irrelevant-001-ui-after-restart",
                question=(
                    "How can a long-running agent resume work after "
                    "a process restart?"
                ),
                objective=(
                    "Explain mechanisms for preserving and restoring "
                    "execution state."
                ),
                claim=(
                    "A dashboard can display the agent's current status "
                    "to a user."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Operational UI detail unrelated to persistence/restoration."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-irrelevant-002-tool-description",
                question=(
                    "How should an agent restrict access to privileged tools?"
                ),
                objective=(
                    "Identify controls that prevent unauthorized tool use."
                ),
                claim=(
                    "A tool description can explain what a function does "
                    "and what parameters it accepts."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Tool-related statement without authorization control."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-irrelevant-003-model-temperature",
                question=(
                    "How can an agent recover from transient API failures "
                    "without retrying forever?"
                ),
                objective=(
                    "Describe bounded retry behavior for transient failures."
                ),
                claim=(
                    "Sampling settings can influence how varied a model's "
                    "generated text is."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Model-generation detail unrelated to failure recovery."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-irrelevant-004-prompt-storage",
                question=(
                    "How can an agent team detect that a prompt change "
                    "made behavior worse?"
                ),
                objective=(
                    "Explain an evaluation method for detecting regressions."
                ),
                claim=(
                    "Prompt files can be stored in a version-control repository."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Change-management detail without regression evaluation."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-irrelevant-005-source-css",
                question=(
                    "How should a research agent make a factual answer "
                    "traceable to its sources?"
                ),
                objective=(
                    "Describe provenance needed to connect answer claims "
                    "back to source material."
                ),
                claim=(
                    "A web reader may remove navigation menus and styling "
                    "before extracting article text."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Research-pipeline detail unrelated to answer provenance."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-irrelevant-006-agent-avatar",
                question=(
                    "What mechanism lets one specialized agent delegate "
                    "work to another specialized agent?"
                ),
                objective=(
                    "Explain a concrete delegation mechanism between agents."
                ),
                claim=(
                    "Different agents can be given distinct names "
                    "and user-facing descriptions."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description=(
                    "Multi-agent presentation detail without delegation."
                ),
            ),
        ],
    )
