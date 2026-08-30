"""Compose the approved Stage 9 development runner without executing it."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.evals.stage9_bounded_development_baseline_runner import (
    BoundedStage9DevelopmentBaselineRunner,
)
from app.evals.stage9_conservative_cost_estimator import (
    ConservativeStage9RecordedTokenCostEstimator,
)
from app.evals.stage9_development_case_artifact_writer import (
    Stage9DevelopmentCaseArtifactWriter,
)
from app.evals.stage9_development_case_executor import (
    ResearchAgentLoopProtocol,
    Stage9DevelopmentCaseExecutorAdapter,
)
from app.schemas.stage9_baseline_runtime_stack import Stage9LockedBaselineExperiment
from app.schemas.stage9_development_baseline_run import (
    STAGE9_DEVELOPMENT_CASE_IDS,
    Stage9DevelopmentRunBudget,
    Stage9DevelopmentRunRequest,
)

APPROVED_MANIFEST_SHA256 = (
    "60179543f5290136d434d4f4c72598af8f74eb569a1d06b43c7490320d81e191"
)
APPROVED_REVIEW_SHA256 = (
    "f36c0b7bee7cc9548f2f3a36946e4b49293883b69349b4499f2c80d27190cae7"
)
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class Stage9DevelopmentExecutionBundle:
    """The exact request and runner awaiting explicit paid-run authorization."""

    request: Stage9DevelopmentRunRequest
    runner: BoundedStage9DevelopmentBaselineRunner


def create_stage9_development_execution_bundle(
    *,
    experiment: Stage9LockedBaselineExperiment,
    research_loop: ResearchAgentLoopProtocol,
    output_directory: Path,
    run_id: str,
) -> Stage9DevelopmentExecutionBundle:
    """Bind the locked development partition and ceilings without running it."""

    if not isinstance(experiment, Stage9LockedBaselineExperiment):
        raise TypeError("experiment must be a locked Stage 9 experiment")
    if not callable(getattr(research_loop, "run", None)):
        raise TypeError("research_loop must expose run")
    if not _SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("run_id must be filesystem-safe")

    destination = Path(output_directory)
    if destination.exists() and destination.is_symlink():
        raise ValueError("output directory must not be a symbolic link")

    request = Stage9DevelopmentRunRequest(
        run_id=run_id,
        manifest_sha256=APPROVED_MANIFEST_SHA256,
        review_sha256=APPROVED_REVIEW_SHA256,
        case_ids=STAGE9_DEVELOPMENT_CASE_IDS,
        repetitions_per_case=1,
        budget=Stage9DevelopmentRunBudget(
            maximum_provider_requests=16,
            maximum_external_requests=24,
            maximum_recorded_tokens=120_000,
            maximum_elapsed_seconds=2_880.0,
            maximum_estimated_cost=Decimal("1.50"),
            currency="USD",
        ),
    )
    executor = Stage9DevelopmentCaseExecutorAdapter(
        experiment=experiment,
        research_loop=research_loop,
        cost_estimator=ConservativeStage9RecordedTokenCostEstimator(),
        artifact_writer=Stage9DevelopmentCaseArtifactWriter(destination),
    )
    return Stage9DevelopmentExecutionBundle(
        request=request,
        runner=BoundedStage9DevelopmentBaselineRunner(
            experiment=experiment,
            executor=executor,
        ),
    )
