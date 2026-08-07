"""Fresh v2 DEV dataset for claim relevance evaluation."""

from __future__ import annotations

from app.schemas.claim_relevance_evaluation import (
    ClaimRelevanceEvaluationCase,
    ClaimRelevanceEvaluationDataset,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceLevel,
)


def build_claim_relevance_golden_dataset_v2(
) -> ClaimRelevanceEvaluationDataset:
    """Build the fresh v2 DEV claim relevance dataset."""

    return ClaimRelevanceEvaluationDataset(
        dataset_id="claim-relevance-golden-v2",
        version="2.0.0",
        cases=[
            # -------------------------------------------------
            # Directly relevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="v2-direct-001-checkpoint",
                question=(
                    "How can an agent recover its workflow after a crash?"
                ),
                objective=(
                    "Describe a concrete checkpoint and restoration method."
                ),
                claim=(
                    "The runtime can persist a checkpoint after each completed "
                    "step and reload the latest checkpoint after restart."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct checkpoint-and-restore method.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-direct-002-permission",
                question=(
                    "How can an agent prevent unauthorized database writes?"
                ),
                objective=(
                    "Explain a preventive authorization control."
                ),
                claim=(
                    "Before a write tool runs, an authorization policy can "
                    "check whether the caller has permission for that operation."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct preventive authorization control.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-direct-003-comparison",
                question=(
                    "How do deterministic rules differ from model-based "
                    "judgments in an agent pipeline?"
                ),
                objective=(
                    "Contrast their roles in making execution decisions."
                ),
                claim=(
                    "Deterministic rules produce fixed outcomes from explicit "
                    "conditions, while model-based judgments interpret "
                    "semantic context probabilistically."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Directly provides the requested contrast.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-direct-004-cost-cap",
                question=(
                    "How can a research agent avoid unlimited model spending?"
                ),
                objective=(
                    "Give a concrete runtime mechanism that bounds usage."
                ),
                claim=(
                    "The executor can stop launching new model calls when "
                    "its cumulative token budget reaches a configured limit."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct bounded-usage mechanism.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-direct-005-source-anchor",
                question=(
                    "How can citations remain traceable after a document "
                    "is split into evidence excerpts?"
                ),
                objective=(
                    "Describe provenance fields that preserve source linkage."
                ),
                claim=(
                    "Each excerpt can store its document identifier together "
                    "with exact character offsets into the original document."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct provenance-linkage mechanism.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-direct-006-loop-cause",
                question=(
                    "What can cause an agent to repeatedly call the same tool?"
                ),
                objective=(
                    "Explain a concrete execution-state cause of repetition."
                ),
                claim=(
                    "If the tool result is never written back into the state "
                    "used by the next model step, the model may keep requesting "
                    "the same action."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT
                ),
                description="Direct state-related cause.",
            ),

            # -------------------------------------------------
            # Partially relevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="v2-partial-001-storage-prerequisite",
                question=(
                    "How can an agent recover its workflow after a crash?"
                ),
                objective=(
                    "Describe a concrete checkpoint and restoration method."
                ),
                claim=(
                    "Durable storage is needed if workflow state must survive "
                    "the lifetime of a single process."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description="Necessary prerequisite without restore procedure.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-partial-002-auth-prerequisite",
                question=(
                    "How can an agent prevent unauthorized database writes?"
                ),
                objective=(
                    "Explain a preventive authorization control."
                ),
                claim=(
                    "A reliable caller identity is required before an "
                    "authorization policy can decide whether a database "
                    "write should be permitted."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Material prerequisite for authorization, but not "
                    "the control itself."
                ),
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-partial-003-commonality",
                question=(
                    "How do deterministic rules differ from model-based "
                    "judgments in an agent pipeline?"
                ),
                objective=(
                    "Contrast their roles in making execution decisions."
                ),
                claim=(
                    "Both deterministic rules and model-based judgments can "
                    "influence which action the pipeline takes next."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description="Relevant commonality without the requested contrast.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-partial-004-cost-observability",
                question=(
                    "How can a research agent avoid unlimited model spending?"
                ),
                objective=(
                    "Give a concrete runtime mechanism that bounds usage."
                ),
                claim=(
                    "Recording token consumption for each model call makes "
                    "usage trends visible."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description="Useful observability, but not a bounding mechanism.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-partial-005-bibliography",
                question=(
                    "How can citations remain traceable after a document "
                    "is split into evidence excerpts?"
                ),
                objective=(
                    "Describe provenance fields that preserve source linkage."
                ),
                claim=(
                    "The final report can include a bibliography containing "
                    "the titles and URLs of all consulted documents."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description="Source reporting without excerpt-level linkage.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-partial-006-state-link",
                question=(
                    "What can cause an agent to repeatedly call the same tool?"
                ),
                objective=(
                    "Explain a concrete execution-state cause of repetition."
                ),
                claim=(
                    "Whether the model repeats a tool call can depend on "
                    "which prior tool results are present in the execution "
                    "state."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT
                ),
                description=(
                    "Directly links repetition to execution state, but does "
                    "not identify a concrete faulty state condition."
                ),
            ),

            # -------------------------------------------------
            # Irrelevant
            # -------------------------------------------------
            ClaimRelevanceEvaluationCase(
                case_id="v2-irrelevant-001-dashboard",
                question=(
                    "How can an agent recover its workflow after a crash?"
                ),
                objective=(
                    "Describe a concrete checkpoint and restoration method."
                ),
                claim=(
                    "A web dashboard can show whether an agent is currently "
                    "running, idle, or stopped."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Status UI without crash recovery.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-irrelevant-002-posthoc-audit",
                question=(
                    "How can an agent prevent unauthorized database writes?"
                ),
                objective=(
                    "Explain a preventive authorization control."
                ),
                claim=(
                    "An audit log can record which database writes occurred "
                    "so that administrators can review them later."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Post-hoc audit does not prevent writes.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-irrelevant-003-serialization",
                question=(
                    "How do deterministic rules differ from model-based "
                    "judgments in an agent pipeline?"
                ),
                objective=(
                    "Contrast their roles in making execution decisions."
                ),
                claim=(
                    "Pipeline configuration can be serialized as JSON."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Pipeline detail unrelated to comparison.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-irrelevant-004-versioning",
                question=(
                    "How can a research agent avoid unlimited model spending?"
                ),
                objective=(
                    "Give a concrete runtime mechanism that bounds usage."
                ),
                claim=(
                    "Prompt templates can be versioned in a source-control "
                    "repository."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Change management unrelated to spending bounds.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-irrelevant-005-cleaning",
                question=(
                    "How can citations remain traceable after a document "
                    "is split into evidence excerpts?"
                ),
                objective=(
                    "Describe provenance fields that preserve source linkage."
                ),
                claim=(
                    "HTML cleaning can remove menus and repeated navigation "
                    "text before analysis."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Document cleaning unrelated to provenance linkage.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="v2-irrelevant-006-tool-schema",
                question=(
                    "What can cause an agent to repeatedly call the same tool?"
                ),
                objective=(
                    "Explain a concrete execution-state cause of repetition."
                ),
                claim=(
                    "A tool schema can describe the arguments accepted by "
                    "a function."
                ),
                expected_relevance_level=(
                    ClaimRelevanceLevel.IRRELEVANT
                ),
                description="Tool metadata unrelated to repeated calls.",
            ),
        ],
    )
