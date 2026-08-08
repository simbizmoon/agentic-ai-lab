"""Fresh blind holdout dataset for semantic answer coverage evaluation."""

from __future__ import annotations

from app.evals.answer_coverage_evaluation import (
    AnswerCoverageEvaluationCase,
    AnswerCoverageEvaluationDataset,
)
from app.schemas.answer_coverage_judgment import AnswerCoverageLevel


def build_answer_coverage_blind_holdout_dataset(
) -> AnswerCoverageEvaluationDataset:
    """Return a fresh 20-case blind holdout dataset."""

    return AnswerCoverageEvaluationDataset(
        dataset_id="answer-coverage-blind-holdout-v1",
        version="1.0.0",
        cases=[
            # FULLY_COVERED (7)
            AnswerCoverageEvaluationCase(
                case_id="retry-policy-full",
                question="How does a retry policy control repeated requests?",
                objective=(
                    "Explain when a retry is allowed, what limit stops retries, "
                    "and what happens after the limit is reached."
                ),
                claims=[
                    "A failed request is retried only when the failure is classified as retryable.",
                    "The retry counter is compared with the configured maximum before another attempt begins.",
                    "Once the maximum retry count is reached, no further retry is started and the failure is returned.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="cache-invalidation-full",
                question="How does cache invalidation keep cached data fresh?",
                objective=(
                    "Explain what event marks cached data stale and how a later read obtains fresh data."
                ),
                claims=[
                    "A source update marks the corresponding cache entry stale.",
                    "When a later read encounters a stale entry, the system fetches current data from the source.",
                    "The refreshed value replaces the stale cache entry before being returned.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="rate-limit-full",
                question="How does a rate limiter prevent excessive requests?",
                objective=(
                    "Describe the tracked usage, the threshold decision, and the response to an over-limit request."
                ),
                claims=[
                    "The limiter tracks the number of requests associated with a client during the active window.",
                    "Each incoming request is checked against the configured request limit.",
                    "Requests above the limit are rejected until the applicable window permits more requests.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="fallback-routing-full",
                question="How does fallback routing handle an unavailable primary service?",
                objective=(
                    "Explain detection of primary unavailability and how traffic is redirected to a fallback."
                ),
                claims=[
                    "A health check determines that the primary service is unavailable.",
                    "The router stops selecting the unavailable primary target.",
                    "Subsequent requests are directed to the configured fallback service.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="schema-validation-full-short",
                question="How does schema validation reject malformed input?",
                objective=(
                    "Explain how input is checked against requirements and what happens when validation fails."
                ),
                claims=[
                    "The validator checks the submitted fields and types against the schema, and when a required constraint fails it rejects the input with validation errors instead of passing it to normal processing.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="queue-backpressure-full",
                question="How does backpressure protect a worker queue from overload?",
                objective=(
                    "Explain the load signal, the admission decision, and how excess work is prevented from entering the queue."
                ),
                claims=[
                    "The system observes the current queue depth.",
                    "Before accepting new work, it compares queue depth with the configured capacity threshold.",
                    "When capacity is exhausted, additional work is rejected or deferred rather than enqueued.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="feature-flag-full",
                question="How does a feature flag control whether a feature executes?",
                objective=(
                    "Explain how flag state is evaluated and how that result changes execution."
                ),
                claims=[
                    "The runtime reads the configured feature flag state for the current context.",
                    "If the flag is enabled, execution enters the feature path; if it is disabled, that path is skipped.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),

            # PARTIALLY_COVERED (7)
            AnswerCoverageEvaluationCase(
                case_id="retry-policy-no-terminal-action",
                question="How does a retry policy control repeated requests?",
                objective=(
                    "Explain when a retry is allowed, what limit stops retries, "
                    "and what happens after the limit is reached."
                ),
                claims=[
                    "A failed request is retried only when the failure is classified as retryable.",
                    "The retry counter is compared with a configured maximum before another attempt.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="cache-invalidation-stale-only",
                question="How does cache invalidation keep cached data fresh?",
                objective=(
                    "Explain what event marks cached data stale and how a later read obtains fresh data."
                ),
                claims=[
                    "A source update marks the related cache entry stale.",
                    "The cache records when the entry became stale.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="rate-limit-count-only",
                question="How does a rate limiter prevent excessive requests?",
                objective=(
                    "Describe the tracked usage, the threshold decision, and the response to an over-limit request."
                ),
                claims=[
                    "The limiter tracks requests per client during a time window.",
                    "The current count is compared with a configured limit.",
                    "Usage counts are exported for monitoring.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="fallback-detection-only",
                question="How does fallback routing handle an unavailable primary service?",
                objective=(
                    "Explain detection of primary unavailability and how traffic is redirected to a fallback."
                ),
                claims=[
                    "Health checks can identify that the primary service is unavailable.",
                    "The failure state is recorded in routing telemetry.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="schema-validation-check-only",
                question="How does schema validation reject malformed input?",
                objective=(
                    "Explain how input is checked against requirements and what happens when validation fails."
                ),
                claims=[
                    "Submitted values are checked for required fields and expected types.",
                    "Validation problems are collected into an error list.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="queue-backpressure-no-admission-action",
                question="How does backpressure protect a worker queue from overload?",
                objective=(
                    "Explain the load signal, the admission decision, and how excess work is prevented from entering the queue."
                ),
                claims=[
                    "The system observes current queue depth.",
                    "Queue depth is compared with the configured capacity threshold.",
                    "Historical queue depth is graphed for operators.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="feature-flag-one-branch",
                question="How does a feature flag control whether a feature executes?",
                objective=(
                    "Explain how flag state is evaluated and how that result changes execution."
                ),
                claims=[
                    "The runtime reads the current feature flag state.",
                    "When the flag is enabled, the feature path executes.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),

            # INSUFFICIENT (6)
            AnswerCoverageEvaluationCase(
                case_id="retry-policy-observability-only",
                question="How does a retry policy control repeated requests?",
                objective=(
                    "Explain when a retry is allowed, what limit stops retries, "
                    "and what happens after the limit is reached."
                ),
                claims=[
                    "Request failures are written to structured logs.",
                    "Dashboards display failure counts by endpoint.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="cache-invalidation-storage-only",
                question="How does cache invalidation keep cached data fresh?",
                objective=(
                    "Explain what event marks cached data stale and how a later read obtains fresh data."
                ),
                claims=[
                    "Cached values are stored with metadata.",
                    "Cache entries can be inspected through an administration page.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="rate-limit-reporting-only",
                question="How does a rate limiter prevent excessive requests?",
                objective=(
                    "Describe the tracked usage, the threshold decision, and the response to an over-limit request."
                ),
                claims=[
                    "API traffic is summarized in daily reports.",
                    "Operators can search request logs by client identifier.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="fallback-config-only",
                question="How does fallback routing handle an unavailable primary service?",
                objective=(
                    "Explain detection of primary unavailability and how traffic is redirected to a fallback."
                ),
                claims=[
                    "The routing configuration stores primary and secondary service names.",
                    "Configuration changes are versioned.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="schema-validation-docs-only",
                question="How does schema validation reject malformed input?",
                objective=(
                    "Explain how input is checked against requirements and what happens when validation fails."
                ),
                claims=[
                    "The API documentation lists available request fields.",
                    "Schema versions are stored in source control.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="feature-flag-audit-only",
                question="How does a feature flag control whether a feature executes?",
                objective=(
                    "Explain how flag state is evaluated and how that result changes execution."
                ),
                claims=[
                    "Flag changes are written to an audit log.",
                    "Administrators can view a history of flag updates.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
        ],
    )
