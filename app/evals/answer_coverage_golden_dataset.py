"""Development dataset for semantic answer coverage evaluation."""

from __future__ import annotations

from app.evals.answer_coverage_evaluation import (
    AnswerCoverageEvaluationCase,
    AnswerCoverageEvaluationDataset,
)
from app.schemas.answer_coverage_judgment import AnswerCoverageLevel


def build_answer_coverage_golden_dataset() -> AnswerCoverageEvaluationDataset:
    """Return the balanced 18-case development dataset."""

    return AnswerCoverageEvaluationDataset(
        dataset_id="answer-coverage-golden-v2",
        version="2.0.0",
        cases=[
            # -----------------------------------------------------------------
            # FULLY_COVERED (6)
            # -----------------------------------------------------------------
            AnswerCoverageEvaluationCase(
                case_id="mechanism-budget-full",
                question="How does a system enforce an execution budget?",
                objective=(
                    "Explain how usage is measured, compared with limits, "
                    "and used to stop later execution."
                ),
                claims=[
                    "The system records cumulative usage after each operation.",
                    "Before another operation begins, cumulative usage is compared with the configured execution limit.",
                    "When the limit is exhausted, the system prevents additional operations from starting.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="comparison-retrieval-full",
                question="How do keyword retrieval and embedding retrieval differ?",
                objective=(
                    "Compare the matching signal used by each approach "
                    "and explain the practical tradeoff."
                ),
                claims=[
                    "Keyword retrieval ranks passages using lexical term overlap.",
                    "Embedding retrieval ranks passages using vector-space semantic similarity.",
                    "Keyword matching favors exact wording, while embeddings can recover semantically similar wording that uses different terms.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="access-control-full",
                question="How can an agent restrict a tool to authorized users?",
                objective=(
                    "Explain the authorization input, the decision point, "
                    "and the action taken when access is denied."
                ),
                claims=[
                    "The tool call receives the caller identity and applicable authorization policy as inputs.",
                    "Before invocation, the authorization layer evaluates whether the caller is permitted to use the tool.",
                    "If authorization fails, the tool invocation is blocked and an access-denied result is returned.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="evaluation-method-full",
                question="How should retrieval quality be evaluated?",
                objective=(
                    "Describe the reference data, the comparison performed, "
                    "and the metric used to summarize retrieval performance."
                ),
                claims=[
                    "A labeled evaluation dataset identifies the passages expected to be relevant for each query.",
                    "Retrieved results are compared with those expected relevant passages for each case.",
                    "Metrics such as recall at a fixed cutoff summarize how many expected relevant passages were retrieved.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="recovery-full-short",
                question="How does checkpoint recovery resume a failed workflow?",
                objective=(
                    "Explain what state is saved and how execution continues "
                    "from that saved state instead of restarting."
                ),
                claims=[
                    "The checkpoint stores the completed-step state and the next resumable position, and recovery restores that checkpoint so execution continues from the saved position rather than rerunning the workflow from the beginning.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="objective-narrow-full",
                question="What does the monitoring subsystem do?",
                objective=(
                    "Focus only on how it detects that a configured usage "
                    "threshold has been reached and emits an alert."
                ),
                claims=[
                    "The subsystem compares the observed usage value with the configured threshold.",
                    "When the threshold is reached, it emits an alert event.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),

            # -----------------------------------------------------------------
            # PARTIALLY_COVERED (6)
            # -----------------------------------------------------------------
            AnswerCoverageEvaluationCase(
                case_id="mechanism-budget-no-enforcement",
                question="How does a system enforce an execution budget?",
                objective=(
                    "Explain how usage is measured, compared with limits, "
                    "and used to stop later execution."
                ),
                claims=[
                    "The system records cumulative usage after each operation.",
                    "Before another operation begins, usage is compared with the configured limit.",
                    "Usage statistics are written to an execution trace.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="comparison-one-side",
                question="How do keyword retrieval and embedding retrieval differ?",
                objective=(
                    "Compare the matching signal used by each approach "
                    "and explain the practical tradeoff."
                ),
                claims=[
                    "Keyword retrieval ranks passages using lexical term overlap.",
                    "Exact term matches can be useful when terminology is stable.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="access-control-measurement-only",
                question="How can an agent restrict a tool to authorized users?",
                objective=(
                    "Explain the authorization input, the decision point, "
                    "and the action taken when access is denied."
                ),
                claims=[
                    "The system records the caller identity for each requested tool invocation.",
                    "Authorization policies are attached to tool metadata.",
                    "Denied-attempt statistics are available in an audit report.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="evaluation-method-no-metric",
                question="How should retrieval quality be evaluated?",
                objective=(
                    "Describe the reference data, the comparison performed, "
                    "and the metric used to summarize retrieval performance."
                ),
                claims=[
                    "A labeled dataset identifies passages expected to be relevant for each query.",
                    "Retrieved passages are compared with the expected relevant passages.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="repeated-same-aspect",
                question="How does checkpoint recovery resume a failed workflow?",
                objective=(
                    "Explain what state is saved and how execution continues "
                    "from that saved state instead of restarting."
                ),
                claims=[
                    "A checkpoint stores completed step identifiers.",
                    "Completed step identifiers are persisted in checkpoint storage.",
                    "Checkpoint metadata records which steps already completed.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="broad-question-narrow-objective-partial",
                question="What does the monitoring subsystem do?",
                objective=(
                    "Focus only on how it detects that a configured usage "
                    "threshold has been reached and emits an alert."
                ),
                claims=[
                    "The subsystem records usage observations.",
                    "It compares the observed usage value with the configured threshold.",
                    "It stores timestamps for each observation.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),

            # -----------------------------------------------------------------
            # INSUFFICIENT (6)
            # -----------------------------------------------------------------
            AnswerCoverageEvaluationCase(
                case_id="mechanism-budget-insufficient",
                question="How does a system enforce an execution budget?",
                objective=(
                    "Explain how usage is measured, compared with limits, "
                    "and used to stop later execution."
                ),
                claims=[
                    "Execution traces can be exported as JSON.",
                    "The system supports named execution profiles.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="comparison-unrelated-context",
                question="How do keyword retrieval and embedding retrieval differ?",
                objective=(
                    "Compare the matching signal used by each approach "
                    "and explain the practical tradeoff."
                ),
                claims=[
                    "Search results can be cached.",
                    "Documents may contain metadata and timestamps.",
                    "Retrieval systems can run in web applications.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="access-control-audit-only",
                question="How can an agent restrict a tool to authorized users?",
                objective=(
                    "Explain the authorization input, the decision point, "
                    "and the action taken when access is denied."
                ),
                claims=[
                    "Every tool invocation is written to an audit log after execution.",
                    "Administrators can export monthly usage summaries.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="evaluation-method-storage-only",
                question="How should retrieval quality be evaluated?",
                objective=(
                    "Describe the reference data, the comparison performed, "
                    "and the metric used to summarize retrieval performance."
                ),
                claims=[
                    "Retrieval results are persisted in versioned JSON files.",
                    "Each run receives a unique execution identifier.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="recovery-background-only",
                question="How does checkpoint recovery resume a failed workflow?",
                objective=(
                    "Explain what state is saved and how execution continues "
                    "from that saved state instead of restarting."
                ),
                claims=[
                    "Workflows can contain multiple dependent steps.",
                    "Failures may be caused by network or tool errors.",
                    "Execution histories are useful for debugging.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="objective-narrow-wrong-capability",
                question="What does the monitoring subsystem do?",
                objective=(
                    "Focus only on how it detects that a configured usage "
                    "threshold has been reached and emits an alert."
                ),
                claims=[
                    "The subsystem compresses archived monitoring records.",
                    "Historical records can be searched by date.",
                    "Operators can download CSV exports.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
        ],
    )
