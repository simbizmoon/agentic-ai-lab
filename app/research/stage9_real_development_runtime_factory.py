"""Secret-safe composition of Stage 9 real acquisition providers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import httpx

from app.research.bounded_scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflow,
)
from app.research.epo_ops_claims_retriever import EpoOpsClaimsRetriever
from app.research.epo_ops_client import EpoOpsClient
from app.research.openalex_scholarly_metadata_provider import (
    OpenAlexScholarlyMetadataProvider,
)
from app.research.stage9_development_acquisition_router import (
    Stage9AcquisitionChannelProvider,
)
from app.research.stage9_development_runtime_factory import (
    Stage9DevelopmentRuntime,
    Stage9PackedResearchLoopFactory,
    create_stage9_development_runtime,
)
from app.research.stage9_local_repository_acquisition_adapter import (
    Stage9LocalRepositoryAcquisitionAdapter,
)
from app.research.stage9_official_web_acquisition_adapter import (
    Stage9OfficialWebAcquisitionAdapter,
)
from app.research.stage9_patent_acquisition_adapter import (
    Stage9PatentAcquisitionAdapter,
)
from app.research.stage9_real_provider_binding_preflight import (
    EPO_CONSUMER_KEY_ENV,
    EPO_CONSUMER_SECRET_ENV,
    TAVILY_API_KEY_ENV,
)
from app.research.stage9_scholarly_acquisition_adapter import (
    Stage9ScholarlyAcquisitionAdapter,
)
from app.research.stage9_tavily_official_web_provider import (
    Stage9TavilyOfficialWebProvider,
)
from app.schemas.epo_ops_config import EpoOpsConfig
from app.schemas.stage9_baseline_runtime_stack import Stage9LockedBaselineExperiment


class Stage9RealDevelopmentRuntimeFactoryError(RuntimeError):
    """The real acquisition runtime could not be safely composed."""


def create_stage9_real_development_runtime(
    *,
    experiment: Stage9LockedBaselineExperiment,
    environ: Mapping[str, str],
    repository_root: Path,
    packed_loop_factory: Stage9PackedResearchLoopFactory,
    official_web: Stage9AcquisitionChannelProvider | None = None,
    tavily_client: httpx.Client | None = None,
    openalex_client: httpx.Client | None = None,
    epo_client: httpx.Client | None = None,
) -> Stage9DevelopmentRuntime:
    """Compose real provider bindings without executing any provider request."""

    required_names = [EPO_CONSUMER_KEY_ENV, EPO_CONSUMER_SECRET_ENV]
    if official_web is None:
        required_names.append(TAVILY_API_KEY_ENV)
    values = {name: environ.get(name, "").strip() for name in required_names}
    missing = tuple(name for name, value in values.items() if not value)
    if missing:
        raise Stage9RealDevelopmentRuntimeFactoryError(
            "missing acquisition credentials: " + ", ".join(missing)
        )

    root = repository_root.resolve(strict=True)
    if not root.is_dir():
        raise Stage9RealDevelopmentRuntimeFactoryError(
            "repository_root must be a directory"
        )

    if official_web is None:
        official_web = Stage9OfficialWebAcquisitionAdapter(
            provider=Stage9TavilyOfficialWebProvider(
                api_key=values[TAVILY_API_KEY_ENV],
                client=tavily_client,
            )
        )
    scholarly_primary = Stage9ScholarlyAcquisitionAdapter(
        workflow=BoundedScholarlyEvidenceWorkflow(
            provider=OpenAlexScholarlyMetadataProvider(client=openalex_client)
        )
    )
    epo_patent = Stage9PatentAcquisitionAdapter(
        claims_retriever=EpoOpsClaimsRetriever(
            client=EpoOpsClient(
                config=EpoOpsConfig(
                    consumer_key=values[EPO_CONSUMER_KEY_ENV],
                    consumer_secret=values[EPO_CONSUMER_SECRET_ENV],
                ),
                client=epo_client,
            )
        )
    )
    local_repository = Stage9LocalRepositoryAcquisitionAdapter(repository_root=root)
    return create_stage9_development_runtime(
        experiment=experiment,
        official_web=official_web,
        scholarly_primary=scholarly_primary,
        epo_patent=epo_patent,
        local_repository=local_repository,
        packed_loop_factory=packed_loop_factory,
    )
