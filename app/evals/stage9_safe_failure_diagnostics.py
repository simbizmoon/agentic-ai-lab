"""Convert Stage 9 exception chains into non-sensitive diagnostic codes."""

from __future__ import annotations

_CLASS_CODE_PRIORITY = (
    ("AuthenticationError", "provider_authentication_failed"),
    ("PermissionDeniedError", "provider_permission_denied"),
    ("NotFoundError", "provider_resource_not_found"),
    ("BadRequestError", "provider_bad_request"),
    ("RateLimitError", "provider_rate_limited"),
    ("APITimeoutError", "provider_timeout"),
    ("APIConnectionError", "provider_connection_failed"),
    ("Stage9TavilyTimeoutError", "official_web_provider_timeout"),
    ("Stage9TavilyConnectionError", "official_web_provider_connection_failed"),
    ("Stage9TavilyHttpStatusError", "official_web_provider_http_failed"),
    (
        "Stage9TavilyResponseValidationError",
        "official_web_provider_response_invalid",
    ),
    (
        "Stage9TavilyRawContentUnavailableError",
        "official_web_raw_content_unavailable",
    ),
    (
        "Stage9TavilyResultCountBoundaryError",
        "official_web_result_count_boundary_failed",
    ),
    (
        "Stage9TavilyContentSizeBoundaryError",
        "official_web_content_size_boundary_failed",
    ),
    (
        "Stage9TavilyDomainBoundaryError",
        "official_web_domain_boundary_failed",
    ),
    ("Stage9TavilyBoundaryError", "official_web_provider_boundary_failed"),
    ("Stage9TavilyOfficialWebProviderError", "official_web_provider_failed"),
    ("Stage9OfficialWebAcquisitionError", "official_web_evidence_invalid"),
    ("Stage9DevelopmentAcquisitionRouterError", "acquisition_routing_failed"),
    ("Stage9AcquisitionAwareResearchLoopError", "acquisition_loop_failed"),
    ("Stage9PackedResearchLoopFactoryError", "packed_loop_composition_failed"),
    ("Stage9DevelopmentCaseArtifactError", "artifact_persistence_failed"),
    ("Stage9ConservativeCostEstimationError", "cost_estimation_failed"),
    ("Stage9PlannerUsageAccountingError", "planner_usage_accounting_failed"),
    ("PlannerClientError", "planner_output_invalid"),
    ("BoundedResearchPlanningLoopError", "planning_loop_failed"),
    ("ValidationError", "contract_validation_failed"),
)


def safe_stage9_failure_code(error: BaseException) -> str:
    """Classify an exception chain without retaining messages or arguments."""

    if not isinstance(error, BaseException):
        raise TypeError("error must be an exception")

    names: set[str] = set()
    visited: set[int] = set()
    current: BaseException | None = error
    while current is not None and len(visited) < 16:
        identity = id(current)
        if identity in visited:
            break
        visited.add(identity)
        names.add(type(current).__name__)
        current = current.__cause__ or current.__context__

    for class_name, code in _CLASS_CODE_PRIORITY:
        if class_name in names:
            return code
    return "case_execution_failed"
