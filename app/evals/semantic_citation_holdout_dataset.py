"""Blind holdout dataset for semantic citation evaluation."""

from __future__ import annotations

from app.schemas.semantic_citation_evaluation import (
    SemanticCitationEvaluationCase,
    SemanticCitationEvaluationDataset,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


def build_semantic_citation_holdout_dataset(
) -> SemanticCitationEvaluationDataset:
    """Build the fixed blind semantic citation holdout dataset."""

    return SemanticCitationEvaluationDataset(
        dataset_id="semantic-citation-holdout-v1",
        version="1.0.0",
        cases=[
            # -------------------------------------------------
            # Fully supported
            # -------------------------------------------------
            SemanticCitationEvaluationCase(
                case_id="holdout-fully-001-paraphrase",
                claim=(
                    "The client records the identifier "
                    "returned by the server."
                ),
                evidence=(
                    "The identifier returned by the server "
                    "is recorded by the client."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description=(
                    "Passive-to-active paraphrase with "
                    "preserved meaning."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-fully-002-subset",
                claim=(
                    "The response includes a timestamp."
                ),
                evidence=(
                    "The response includes a timestamp, "
                    "request ID, and status value."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description=(
                    "Claim selects one explicitly supported "
                    "member of a larger set."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-fully-003-condition-preserved",
                claim=(
                    "When debug mode is enabled, detailed "
                    "logs are written."
                ),
                evidence=(
                    "Detailed logs are written when debug "
                    "mode is enabled."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description=(
                    "Condition and behavior are preserved "
                    "through reordering."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-fully-004-quantity-preserved",
                claim=(
                    "The batch contains ten records."
                ),
                evidence=(
                    "Exactly ten records are contained "
                    "in the batch."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description=(
                    "Exact quantity is preserved."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-fully-005-logical-narrowing",
                claim=(
                    "Administrators can view audit logs."
                ),
                evidence=(
                    "Administrators and security reviewers "
                    "can view audit logs."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description=(
                    "Claim is a supported subset of the "
                    "authorized roles."
                ),
            ),

            # -------------------------------------------------
            # Partially supported
            # -------------------------------------------------
            SemanticCitationEvaluationCase(
                case_id="holdout-partial-001-time-scope",
                claim=(
                    "The service is available at all times."
                ),
                evidence=(
                    "The service is available during "
                    "business hours."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "Core availability is supported while "
                    "temporal scope is broadened."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-partial-002-exception-omitted",
                claim=(
                    "Requests are accepted from authenticated "
                    "users."
                ),
                evidence=(
                    "Requests are accepted from authenticated "
                    "users except while maintenance mode "
                    "is active."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "Claim omits an explicit exception."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-partial-003-conjunction",
                claim=(
                    "The worker validates the payload and "
                    "encrypts it before storage."
                ),
                evidence=(
                    "The worker validates the payload."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "One conjunct is supported while the "
                    "second is unspecified."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-partial-004-frequency",
                claim=(
                    "The scheduler checks the queue every minute."
                ),
                evidence=(
                    "The scheduler checks the queue periodically."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "Core periodic behavior is supported but "
                    "the exact frequency is not."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-partial-005-geographic-scope",
                claim=(
                    "The feature is available in every region."
                ),
                evidence=(
                    "The feature is available in several regions."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "Availability is supported while geographic "
                    "scope is overstated."
                ),
            ),

            # -------------------------------------------------
            # Unsupported
            # -------------------------------------------------
            SemanticCitationEvaluationCase(
                case_id="holdout-unsupported-001-date",
                claim=(
                    "The feature was released in March 2026."
                ),
                evidence=(
                    "The feature is available in the current "
                    "release."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "Evidence does not specify the claimed date."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-unsupported-002-property",
                claim=(
                    "The cache stores encrypted values."
                ),
                evidence=(
                    "The cache stores values for five minutes."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "Evidence concerns retention duration, "
                    "not encryption."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-unsupported-003-entity",
                claim=(
                    "The browser verifies access tokens."
                ),
                evidence=(
                    "The API server verifies access tokens."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "The same action is attributed to a "
                    "different entity."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-unsupported-004-mechanism",
                claim=(
                    "The application uses a hardware key "
                    "to protect credentials."
                ),
                evidence=(
                    "The application protects stored credentials."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "Protection is supported but the claimed "
                    "mechanism is unspecified."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-unsupported-005-different-metric",
                claim=(
                    "Compression reduces memory consumption."
                ),
                evidence=(
                    "Compression reduced network transfer size."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "Evidence reports improvement in a "
                    "different metric."
                ),
            ),

            # -------------------------------------------------
            # Contradicted
            # -------------------------------------------------
            SemanticCitationEvaluationCase(
                case_id="holdout-contradicted-001-state",
                claim=(
                    "The account is active."
                ),
                evidence=(
                    "The account is suspended."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Evidence states a mutually incompatible state."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-contradicted-002-sign",
                claim=(
                    "The update added five records."
                ),
                evidence=(
                    "The update removed five records."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Evidence states the opposite operation."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-contradicted-003-minimum",
                claim=(
                    "At least ten approvals are required."
                ),
                evidence=(
                    "No more than five approvals are required."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Minimum and maximum bounds are mutually "
                    "incompatible."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-contradicted-004-order",
                claim=(
                    "Data validation happens before parsing."
                ),
                evidence=(
                    "Parsing happens before data validation."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Evidence reverses the claimed processing order."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="holdout-contradicted-005-negation",
                claim=(
                    "Anonymous access is permitted."
                ),
                evidence=(
                    "Anonymous access is not permitted."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Evidence explicitly negates the claim."
                ),
            ),
        ],
    )
