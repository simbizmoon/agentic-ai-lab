"""EPO OPS composition for companion patent-claims acquisition."""

from __future__ import annotations

from collections.abc import Callable

from app.research.epo_ops_claims_retriever import EpoOpsClaimsRetriever
from app.research.epo_ops_client import EpoOpsClient
from app.research.epo_ops_patent_runtime import (
    EpoOpsClientFactory,
    EpoOpsConfigLoader,
    load_epo_ops_config,
)
from app.research.patent_claims_runtime import (
    PatentClaimsRuntime,
    PatentClaimsRuntimeResult,
)
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)

EpoOpsClaimsRetrieverFactory = Callable[[EpoOpsClient], EpoOpsClaimsRetriever]


class EpoOpsPatentClaimsRuntime:
    """Build one request-bound OPS client and acquire claims post-execution."""

    def __init__(
        self,
        *,
        config_loader: EpoOpsConfigLoader | None = None,
        client_factory: EpoOpsClientFactory | None = None,
        claims_retriever_factory: EpoOpsClaimsRetrieverFactory | None = None,
    ) -> None:
        self._config_loader = config_loader or load_epo_ops_config
        self._client_factory = client_factory or (
            lambda config: EpoOpsClient(config=config)
        )
        self._claims_retriever_factory = claims_retriever_factory or (
            lambda client: EpoOpsClaimsRetriever(client=client)
        )

    def enrich(
        self,
        execution: PatentResearchPlanExecutionResult,
    ) -> PatentClaimsRuntimeResult:
        """Acquire claims with the same response-byte bound as the source request."""

        maximum_bytes = execution.collection.request.maximum_bytes
        config = self._config_loader(maximum_bytes)
        if config.maximum_response_bytes != maximum_bytes:
            raise RuntimeError(
                "EPO OPS claims config was not bound to the patent request maximum_bytes"
            )

        client = self._client_factory(config)
        runtime = PatentClaimsRuntime(
            claims_retriever=self._claims_retriever_factory(client),
        )
        return runtime.enrich(execution)
