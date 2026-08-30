"""Secret-safe preflight for the Stage 9 development live-provider binding."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.stage9_baseline_runtime_stack import (
    Stage9LockedBaselineExperiment,
    Stage9RuntimeComponentRole,
)
from app.schemas.stage9_development_baseline_run import STAGE9_DEVELOPMENT_CASE_IDS

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
TAVILY_API_KEY_ENV = "TAVILY_API_KEY"
EPO_CONSUMER_KEY_ENV = "EPO_OPS_CONSUMER_KEY"
EPO_CONSUMER_SECRET_ENV = "EPO_OPS_CONSUMER_SECRET"
REQUIRED_SECRET_ENV_NAMES = (
    OPENAI_API_KEY_ENV,
    TAVILY_API_KEY_ENV,
    EPO_CONSUMER_KEY_ENV,
    EPO_CONSUMER_SECRET_ENV,
)

DEVELOPMENT_MAXIMUM_PROVIDER_REQUESTS = 16
DEVELOPMENT_MAXIMUM_EXTERNAL_REQUESTS = 24
DEVELOPMENT_MAXIMUM_ESTIMATED_COST = Decimal("1.50")
CONSERVATIVE_ACQUISITION_EXTERNAL_REQUESTS = 5
_MAXIMUM_ROADMAP_BYTES = 512_000


class Stage9ProviderPreflightStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class Stage9RealProviderPreflightResult(BaseModel):
    """Only presence and bounded configuration; no secret values are retained."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    status: Stage9ProviderPreflightStatus
    missing_environment_names: tuple[str, ...]
    planned_case_ids: tuple[str, ...]
    maximum_provider_requests: int = Field(ge=1)
    maximum_external_requests: int = Field(ge=1)
    conservative_acquisition_external_requests: int = Field(ge=0)
    maximum_estimated_cost: Decimal = Field(ge=Decimal(0))
    currency: str = Field(pattern=r"^USD$")
    repository_roadmap_ready: bool
    openalex_credential_required: bool
    paid_execution_started: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        blocked = (
            bool(self.missing_environment_names) or not self.repository_roadmap_ready
        )
        expected = (
            Stage9ProviderPreflightStatus.BLOCKED
            if blocked
            else Stage9ProviderPreflightStatus.READY
        )
        if self.status is not expected:
            raise ValueError("preflight status must match missing prerequisites")
        if self.paid_execution_started:
            raise ValueError("preflight must not start paid execution")
        if self.openalex_credential_required:
            raise ValueError(
                "current bounded OpenAlex metadata path is unauthenticated"
            )
        if len(set(self.missing_environment_names)) != len(
            self.missing_environment_names
        ):
            raise ValueError("missing environment names must be unique")
        return self


class Stage9RealProviderBindingPreflight:
    """Validate credentials, locked models, repository, and phase ceilings offline."""

    def check(
        self,
        *,
        experiment: Stage9LockedBaselineExperiment,
        environ: Mapping[str, str],
        repository_root: Path,
    ) -> Stage9RealProviderPreflightResult:
        if not isinstance(experiment, Stage9LockedBaselineExperiment):
            raise TypeError("experiment must be a locked Stage 9 experiment")
        self._validate_runtime_stack(experiment)
        self._validate_development_partition(experiment)
        missing = tuple(
            name
            for name in REQUIRED_SECRET_ENV_NAMES
            if not environ.get(name, "").strip()
        )
        roadmap_ready = self._roadmap_ready(repository_root)
        status = (
            Stage9ProviderPreflightStatus.BLOCKED
            if missing or not roadmap_ready
            else Stage9ProviderPreflightStatus.READY
        )
        return Stage9RealProviderPreflightResult(
            status=status,
            missing_environment_names=missing,
            planned_case_ids=STAGE9_DEVELOPMENT_CASE_IDS,
            maximum_provider_requests=DEVELOPMENT_MAXIMUM_PROVIDER_REQUESTS,
            maximum_external_requests=DEVELOPMENT_MAXIMUM_EXTERNAL_REQUESTS,
            conservative_acquisition_external_requests=(
                CONSERVATIVE_ACQUISITION_EXTERNAL_REQUESTS
            ),
            maximum_estimated_cost=DEVELOPMENT_MAXIMUM_ESTIMATED_COST,
            currency="USD",
            repository_roadmap_ready=roadmap_ready,
            openalex_credential_required=False,
            paid_execution_started=False,
        )

    @staticmethod
    def _validate_runtime_stack(experiment: Stage9LockedBaselineExperiment) -> None:
        expected = {
            Stage9RuntimeComponentRole.PLANNER: "responses.create",
            Stage9RuntimeComponentRole.GROUNDED_ANSWER_GENERATOR: "responses.create",
            Stage9RuntimeComponentRole.CITATION_EVALUATOR: "responses.parse",
        }
        for role, operation in expected.items():
            component = experiment.runtime_stack.component(role)
            if component.provider_name.casefold() != "openai":
                raise ValueError("Stage 9 locked runtime requires OpenAI components")
            if component.operation != operation:
                raise ValueError("Stage 9 locked runtime operation changed")
            if component.model_name != experiment.plan.manifest.model_name:
                raise ValueError("runtime component model differs from the manifest")

    @staticmethod
    def _validate_development_partition(
        experiment: Stage9LockedBaselineExperiment,
    ) -> None:
        if experiment.plan.development_case_ids != STAGE9_DEVELOPMENT_CASE_IDS:
            raise ValueError("development partition differs from the approved lock")
        if len(experiment.plan.blind_holdout_case_ids) != 6:
            raise ValueError("blind holdout partition differs from the approved lock")

    @staticmethod
    def _roadmap_ready(repository_root: Path) -> bool:
        try:
            root = repository_root.resolve(strict=True)
            path = root / "ROADMAP.md"
            if path.is_symlink():
                return False
            resolved = path.resolve(strict=True)
            return (
                root.is_dir()
                and resolved.parent == root
                and resolved.is_file()
                and 0 < resolved.stat().st_size <= _MAXIMUM_ROADMAP_BYTES
            )
        except OSError:
            return False
