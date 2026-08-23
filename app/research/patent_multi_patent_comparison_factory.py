"""Production composition for the explicit patent comparison workflow."""

from __future__ import annotations

from collections.abc import Callable

from openai import OpenAI

from app.config import Settings, load_settings
from app.research.epo_ops_abstract_retriever import EpoOpsAbstractRetriever
from app.research.epo_ops_claims_retriever import EpoOpsClaimsRetriever
from app.research.epo_ops_client import EpoOpsClient
from app.research.epo_ops_patent_runtime import (
    EpoOpsClientFactory,
    EpoOpsConfigLoader,
    load_epo_ops_config,
)
from app.research.openai_patent_claim_element_decomposer import (
    OpenAIPatentClaimElementDecomposer,
)
from app.research.openai_patent_element_evidence_relevance_evaluator import (
    OpenAIPatentElementEvidenceRelevanceEvaluator,
)
from app.research.patent_multi_patent_comparison_acquisition import (
    ExactAbstractRetrieverProtocol,
    ExactClaimsRetrieverProtocol,
    PatentMultiPatentComparisonAcquisition,
)
from app.research.patent_multi_patent_comparison_full_workflow import (
    PatentMultiPatentComparisonFullWorkflow,
    PatentMultiPatentSelectedClaimDecomposition,
    SelectedClaimDecomposerProtocol,
)
from app.research.patent_multi_patent_comparison_workflow import (
    PatentMultiPatentComparisonWorkflow,
)
from app.research.patent_prior_art_evidence_mapping_runtime import (
    PatentElementEvidenceRelevanceEvaluatorProtocol,
    PatentPriorArtEvidenceMappingRuntime,
)
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)
from app.services.openai_client import create_openai_client

OpenAIClientFactory = Callable[[Settings], OpenAI]


def build_openai_epo_patent_multi_patent_comparison_workflow(
    request: PatentMultiPatentComparisonRequest,
    *,
    settings: Settings | None = None,
    openai_client: OpenAI | None = None,
    openai_client_factory: OpenAIClientFactory = create_openai_client,
    epo_config_loader: EpoOpsConfigLoader = load_epo_ops_config,
    epo_client_factory: EpoOpsClientFactory | None = None,
    claims_retriever: ExactClaimsRetrieverProtocol | None = None,
    abstract_retriever: ExactAbstractRetrieverProtocol | None = None,
    claim_decomposer: SelectedClaimDecomposerProtocol | None = None,
    mapping_evaluator: PatentElementEvidenceRelevanceEvaluatorProtocol | None = None,
) -> PatentMultiPatentComparisonFullWorkflow:
    """Build one request-bound workflow while sharing provider clients."""

    if not isinstance(request, PatentMultiPatentComparisonRequest):
        raise TypeError("request must be a PatentMultiPatentComparisonRequest")

    resolved_claims = claims_retriever
    resolved_abstract = abstract_retriever
    if resolved_claims is None or resolved_abstract is None:
        config = epo_config_loader(request.maximum_bytes)
        if config.maximum_response_bytes != request.maximum_bytes:
            raise RuntimeError(
                "EPO OPS config was not bound to comparison request maximum_bytes"
            )
        make_epo_client = epo_client_factory or (
            lambda resolved_config: EpoOpsClient(config=resolved_config)
        )
        epo_client = make_epo_client(config)
        if resolved_claims is None:
            resolved_claims = EpoOpsClaimsRetriever(client=epo_client)
        if resolved_abstract is None:
            resolved_abstract = EpoOpsAbstractRetriever(client=epo_client)

    resolved_decomposer = claim_decomposer
    resolved_evaluator = mapping_evaluator
    if resolved_decomposer is None or resolved_evaluator is None:
        resolved_settings = settings or load_settings()
        resolved_openai_client = openai_client or openai_client_factory(
            resolved_settings
        )
        if resolved_decomposer is None:
            resolved_decomposer = OpenAIPatentClaimElementDecomposer(
                client=resolved_openai_client,
                model=resolved_settings.openai_model,
            )
        if resolved_evaluator is None:
            resolved_evaluator = OpenAIPatentElementEvidenceRelevanceEvaluator(
                client=resolved_openai_client,
                model=resolved_settings.openai_model,
            )

    return PatentMultiPatentComparisonFullWorkflow(
        acquisition=PatentMultiPatentComparisonAcquisition(
            claims_retriever=resolved_claims,
            abstract_retriever=resolved_abstract,
        ),
        selected_decomposition=PatentMultiPatentSelectedClaimDecomposition(
            claim_decomposer=resolved_decomposer,
        ),
        downstream_workflow=PatentMultiPatentComparisonWorkflow(
            mapping_runtime=PatentPriorArtEvidenceMappingRuntime(
                evaluator=resolved_evaluator,
            ),
        ),
    )
