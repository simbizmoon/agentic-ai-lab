"""Safe persistence for one Stage 9 development baseline case."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopResult,
    ResearchAgentLoopDecision,
)
from app.schemas.provider_cost import CostKind
from app.schemas.stage9_development_baseline_run import (
    STAGE9_DEVELOPMENT_CASE_IDS,
    Stage9DevelopmentCaseRecord,
    Stage9DevelopmentCaseStatus,
    Stage9DevelopmentCaseUsage,
)

ARTIFACT_VERSION = "stage9-development-case-artifact-v1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class Stage9DevelopmentCaseArtifactError(RuntimeError):
    """The case artifact could not be persisted without weakening safety."""


class Stage9DevelopmentCaseArtifact(BaseModel):
    """Typed, exact payload stored for later human evaluation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    artifact_version: str = Field(pattern=r"^stage9-development-case-artifact-v1$")
    case_id: str
    execution_id: str
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_model_ids: tuple[str, ...] = Field(min_length=1, max_length=32)
    estimated_cost: Decimal = Field(ge=Decimal(0), le=Decimal("1.50"))
    currency: str = Field(pattern=r"^USD$")
    cost_kind: CostKind
    loop_result: BoundedResearchAgentLoopResult

    @model_validator(mode="after")
    def validate_identity_and_authority(self) -> Stage9DevelopmentCaseArtifact:
        if self.case_id not in STAGE9_DEVELOPMENT_CASE_IDS:
            raise ValueError("artifact case must belong to the development partition")
        if not _SAFE_ID.fullmatch(self.execution_id):
            raise ValueError("execution ID is not filesystem-safe")
        if any(
            not value.strip() or value != value.strip()
            for value in self.response_model_ids
        ):
            raise ValueError("response model IDs must be normalized and nonblank")
        if self.cost_kind is not CostKind.ESTIMATED:
            raise ValueError("artifact cost must retain estimated authority")
        if not self.estimated_cost.is_finite():
            raise ValueError("estimated cost must be finite")
        return self


def _case_status(decision: ResearchAgentLoopDecision) -> Stage9DevelopmentCaseStatus:
    return {
        ResearchAgentLoopDecision.GOAL_ACHIEVED: (
            Stage9DevelopmentCaseStatus.ANSWER_AVAILABLE
        ),
        ResearchAgentLoopDecision.ABSTAIN: Stage9DevelopmentCaseStatus.ABSTAINED,
        ResearchAgentLoopDecision.BUDGET_EXHAUSTED: (
            Stage9DevelopmentCaseStatus.INCOMPLETE
        ),
        ResearchAgentLoopDecision.HUMAN_REVIEW: Stage9DevelopmentCaseStatus.FAILED,
        ResearchAgentLoopDecision.TERMINAL_FAILURE: (
            Stage9DevelopmentCaseStatus.FAILED
        ),
        ResearchAgentLoopDecision.REPLAN: Stage9DevelopmentCaseStatus.INCOMPLETE,
    }[decision]


def _canonical_json(artifact: Stage9DevelopmentCaseArtifact) -> bytes:
    return (
        json.dumps(
            artifact.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


class Stage9DevelopmentCaseArtifactWriter:
    """Write one immutable case directory and return its runner record."""

    def __init__(self, output_directory: Path) -> None:
        self._output_directory = Path(output_directory)

    def write(
        self,
        *,
        case_id: str,
        execution_id: str,
        manifest_sha256: str,
        review_sha256: str,
        response_model_ids: tuple[str, ...],
        estimated_cost: Decimal,
        loop_result: BoundedResearchAgentLoopResult,
    ) -> Stage9DevelopmentCaseRecord:
        if not isinstance(loop_result, BoundedResearchAgentLoopResult):
            raise TypeError("loop_result must be a BoundedResearchAgentLoopResult")
        artifact = Stage9DevelopmentCaseArtifact(
            artifact_version=ARTIFACT_VERSION,
            case_id=case_id,
            execution_id=execution_id,
            manifest_sha256=manifest_sha256,
            review_sha256=review_sha256,
            response_model_ids=response_model_ids,
            estimated_cost=estimated_cost,
            currency="USD",
            cost_kind=CostKind.ESTIMATED,
            loop_result=loop_result,
        )
        payload = _canonical_json(artifact)
        checksum = hashlib.sha256(payload).hexdigest()
        final_directory = self._output_directory / case_id / execution_id
        temporary_directory = final_directory.with_name(f".{execution_id}.tmp")

        self._validate_destination(final_directory, temporary_directory)
        try:
            temporary_directory.mkdir(parents=True, mode=0o700)
            os.chmod(temporary_directory, 0o700)
            artifact_path = temporary_directory / "workflow.json"
            checksum_path = temporary_directory / "workflow.json.sha256"
            self._write_private(artifact_path, payload)
            self._write_private(checksum_path, f"{checksum}  workflow.json\n".encode())
            loaded = Stage9DevelopmentCaseArtifact.model_validate_json(
                artifact_path.read_bytes()
            )
            if loaded != artifact:
                raise Stage9DevelopmentCaseArtifactError(
                    "typed artifact round-trip changed the payload"
                )
            temporary_directory.rename(final_directory)
        except (OSError, TypeError, ValueError, Stage9DevelopmentCaseArtifactError):
            if temporary_directory.exists() and not temporary_directory.is_symlink():
                shutil.rmtree(temporary_directory)
            raise

        final_artifact_path = final_directory / "workflow.json"
        usage = loop_result.usage
        return Stage9DevelopmentCaseRecord(
            case_id=case_id,
            execution_id=execution_id,
            status=_case_status(loop_result.final_decision),
            workflow_artifact_path=str(final_artifact_path.resolve()),
            workflow_artifact_sha256=checksum,
            response_model_ids=response_model_ids,
            usage=Stage9DevelopmentCaseUsage(
                provider_requests=usage.provider_calls,
                external_requests=usage.external_requests,
                recorded_tokens=usage.recorded_tokens,
                elapsed_seconds=usage.elapsed_seconds,
                estimated_cost=estimated_cost,
                currency="USD",
                cost_kind=CostKind.ESTIMATED,
            ),
        )

    def _validate_destination(
        self, final_directory: Path, temporary_directory: Path
    ) -> None:
        if self._output_directory.exists() and self._output_directory.is_symlink():
            raise Stage9DevelopmentCaseArtifactError(
                "output directory must not be a symbolic link"
            )
        case_directory = final_directory.parent
        if case_directory.exists() and case_directory.is_symlink():
            raise Stage9DevelopmentCaseArtifactError(
                "case directory must not be a symbolic link"
            )
        if final_directory.exists() or final_directory.is_symlink():
            raise Stage9DevelopmentCaseArtifactError(
                "case execution artifact already exists"
            )
        if temporary_directory.exists() or temporary_directory.is_symlink():
            raise Stage9DevelopmentCaseArtifactError(
                "temporary case artifact already exists"
            )

    @staticmethod
    def _write_private(path: Path, payload: bytes) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
