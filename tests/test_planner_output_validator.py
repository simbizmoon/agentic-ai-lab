"""Tests for deterministic planner output validation."""

from app.planning.planner_output_validator import (
    PlannerOutputValidator,
)
from app.schemas.plan_draft import PlanStepDraft
from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_output_validation import (
    PlannerOutputValidationCode,
    PlannerOutputValidationResult,
)


def step(
    *,
    step_id: str,
    dependencies: list[str] | None = None,
    tool_name: str | None = None,
) -> PlanStepDraft:
    """Return one planner output step."""

    return PlanStepDraft(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete {step_id}.",
        dependencies=dependencies or [],
        tool_name=tool_name,
    )


def output(
    *steps: PlanStepDraft,
) -> PlanDraftOutput:
    """Return one structured planner output."""

    return PlanDraftOutput(
        reasoning_summary="The steps satisfy the goal.",
        steps=list(steps),
    )


def request(
    **overrides: object,
) -> PlanCreationRequest:
    """Return one planning request."""

    values: dict[str, object] = {
        "goal": "Complete the requested workflow.",
        "available_tools": ["python", "pytest"],
        "maximum_steps": 5,
        "allow_parallel_steps": True,
    }
    values.update(overrides)

    return PlanCreationRequest(**values)


def codes(
    result: PlannerOutputValidationResult,
) -> list[PlannerOutputValidationCode]:
    """Return validation codes."""

    return [
        issue.code
        for issue in result.issues
    ]


def test_validator_accepts_valid_linear_plan() -> None:
    result = PlannerOutputValidator().validate(
        request=request(),
        output=output(
            step(
                step_id="step-1",
                tool_name="python",
            ),
            step(
                step_id="step-2",
                dependencies=["step-1"],
                tool_name="pytest",
            ),
        ),
    )

    assert result.valid is True
    assert result.execution_order == [
        "step-1",
        "step-2",
    ]


def test_validator_rejects_too_many_steps() -> None:
    result = PlannerOutputValidator().validate(
        request=request(maximum_steps=1),
        output=output(
            step(step_id="step-1"),
            step(step_id="step-2"),
        ),
    )

    assert (
        PlannerOutputValidationCode.TOO_MANY_STEPS
        in codes(result)
    )


def test_validator_requires_tool_when_configured() -> None:
    result = PlannerOutputValidator().validate(
        request=request(
            require_tool_for_each_step=True
        ),
        output=output(
            step(step_id="step-1")
        ),
    )

    assert (
        PlannerOutputValidationCode.TOOL_REQUIRED
        in codes(result)
    )


def test_validator_rejects_unavailable_tool() -> None:
    result = PlannerOutputValidator().validate(
        request=request(),
        output=output(
            step(
                step_id="step-1",
                tool_name="browser",
            )
        ),
    )

    assert (
        PlannerOutputValidationCode.TOOL_NOT_AVAILABLE
        in codes(result)
    )


def test_validator_detects_cycle() -> None:
    result = PlannerOutputValidator().validate(
        request=request(),
        output=output(
            step(
                step_id="step-1",
                dependencies=["step-2"],
            ),
            step(
                step_id="step-2",
                dependencies=["step-1"],
            ),
        ),
    )

    assert result.valid is False
    assert (
        PlannerOutputValidationCode.CIRCULAR_DEPENDENCY
        in codes(result)
    )
    assert result.execution_order == []


def test_validator_rejects_parallel_steps_when_disabled() -> None:
    result = PlannerOutputValidator().validate(
        request=request(
            allow_parallel_steps=False
        ),
        output=output(
            step(step_id="step-1"),
            step(step_id="step-2"),
        ),
    )

    assert (
        PlannerOutputValidationCode
        .PARALLEL_STEPS_NOT_ALLOWED
        in codes(result)
    )


def test_validator_accepts_linear_plan_when_parallel_disabled() -> None:
    result = PlannerOutputValidator().validate(
        request=request(
            allow_parallel_steps=False
        ),
        output=output(
            step(step_id="step-1"),
            step(
                step_id="step-2",
                dependencies=["step-1"],
            ),
        ),
    )

    assert result.valid is True
