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
    ("Stage9PlannerUsageAccountingError", "planner_usage_accounting_failed"),
    ("PlannerClientError", "planner_output_invalid"),
    ("BoundedResearchPlanningLoopError", "planning_loop_failed"),
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
