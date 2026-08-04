"""End-to-end tests for Phase 11 reliability components."""


import pytest

from app.guardrails.failure_recovery import (
    FailureRecoveryContext,
    RecoveryCandidate,
)
from app.guardrails.failure_recovery_evaluator import (
    FailureRecoveryEvaluator,
)
from app.guardrails.failure_recovery_policy import (
    FailureRecoveryPolicy,
    RecoveryStrategy,
    RecoveryStrategyRule,
    RecoveryTargetType,
)
from app.guardrails.guardrail_result import (
    GuardrailDecision,
)
from app.guardrails.input_guardrail_evaluator import (
    InputGuardrailEvaluator,
)
from app.guardrails.input_guardrail_snapshot import (
    InputGuardrailSnapshot,
)
from app.guardrails.phase11_e2e_evaluator import (
    Phase11E2EEvaluator,
)
from app.guardrails.phase11_e2e_evaluator_error import (
    Phase11E2EEvaluatorError,
)
from app.guardrails.reliability_metrics import (
    ReliabilityExecutionRecord,
    ReliabilityExecutionStatus,
    ReliabilityRecoveryStatus,
)
from app.guardrails.reliability_metrics_calculator import (
    ReliabilityMetricsCalculator,
)
from app.guardrails.retry_decision import (
    RetryDecisionType,
    RetryFailureContext,
    RetryStopReason,
)
from app.guardrails.retry_policy import (
    RetryBackoffStrategy,
    RetryFailureCategory,
    RetryJitterStrategy,
    RetryPolicy,
)
from app.guardrails.retry_policy_evaluator import (
    RetryPolicyEvaluator,
)
from app.guardrails.tool_permission import (
    AgentToolPermissionProfile,
    ToolAccessMode,
    ToolCallRequest,
    ToolPermissionRule,
    ToolRiskLevel,
)
from app.guardrails.tool_permission_guardrail_evaluator import (
    ToolPermissionGuardrailEvaluator,
)
from app.guardrails.tool_permission_guardrail_snapshot import (
    ToolPermissionGuardrailSnapshot,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentInput,
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)


