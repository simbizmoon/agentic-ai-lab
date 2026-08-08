"""Golden DEV v1 dataset for semantic evidence relevance."""

from __future__ import annotations

from app.schemas.evidence_relevance_evaluation import (
    EvidenceRelevanceEvaluationCase,
    EvidenceRelevanceEvaluationDataset,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceLevel,
)


def evidence_relevance_golden_dev_v1() -> (
    EvidenceRelevanceEvaluationDataset
):
    """Return balanced Golden DEV v1 cases."""

    direct = EvidenceRelevanceLevel.DIRECTLY_RELEVANT
    partial = EvidenceRelevanceLevel.PARTIALLY_RELEVANT
    irrelevant = EvidenceRelevanceLevel.IRRELEVANT

    return EvidenceRelevanceEvaluationDataset(
        dataset_id="evidence-relevance-golden-dev-v1",
        cases=[
            EvidenceRelevanceEvaluationCase(
                case_id="direct-001-tool-mechanism",
                question="How does an agent use function tools?",
                objective=(
                    "Explain how callable functions are exposed "
                    "and invoked during execution."
                ),
                evidence=(
                    "A function tool gives the agent a named function "
                    "with an input schema, and the runtime executes the "
                    "selected function when the model emits a tool call."
                ),
                expected_level=direct,
                notes="Direct mechanism evidence.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="direct-002-retry-cause",
                question="Why do repeated retries amplify outages?",
                objective=(
                    "Identify the causal mechanism by which retries "
                    "increase load during failure."
                ),
                evidence=(
                    "When many clients immediately retry failed requests, "
                    "each original failure creates additional requests, "
                    "raising load on an already degraded service."
                ),
                expected_level=direct,
                notes="Direct causal explanation.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="direct-003-access-control",
                question="How can tool execution be restricted?",
                objective=(
                    "Explain a preventive authorization mechanism."
                ),
                evidence=(
                    "Before execution, the runtime checks whether the "
                    "requested tool is in the caller's allowed-tool set "
                    "and rejects calls that are not authorized."
                ),
                expected_level=direct,
                notes="Direct preventive control evidence.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="direct-004-comparison",
                question="How do polling and webhooks differ?",
                objective=(
                    "Explain the operational distinction between "
                    "the two delivery mechanisms."
                ),
                evidence=(
                    "Polling requires the client to repeatedly ask for "
                    "updates, while a webhook sends an HTTP callback when "
                    "an event occurs."
                ),
                expected_level=direct,
                notes="Direct comparison.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="direct-005-evaluation",
                question="How should retrieval quality be evaluated?",
                objective=(
                    "Describe a concrete metric for ranked retrieval."
                ),
                evidence=(
                    "Mean reciprocal rank measures how high the first "
                    "relevant result appears by averaging the reciprocal "
                    "of its rank across queries."
                ),
                expected_level=direct,
                notes="Direct evaluation method.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="direct-006-cost-control",
                question="How can model spending be bounded?",
                objective=(
                    "Explain a concrete runtime usage control."
                ),
                evidence=(
                    "The runner checks the cumulative token budget before "
                    "starting another model call and stops new calls once "
                    "the configured ceiling is reached."
                ),
                expected_level=direct,
                notes="Direct bounded-execution mechanism.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="partial-001-tool-definition",
                question="How does an agent use function tools?",
                objective=(
                    "Explain how callable functions are exposed "
                    "and invoked during execution."
                ),
                evidence=(
                    "A tool definition provides a function name, "
                    "description, and input schema to the agent, but this "
                    "passage does not describe runtime invocation."
                ),
                expected_level=partial,
                notes="Availability without execution.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="partial-002-retry-backoff",
                question="Why do repeated retries amplify outages?",
                objective=(
                    "Identify the causal mechanism by which retries "
                    "increase load during failure."
                ),
                evidence=(
                    "Exponential backoff spaces retry attempts farther "
                    "apart after repeated failures, reducing how quickly "
                    "new retry traffic is generated."
                ),
                expected_level=partial,
                notes="Mitigation illuminates mechanism but is not cause.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="partial-003-auth-prerequisite",
                question="How can tool execution be restricted?",
                objective=(
                    "Explain a preventive authorization mechanism."
                ),
                evidence=(
                    "Each tool call carries the identity of the requesting "
                    "principal so authorization policy can be evaluated."
                ),
                expected_level=partial,
                notes="Necessary input to control, not the control itself.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="partial-004-comparison-baseline",
                question="How do polling and webhooks differ?",
                objective=(
                    "Explain the operational distinction between "
                    "the two delivery mechanisms."
                ),
                evidence=(
                    "Both polling and webhooks are mechanisms for learning "
                    "about changes in a remote system."
                ),
                expected_level=partial,
                notes="Meaningful comparison baseline only.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="partial-005-evaluation-signal",
                question="How should retrieval quality be evaluated?",
                objective=(
                    "Describe a concrete metric for ranked retrieval."
                ),
                evidence=(
                    "The evaluation dataset records which documents are "
                    "relevant for each query so ranking metrics can compare "
                    "retrieved results against expected relevance."
                ),
                expected_level=partial,
                notes="Prerequisite signal, not metric.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="partial-006-cost-observability",
                question="How can model spending be bounded?",
                objective=(
                    "Explain a concrete runtime usage control."
                ),
                evidence=(
                    "The runtime records token usage after every model "
                    "call so cumulative consumption can be compared with "
                    "a configured budget."
                ),
                expected_level=partial,
                notes="Measurement prerequisite, not stopping control.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="irrelevant-001-tool-positioning",
                question="How does an agent use function tools?",
                objective=(
                    "Explain how callable functions are exposed "
                    "and invoked during execution."
                ),
                evidence=(
                    "The SDK can manage the agent loop on behalf of "
                    "the application."
                ),
                expected_level=irrelevant,
                notes="Same product, different capability.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="irrelevant-002-retry-logging",
                question="Why do repeated retries amplify outages?",
                objective=(
                    "Identify the causal mechanism by which retries "
                    "increase load during failure."
                ),
                evidence=(
                    "The service writes retry counts and timestamps to "
                    "an operational log for later analysis."
                ),
                expected_level=irrelevant,
                notes="Observability, not causal mechanism.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="irrelevant-003-access-audit",
                question="How can tool execution be restricted?",
                objective=(
                    "Explain a preventive authorization mechanism."
                ),
                evidence=(
                    "After execution, every tool call is written to an "
                    "audit trail with its arguments and result."
                ),
                expected_level=irrelevant,
                notes="Post-hoc audit, not prevention.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="irrelevant-004-comparison-shared-brand",
                question="How do polling and webhooks differ?",
                objective=(
                    "Explain the operational distinction between "
                    "the two delivery mechanisms."
                ),
                evidence=(
                    "Both features are documented in the same developer "
                    "portal and use the platform's authentication system."
                ),
                expected_level=irrelevant,
                notes="Same domain only, no meaningful baseline.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="irrelevant-005-evaluation-storage",
                question="How should retrieval quality be evaluated?",
                objective=(
                    "Describe a concrete metric for ranked retrieval."
                ),
                evidence=(
                    "Evaluation runs are saved with timestamps so teams "
                    "can review historical experiments."
                ),
                expected_level=irrelevant,
                notes="Storage, not evaluation method.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="irrelevant-006-cost-dashboard",
                question="How can model spending be bounded?",
                objective=(
                    "Explain a concrete runtime usage control."
                ),
                evidence=(
                    "A dashboard displays monthly model spending by team "
                    "after usage records have been aggregated."
                ),
                expected_level=irrelevant,
                notes="Reporting, not runtime control.",
            ),
        ],
    )
