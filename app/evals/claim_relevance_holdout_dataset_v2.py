"""Fresh blind holdout v2 for claim relevance evaluation.

IMPORTANT:
- Created only after Prompt v2.1 was frozen.
- Do not use this dataset to tune Prompt v2.1.
- If Prompt v2.1 is changed after seeing these results, this dataset must no
  longer be treated as blind for that revised prompt.
"""

from __future__ import annotations

from app.schemas.claim_relevance_evaluation import (
    ClaimRelevanceEvaluationCase,
    ClaimRelevanceEvaluationDataset,
)
from app.schemas.claim_relevance_judgment import ClaimRelevanceLevel


def build_claim_relevance_holdout_dataset_v2(
) -> ClaimRelevanceEvaluationDataset:
    """Build the fixed unseen v2 holdout dataset."""

    return ClaimRelevanceEvaluationDataset(
        dataset_id="claim-relevance-holdout-v2",
        version="2.0.0",
        cases=[
            # -------------------------------------------------
            # Directly relevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-direct-001-secret-redaction",
                question=(
                    "How can an agent avoid sending secrets to an external "
                    "model provider?"
                ),
                objective=(
                    "Describe a preventive data-handling control before "
                    "the model request is sent."
                ),
                claim=(
                    "A request filter can detect configured secret patterns "
                    "and redact them before the payload leaves the system."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct preventive redaction control.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-direct-002-tool-result-validation",
                question=(
                    "How can an agent keep malformed tool output from "
                    "corrupting later steps?"
                ),
                objective=(
                    "Explain a concrete validation mechanism at the tool "
                    "result boundary."
                ),
                claim=(
                    "The runtime can validate each tool result against an "
                    "expected schema before adding it to execution state."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct boundary validation mechanism.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-direct-003-human-approval",
                question=(
                    "How can an agent require human approval before a "
                    "high-impact action?"
                ),
                objective=(
                    "Describe a concrete execution control that pauses "
                    "until approval is received."
                ),
                claim=(
                    "The workflow can enter a pending-approval state and "
                    "resume the action only after an authorized reviewer "
                    "approves it."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct approval-gated execution control.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-direct-004-timeout",
                question=(
                    "How can an agent stop a slow external tool from "
                    "blocking a run indefinitely?"
                ),
                objective=(
                    "Give a concrete runtime time-bound control."
                ),
                claim=(
                    "The tool executor can cancel the call when a configured "
                    "timeout expires and return a timeout outcome to the run."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct timeout control.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-direct-005-routing",
                question=(
                    "How can a multi-agent system choose which specialist "
                    "should handle a request?"
                ),
                objective=(
                    "Explain a concrete routing mechanism based on the "
                    "request."
                ),
                claim=(
                    "A router can classify the request against specialist "
                    "capabilities and select the best-matching agent."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct specialist routing mechanism.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-direct-006-stale-source",
                question=(
                    "How can a research agent reduce the risk of citing "
                    "outdated information?"
                ),
                objective=(
                    "Describe a concrete freshness check used when selecting "
                    "sources."
                ),
                claim=(
                    "The source selector can compare publication or update "
                    "dates against a freshness requirement before accepting "
                    "a source."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct source-freshness selection control.",
            ),

            # -------------------------------------------------
            # Partially relevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-partial-001-secret-inventory",
                question=(
                    "How can an agent avoid sending secrets to an external "
                    "model provider?"
                ),
                objective=(
                    "Describe a preventive data-handling control before "
                    "the model request is sent."
                ),
                claim=(
                    "Maintaining an inventory of secret types and sensitive "
                    "fields gives the system a basis for deciding what data "
                    "requires protection."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Material prerequisite for protection, but not the "
                    "pre-send control itself."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-partial-002-schema-definition",
                question=(
                    "How can an agent keep malformed tool output from "
                    "corrupting later steps?"
                ),
                objective=(
                    "Explain a concrete validation mechanism at the tool "
                    "result boundary."
                ),
                claim=(
                    "A tool contract can define the fields and types that "
                    "a valid result is expected to contain."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Defines the validation target but not the boundary "
                    "validation action."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-partial-003-approver-identity",
                question=(
                    "How can an agent require human approval before a "
                    "high-impact action?"
                ),
                objective=(
                    "Describe a concrete execution control that pauses "
                    "until approval is received."
                ),
                claim=(
                    "The system needs a reliable way to identify which "
                    "reviewers are authorized to approve high-impact actions."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Necessary approval prerequisite without pause/resume "
                    "control."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-partial-004-latency-measurement",
                question=(
                    "How can an agent stop a slow external tool from "
                    "blocking a run indefinitely?"
                ),
                objective=(
                    "Give a concrete runtime time-bound control."
                ),
                claim=(
                    "Recording tool-call duration makes it possible to "
                    "observe which integrations regularly exceed expected "
                    "latency."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Useful timing signal, but does not itself stop a call."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-partial-005-capability-catalog",
                question=(
                    "How can a multi-agent system choose which specialist "
                    "should handle a request?"
                ),
                objective=(
                    "Explain a concrete routing mechanism based on the "
                    "request."
                ),
                claim=(
                    "A capability catalog can describe the kinds of tasks "
                    "each specialist is designed to handle."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Material routing input without the selection mechanism."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-partial-006-source-date-metadata",
                question=(
                    "How can a research agent reduce the risk of citing "
                    "outdated information?"
                ),
                objective=(
                    "Describe a concrete freshness check used when selecting "
                    "sources."
                ),
                claim=(
                    "Source records can retain publication and last-updated "
                    "dates when those dates are available."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Provides freshness metadata but not the acceptance check."
                ),
            ),

            # -------------------------------------------------
            # Irrelevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-irrelevant-001-secret-audit",
                question=(
                    "How can an agent avoid sending secrets to an external "
                    "model provider?"
                ),
                objective=(
                    "Describe a preventive data-handling control before "
                    "the model request is sent."
                ),
                claim=(
                    "A billing report can show how many model requests were "
                    "sent to each provider during the month."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Provider reporting unrelated to secret prevention.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-irrelevant-002-tool-label",
                question=(
                    "How can an agent keep malformed tool output from "
                    "corrupting later steps?"
                ),
                objective=(
                    "Explain a concrete validation mechanism at the tool "
                    "result boundary."
                ),
                claim=(
                    "A tool can have a human-readable display name and icon "
                    "in an administration interface."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Presentation metadata unrelated to validation.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-irrelevant-003-approval-notification-theme",
                question=(
                    "How can an agent require human approval before a "
                    "high-impact action?"
                ),
                objective=(
                    "Describe a concrete execution control that pauses "
                    "until approval is received."
                ),
                claim=(
                    "Approval notifications can use a consistent visual theme "
                    "across desktop and mobile clients."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="UI styling unrelated to approval gating.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-irrelevant-004-timeout-docs",
                question=(
                    "How can an agent stop a slow external tool from "
                    "blocking a run indefinitely?"
                ),
                objective=(
                    "Give a concrete runtime time-bound control."
                ),
                claim=(
                    "Tool documentation can include examples showing how "
                    "developers invoke the integration."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Developer documentation unrelated to time bounds.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-irrelevant-005-agent-avatar",
                question=(
                    "How can a multi-agent system choose which specialist "
                    "should handle a request?"
                ),
                objective=(
                    "Explain a concrete routing mechanism based on the "
                    "request."
                ),
                claim=(
                    "Each specialist can use a different avatar in the "
                    "user interface."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Presentation detail unrelated to routing.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="holdout-v2-irrelevant-006-source-layout",
                question=(
                    "How can a research agent reduce the risk of citing "
                    "outdated information?"
                ),
                objective=(
                    "Describe a concrete freshness check used when selecting "
                    "sources."
                ),
                claim=(
                    "A report can place source titles in a two-column "
                    "bibliography layout."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Report layout unrelated to source freshness.",
            ),
        ],
    )