def identity(
    *,
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentIdentity:
    """Return one research-agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=role.value,
        role=role,
        description=f"{role.value} agent.",
    )


def manager_profile() -> ResearchAgentCapabilityProfile:
    """Return one manager profile."""

    manager = identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
    )

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=manager,
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SEARCH_SPECIALIST,
        ],
    )


def search_profile() -> ResearchAgentCapabilityProfile:
    """Return one search specialist profile."""

    agent = identity(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
    )

    return ResearchAgentCapabilityProfile(
        profile_id="profile-search-001",
        agent=agent,
        capabilities=[
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
    )


def assignment() -> ResearchAgentTaskAssignment:
    """Return one executable search assignment."""

    profile = search_profile()

    return ResearchAgentTaskAssignment(
        assignment_id="assignment-search-001",
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=manager_profile(),
        assignee=profile.agent,
        required_role=ResearchAgentRole.SEARCH_SPECIALIST,
        required_capabilities=[
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
        title="Search sources",
        objective="Find authoritative sources.",
        instructions=[
            "Return normalized source candidates.",
        ],
        inputs=[
            ResearchAgentAssignmentInput(
                name="research-question",
                reference_type="research_question",
                reference_id="question-001",
            )
        ],
        expected_output_type=(
            "research_source_candidate_set"
        ),
        acceptance_criteria=[
            "Return at least one source candidate.",
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )


def input_snapshot() -> InputGuardrailSnapshot:
    """Return one valid assignment input snapshot."""

    return InputGuardrailSnapshot(
        assignment=assignment(),
        assignee_profile=search_profile(),
        available_reference_ids=["question-001"],
        expected_request_id="research-001",
        expected_workspace_id="workspace-001",
    )


def permission_profile() -> AgentToolPermissionProfile:
    """Return one search tool permission profile."""

    return AgentToolPermissionProfile(
        profile_id="tool-profile-001",
        agent_id="agent-search-001",
        agent_role=ResearchAgentRole.SEARCH_SPECIALIST,
        rules=[
            ToolPermissionRule(
                tool_name="source_search",
                allowed_operations=["search"],
                access_mode=ToolAccessMode.READ_ONLY,
                allow_external_network=True,
                maximum_calls=3,
                allowed_roles=[
                    ResearchAgentRole.SEARCH_SPECIALIST,
                ],
            )
        ],
        default_deny=True,
    )


def tool_request(
    *,
    tool_name: str,
) -> ToolCallRequest:
    """Return one tool-call request."""

    return ToolCallRequest(
        call_id=f"call-{tool_name}",
        request_id="research-001",
        workspace_id="workspace-001",
        agent_id="agent-search-001",
        agent_role=ResearchAgentRole.SEARCH_SPECIALIST,
        tool_name=tool_name,
        operation="search",
        external_network=True,
        risk_level=ToolRiskLevel.LOW,
    )


def tool_snapshot(
    *,
    tool_name: str,
) -> ToolPermissionGuardrailSnapshot:
    """Return one tool permission snapshot."""

    return ToolPermissionGuardrailSnapshot(
        request=tool_request(tool_name=tool_name),
        permission_profile=permission_profile(),
        expected_request_id="research-001",
        expected_workspace_id="workspace-001",
        prior_tool_call_count=0,
    )


def retry_policy() -> RetryPolicy:
    """Return one two-attempt retry policy."""

    return RetryPolicy(
        policy_id="retry-policy-e2e",
        name="E2E retry policy",
        description="Retry temporary timeouts once.",
        version="1.0.0",
        maximum_attempts=2,
        base_delay_seconds=1.0,
        maximum_delay_seconds=5.0,
        backoff_strategy=RetryBackoffStrategy.EXPONENTIAL,
        multiplier=2.0,
        jitter_strategy=RetryJitterStrategy.NONE,
        allowed_categories=[
            RetryFailureCategory.TIMEOUT,
        ],
        denied_categories=[
            RetryFailureCategory.VALIDATION,
        ],
        respect_retry_after=True,
        retry_after_max_seconds=30.0,
    )


def retry_failure(
    *,
    failure_id: str,
    attempt_number: int,
) -> RetryFailureContext:
    """Return one timeout failure."""

    return RetryFailureContext(
        failure_id=failure_id,
        category=RetryFailureCategory.TIMEOUT,
        error_code="TOOL_TIMEOUT",
        message="The source search timed out.",
        retryable=True,
        attempt_number=attempt_number,
    )


def recovery_policy() -> FailureRecoveryPolicy:
    """Return one alternate-tool recovery policy."""

    return FailureRecoveryPolicy(
        policy_id="recovery-policy-e2e",
        name="E2E recovery policy",
        description="Use an alternate tool after retries.",
        version="1.0.0",
        strategies=[
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.ALTERNATE_TOOL,
                priority=10,
                allowed_failure_categories=[
                    RetryFailureCategory.TIMEOUT,
                ],
            ),
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.MANUAL_REVIEW,
                priority=20,
            ),
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.ABORT,
                priority=30,
            ),
        ],
        require_manual_review_before_abort=True,
    )


def recovery_context() -> FailureRecoveryContext:
    """Return one exhausted retry context."""

    return FailureRecoveryContext(
        failure_id="failure-attempt-002",
        failure_category=RetryFailureCategory.TIMEOUT,
        error_code="TOOL_TIMEOUT",
        current_tool_name="source_search",
        current_agent_id="agent-search-001",
        retry_exhausted=True,
        candidates=[
            RecoveryCandidate(
                candidate_id="source_search_backup",
                target_type=RecoveryTargetType.TOOL,
                available=True,
                priority=10,
            )
        ],
    )


def execution_records(
) -> list[ReliabilityExecutionRecord]:
    """Return E2E reliability execution records."""

    return [
        ReliabilityExecutionRecord(
            execution_id="execution-attempt-001",
            status=ReliabilityExecutionStatus.TIMED_OUT,
            duration_seconds=10.0,
            attempt_count=1,
            guardrail_evaluated=True,
            guardrail_blocked=False,
            recovery_status=(
                ReliabilityRecoveryStatus.NOT_ATTEMPTED
            ),
            failure_category=RetryFailureCategory.TIMEOUT,
        ),
        ReliabilityExecutionRecord(
            execution_id="execution-attempt-002",
            status=ReliabilityExecutionStatus.TIMED_OUT,
            duration_seconds=10.0,
            attempt_count=2,
            guardrail_evaluated=True,
            guardrail_blocked=False,
            recovery_status=(
                ReliabilityRecoveryStatus.FAILED
            ),
            failure_category=RetryFailureCategory.TIMEOUT,
        ),
        ReliabilityExecutionRecord(
            execution_id="execution-fallback-001",
            status=ReliabilityExecutionStatus.SUCCEEDED,
            duration_seconds=4.0,
            attempt_count=1,
            guardrail_evaluated=True,
            guardrail_blocked=False,
            recovery_status=(
                ReliabilityRecoveryStatus.SUCCEEDED
            ),
        ),
    ]


def evaluator() -> Phase11E2EEvaluator:
    """Return one deterministic Phase 11 E2E evaluator."""

    return Phase11E2EEvaluator(
        input_guardrail_evaluator=InputGuardrailEvaluator(
            evaluation_id_factory=(
                lambda: "input-evaluation-001"
            ),
            violation_id_factory=(
                lambda index: f"input-violation-{index}"
            ),
        ),
        tool_guardrail_evaluator=(
            ToolPermissionGuardrailEvaluator(
                evaluation_id_factory=(
                    lambda: "tool-evaluation-001"
                ),
                violation_id_factory=(
                    lambda index: f"tool-violation-{index}"
                ),
            )
        ),
        retry_policy_evaluator=RetryPolicyEvaluator(
            policy=retry_policy(),
            decision_id_factory=(
                lambda: "retry-decision-001"
            ),
            random_fraction_factory=lambda: 0.5,
        ),
        failure_recovery_evaluator=(
            FailureRecoveryEvaluator(
                policy=recovery_policy(),
                decision_id_factory=(
                    lambda: "recovery-decision-001"
                ),
            )
        ),
        reliability_metrics_calculator=(
            ReliabilityMetricsCalculator(
                metrics_id_factory=(
                    lambda: "reliability-metrics-001"
                )
            )
        ),
        evaluation_id_factory=(
            lambda: "phase11-e2e-001"
        ),
    )


def test_phase11_e2e_reliability_flow() -> None:
    """Run the complete Phase 11 reliability scenario."""

    value = evaluator().evaluate(
        input_snapshot=input_snapshot(),
        denied_tool_snapshot=tool_snapshot(
            tool_name="filesystem_delete"
        ),
        allowed_tool_snapshot=tool_snapshot(
            tool_name="source_search"
        ),
        retry_failures=[
            retry_failure(
                failure_id="failure-attempt-001",
                attempt_number=1,
            ),
            retry_failure(
                failure_id="failure-attempt-002",
                attempt_number=2,
            ),
        ],
        recovery_context=recovery_context(),
        execution_records=execution_records(),
    )

    assert value.completed is True
    assert value.input_guardrail_result.decision is (
        GuardrailDecision.ALLOWED
    )
    assert value.denied_tool_guardrail_result.decision is (
        GuardrailDecision.BLOCKED
    )
    assert value.allowed_tool_guardrail_result.decision is (
        GuardrailDecision.ALLOWED
    )

    assert value.retry_decisions[0].decision is (
        RetryDecisionType.RETRY
    )
    assert value.retry_decisions[1].decision is (
        RetryDecisionType.STOP
    )
    assert value.retry_decisions[1].stop_reason is (
        RetryStopReason.MAXIMUM_ATTEMPTS_REACHED
    )

    assert value.recovery_decision.strategy is (
        RecoveryStrategy.ALTERNATE_TOOL
    )
    assert (
        value.recovery_decision.selected_candidate_id
        == "source_search_backup"
    )

    assert value.reliability_metrics.total_executions == 3
    assert value.reliability_metrics.successful_executions == 1
    assert value.reliability_metrics.timed_out_executions == 2
    assert value.reliability_metrics.recovery_successes == 1
    assert value.reliability_metrics.success_rate == pytest.approx(
        1 / 3
    )


def test_e2e_stops_when_input_guardrail_blocks() -> None:
    invalid_input = input_snapshot().model_copy(
        update={
            "available_reference_ids": [],
        }
    )

    with pytest.raises(
        Phase11E2EEvaluatorError,
        match="input guardrail blocked the E2E scenario",
    ):
        evaluator().evaluate(
            input_snapshot=invalid_input,
            denied_tool_snapshot=tool_snapshot(
                tool_name="filesystem_delete"
            ),
            allowed_tool_snapshot=tool_snapshot(
                tool_name="source_search"
            ),
            retry_failures=[
                retry_failure(
                    failure_id="failure-001",
                    attempt_number=1,
                )
            ],
            recovery_context=recovery_context(),
            execution_records=execution_records(),
        )


def test_e2e_requires_retry_failures() -> None:
    with pytest.raises(
        Phase11E2EEvaluatorError,
        match="E2E scenario requires retry failures",
    ):
        evaluator().evaluate(
            input_snapshot=input_snapshot(),
            denied_tool_snapshot=tool_snapshot(
                tool_name="filesystem_delete"
            ),
            allowed_tool_snapshot=tool_snapshot(
                tool_name="source_search"
            ),
            retry_failures=[],
            recovery_context=recovery_context(),
            execution_records=execution_records(),
        )


def test_e2e_rejects_blank_evaluation_id() -> None:
    value = Phase11E2EEvaluator(
        input_guardrail_evaluator=InputGuardrailEvaluator(),
        tool_guardrail_evaluator=(
            ToolPermissionGuardrailEvaluator()
        ),
        retry_policy_evaluator=RetryPolicyEvaluator(
            policy=retry_policy(),
        ),
        failure_recovery_evaluator=(
            FailureRecoveryEvaluator(
                policy=recovery_policy(),
            )
        ),
        reliability_metrics_calculator=(
            ReliabilityMetricsCalculator()
        ),
        evaluation_id_factory=lambda: " ",
    )

    with pytest.raises(
        Phase11E2EEvaluatorError,
        match="evaluation_id factory returned blank value",
    ):
        value.evaluate(
            input_snapshot=input_snapshot(),
            denied_tool_snapshot=tool_snapshot(
                tool_name="filesystem_delete"
            ),
            allowed_tool_snapshot=tool_snapshot(
                tool_name="source_search"
            ),
            retry_failures=[
                retry_failure(
                    failure_id="failure-001",
                    attempt_number=1,
                )
            ],
            recovery_context=recovery_context(),
            execution_records=execution_records(),
        )
