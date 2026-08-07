"""Adjudicated v2 golden dataset for semantic citation evaluation."""

from __future__ import annotations

from app.schemas.semantic_citation_evaluation import (
    SemanticCitationEvaluationCase,
    SemanticCitationEvaluationDataset,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


def build_semantic_citation_golden_dataset_v2(
) -> SemanticCitationEvaluationDataset:
    """Build the adjudicated semantic citation golden dataset v2."""

    return SemanticCitationEvaluationDataset(
        dataset_id="semantic-citation-golden-v2",
        version="2.0.0",
        cases=[
            # -------------------------------------------------
            # Fully supported
            # -------------------------------------------------
            SemanticCitationEvaluationCase(
                case_id="fully-001-verbatim",
                claim="The SDK supports function tools.",
                evidence="The SDK supports function tools.",
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description="Exact claim/evidence support.",
            ),
            SemanticCitationEvaluationCase(
                case_id="fully-002-paraphrase",
                claim="The service can retry failed requests.",
                evidence=(
                    "Failed requests may be retried by the service."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description=(
                    "Equivalent capability expressed with "
                    "different wording."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="fully-003-narrower",
                claim="The system stores request identifiers.",
                evidence=(
                    "The system stores request identifiers, "
                    "response identifiers, and timestamps."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description=(
                    "Claim is narrower than the evidence."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="fully-004-numeric-narrowing",
                claim=(
                    "The operation may be retried up to "
                    "three times."
                ),
                evidence=(
                    "The operation may be retried up to "
                    "five times."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description=(
                    "Claim uses a stricter numerical bound "
                    "than the evidence allows."
                ),
            ),

            # -------------------------------------------------
            # Partially supported
            # -------------------------------------------------
            SemanticCitationEvaluationCase(
                case_id="partial-001-conjunction",
                claim=(
                    "The SDK supports function tools and "
                    "automatically searches the web."
                ),
                evidence="The SDK supports function tools.",
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "Only one part of a conjunctive claim "
                    "is supported."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="partial-002-qualifier",
                claim=(
                    "The service always retries failed requests."
                ),
                evidence=(
                    "The service may retry failed requests."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "Core retry behavior is supported, but "
                    "the absolute qualifier is overstated."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="partial-003-condition",
                claim="The system records detailed traces.",
                evidence=(
                    "When tracing is enabled, the system "
                    "records detailed traces."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "Claim omits an important condition."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="partial-004-scope",
                claim=(
                    "The application records all user actions."
                ),
                evidence=(
                    "The application records user actions "
                    "performed during authenticated sessions."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "Core behavior is supported but the "
                    "claim broadens scope."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="partial-005-secondary-assertion",
                claim=(
                    "The service validates input and stores "
                    "the validation result permanently."
                ),
                evidence=(
                    "The service validates input."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
                ),
                description=(
                    "Primary assertion is supported while a "
                    "secondary assertion lacks evidence."
                ),
            ),

            # -------------------------------------------------
            # Unsupported
            # -------------------------------------------------
            SemanticCitationEvaluationCase(
                case_id="unsupported-001-unrelated",
                claim="The SDK automatically searches the web.",
                evidence=(
                    "Agents can maintain context across "
                    "multiple execution steps."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "Evidence concerns an unrelated capability."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="unsupported-002-entity",
                claim="The SDK stores conversation history.",
                evidence=(
                    "The database stores conversation history."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "Capability is attributed to a different entity."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="unsupported-003-causal-leap",
                claim=(
                    "Caching causes every request to complete faster."
                ),
                evidence=(
                    "Cached responses were associated with "
                    "lower average latency."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "Correlation evidence does not establish "
                    "the causal universal claim."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="unsupported-004-capability",
                claim="The model can execute shell commands.",
                evidence=(
                    "The model can generate structured JSON output."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "Evidence supports a different capability."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="unsupported-005-missing-number",
                claim=(
                    "The request timeout is exactly 30 seconds."
                ),
                evidence=(
                    "The request supports a configurable timeout."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description=(
                    "Evidence supports timeout capability but "
                    "not the claimed numerical value."
                ),
            ),

            # -------------------------------------------------
            # Contradicted
            # -------------------------------------------------
            SemanticCitationEvaluationCase(
                case_id="contradicted-001-required",
                claim=(
                    "Every agent execution requires at least "
                    "one tool call."
                ),
                evidence=(
                    "Tool use is optional, and an agent may "
                    "finish without calling any tool."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Optional behavior directly contradicts "
                    "a universal requirement."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="contradicted-002-none",
                claim="Some requests are retried.",
                evidence="Requests are never retried.",
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Evidence explicitly denies the claimed behavior."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="contradicted-003-direction",
                claim="The change increased average latency.",
                evidence="The change decreased average latency.",
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Evidence states the opposite direction."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="contradicted-004-temporal",
                claim=(
                    "Authentication occurs after the request "
                    "is processed."
                ),
                evidence=(
                    "Authentication occurs before the request "
                    "is processed."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Evidence states the opposite temporal ordering."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="contradicted-005-numeric-bound",
                claim=(
                    "The operation may be retried up to five times."
                ),
                evidence=(
                    "The operation may be retried up to three times."
                ),
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Claim and evidence state incompatible "
                    "maximum retry counts."
                ),
            ),
            SemanticCitationEvaluationCase(
                case_id="contradicted-006-explicit-negation",
                claim="The feature is enabled by default.",
                evidence="The feature is disabled by default.",
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description=(
                    "Evidence directly negates the claimed default."
                ),
            ),
        ],
    )
