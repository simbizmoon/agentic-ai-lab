"""Composition root for the leakage-safe Stage 9 development runtime."""

from __future__ import annotations

from dataclasses import dataclass

from app.research.stage9_acquisition_aware_research_loop import (
    Stage9AcquisitionAwareResearchLoop,
    Stage9PackedResearchLoopFactory,
)
from app.research.stage9_development_acquisition_router import (
    Stage9AcquisitionChannelProvider,
    Stage9DevelopmentAcquisitionRouter,
)
from app.schemas.stage9_baseline_runtime_stack import Stage9LockedBaselineExperiment
from app.schemas.stage9_development_acquisition import Stage9AcquisitionChannel


@dataclass(frozen=True)
class Stage9DevelopmentRuntime:
    """Exact components used by one development-only baseline runtime."""

    acquisition_router: Stage9DevelopmentAcquisitionRouter
    research_loop: Stage9AcquisitionAwareResearchLoop


def create_stage9_development_runtime(
    *,
    experiment: Stage9LockedBaselineExperiment,
    official_web: Stage9AcquisitionChannelProvider,
    scholarly_primary: Stage9AcquisitionChannelProvider,
    epo_patent: Stage9AcquisitionChannelProvider,
    local_repository: Stage9AcquisitionChannelProvider,
    packed_loop_factory: Stage9PackedResearchLoopFactory,
) -> Stage9DevelopmentRuntime:
    """Bind every locked acquisition channel to the acquisition-aware loop."""

    if not isinstance(experiment, Stage9LockedBaselineExperiment):
        raise TypeError("experiment must be a locked Stage 9 experiment")
    providers = {
        Stage9AcquisitionChannel.OFFICIAL_WEB: official_web,
        Stage9AcquisitionChannel.SCHOLARLY_PRIMARY: scholarly_primary,
        Stage9AcquisitionChannel.EPO_PATENT: epo_patent,
        Stage9AcquisitionChannel.LOCAL_REPOSITORY: local_repository,
    }
    for channel, provider in providers.items():
        acquire = getattr(provider, "acquire", None)
        if not callable(acquire):
            raise TypeError(f"{channel.value} provider must expose acquire")

    router = Stage9DevelopmentAcquisitionRouter(providers=providers)
    loop = Stage9AcquisitionAwareResearchLoop(
        experiment=experiment,
        acquisition_router=router,
        loop_factory=packed_loop_factory,
    )
    return Stage9DevelopmentRuntime(
        acquisition_router=router,
        research_loop=loop,
    )
