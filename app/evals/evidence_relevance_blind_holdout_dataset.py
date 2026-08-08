"""Fresh Blind Holdout v1 for semantic evidence relevance."""

from __future__ import annotations

from app.schemas.evidence_relevance_evaluation import (
    EvidenceRelevanceEvaluationCase,
    EvidenceRelevanceEvaluationDataset,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceLevel,
)


def evidence_relevance_blind_holdout_v1() -> (
    EvidenceRelevanceEvaluationDataset
):
    """Return fixed unseen Blind Holdout v1 cases."""

    direct = EvidenceRelevanceLevel.DIRECTLY_RELEVANT
    partial = EvidenceRelevanceLevel.PARTIALLY_RELEVANT
    irrelevant = EvidenceRelevanceLevel.IRRELEVANT

    return EvidenceRelevanceEvaluationDataset(
        dataset_id="evidence-relevance-blind-holdout-v1",
        cases=[
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-direct-001-rate-limit",
                question="How can request bursts be limited?",
                objective=(
                    "Explain a concrete runtime rate-limiting "
                    "enforcement mechanism."
                ),
                evidence=(
                    "Before accepting a request, the gateway checks a "
                    "per-client token bucket and rejects the request when "
                    "no tokens remain."
                ),
                expected_level=direct,
                notes="Direct enforcement mechanism.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-direct-002-human-approval",
                question="How can risky tool actions require approval?",
                objective=(
                    "Explain a preventive human-in-the-loop control."
                ),
                evidence=(
                    "When a tool call is marked high risk, execution is "
                    "paused and the call proceeds only after a human "
                    "reviewer explicitly approves it."
                ),
                expected_level=direct,
                notes="Direct preventive approval control.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-direct-003-timeout",
                question="How can runaway operations be bounded?",
                objective=(
                    "Explain a concrete timeout enforcement mechanism."
                ),
                evidence=(
                    "The runner starts a deadline timer before execution "
                    "and cancels the operation if it has not completed "
                    "when the timeout expires."
                ),
                expected_level=direct,
                notes="Direct timeout enforcement.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-direct-004-secret-redaction",
                question="How can secrets be prevented from reaching logs?",
                objective=(
                    "Explain a preventive redaction mechanism before "
                    "log persistence."
                ),
                evidence=(
                    "Before writing an event, the logger replaces values "
                    "matching configured secret fields with a redacted "
                    "placeholder and persists only the sanitized payload."
                ),
                expected_level=direct,
                notes="Direct preventive redaction.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-direct-005-source-freshness",
                question="How can stale sources be detected?",
                objective=(
                    "Describe a concrete freshness evaluation method."
                ),
                evidence=(
                    "The evaluator compares each source publication time "
                    "with the research cutoff and flags documents older "
                    "than the allowed freshness window."
                ),
                expected_level=direct,
                notes="Direct freshness evaluation method.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-direct-006-specialist-routing",
                question="How can research tasks be routed to specialists?",
                objective=(
                    "Explain a concrete routing decision mechanism."
                ),
                evidence=(
                    "The router compares a task's required capability "
                    "with registered agent capabilities and assigns the "
                    "task only to agents that advertise the required one."
                ),
                expected_level=direct,
                notes="Direct routing decision mechanism.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-partial-001-rate-counter",
                question="How can request bursts be limited?",
                objective=(
                    "Explain a concrete runtime rate-limiting "
                    "enforcement mechanism."
                ),
                evidence=(
                    "The gateway records each client's recent request "
                    "count so current usage can be compared with a "
                    "configured rate limit."
                ),
                expected_level=partial,
                notes="Measurement prerequisite without rejection.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-partial-002-approval-risk-label",
                question="How can risky tool actions require approval?",
                objective=(
                    "Explain a preventive human-in-the-loop control."
                ),
                evidence=(
                    "Each proposed tool action is assigned a risk label "
                    "that downstream policy can use to decide whether "
                    "human review is needed."
                ),
                expected_level=partial,
                notes="Policy input without pause/approval enforcement.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-partial-003-timeout-measurement",
                question="How can runaway operations be bounded?",
                objective=(
                    "Explain a concrete timeout enforcement mechanism."
                ),
                evidence=(
                    "The runtime records operation start time and elapsed "
                    "duration so execution time can be compared with a "
                    "configured timeout."
                ),
                expected_level=partial,
                notes="Timing signal without cancellation.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-partial-004-redaction-detection",
                question="How can secrets be prevented from reaching logs?",
                objective=(
                    "Explain a preventive redaction mechanism before "
                    "log persistence."
                ),
                evidence=(
                    "A detector identifies fields that match known secret "
                    "patterns and marks them as sensitive before logging."
                ),
                expected_level=partial,
                notes="Detection prerequisite without sanitization.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-partial-005-freshness-metadata",
                question="How can stale sources be detected?",
                objective=(
                    "Describe a concrete freshness evaluation method."
                ),
                evidence=(
                    "Each source record stores its publication timestamp "
                    "so later evaluation can reason about source age."
                ),
                expected_level=partial,
                notes="Necessary metadata, not evaluation rule.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-partial-006-routing-capability",
                question="How can research tasks be routed to specialists?",
                objective=(
                    "Explain a concrete routing decision mechanism."
                ),
                evidence=(
                    "Each agent registration includes a list of supported "
                    "capabilities that can be consulted during assignment."
                ),
                expected_level=partial,
                notes="Routing prerequisite, not assignment rule.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-irrelevant-001-rate-dashboard",
                question="How can request bursts be limited?",
                objective=(
                    "Explain a concrete runtime rate-limiting "
                    "enforcement mechanism."
                ),
                evidence=(
                    "A dashboard shows daily request volume by customer "
                    "for capacity planning."
                ),
                expected_level=irrelevant,
                notes="Post-hoc reporting only.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-irrelevant-002-approval-audit",
                question="How can risky tool actions require approval?",
                objective=(
                    "Explain a preventive human-in-the-loop control."
                ),
                evidence=(
                    "After execution, completed tool actions are listed "
                    "in an audit report with the responsible user."
                ),
                expected_level=irrelevant,
                notes="Post-hoc audit, no approval control.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-irrelevant-003-timeout-docs",
                question="How can runaway operations be bounded?",
                objective=(
                    "Explain a concrete timeout enforcement mechanism."
                ),
                evidence=(
                    "The timeout setting is documented in the same "
                    "configuration guide as retry settings."
                ),
                expected_level=irrelevant,
                notes="Documentation location, no mechanism.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-irrelevant-004-redaction-encryption",
                question="How can secrets be prevented from reaching logs?",
                objective=(
                    "Explain a preventive redaction mechanism before "
                    "log persistence."
                ),
                evidence=(
                    "Stored log files are encrypted at rest using the "
                    "platform's standard storage encryption."
                ),
                expected_level=irrelevant,
                notes="Different security control after persistence.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-irrelevant-005-freshness-ranking",
                question="How can stale sources be detected?",
                objective=(
                    "Describe a concrete freshness evaluation method."
                ),
                evidence=(
                    "Search results are ranked by textual similarity to "
                    "the user's query."
                ),
                expected_level=irrelevant,
                notes="Relevance ranking, not freshness.",
            ),
            EvidenceRelevanceEvaluationCase(
                case_id="holdout-irrelevant-006-routing-trace",
                question="How can research tasks be routed to specialists?",
                objective=(
                    "Explain a concrete routing decision mechanism."
                ),
                evidence=(
                    "The system records which agent handled each task so "
                    "operators can review assignment history."
                ),
                expected_level=irrelevant,
                notes="Traceability after assignment, not routing rule.",
            ),
        ],
    )
