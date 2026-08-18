"""Runtime composition for bounded EPO OPS patent plan execution."""

from __future__ import annotations

import os
from collections.abc import Callable

from dotenv import load_dotenv
from pydantic import SecretStr

from app.research.epo_ops_abstract_retriever import EpoOpsAbstractRetriever
from app.research.epo_ops_bibliographic_searcher import EpoOpsBibliographicSearcher
from app.research.epo_ops_client import EpoOpsClient
from app.research.patent_research_handler import PatentResearchHandler
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
    PatentResearchPlanExecutor,
)
from app.schemas.epo_ops_config import EpoOpsConfig
from app.schemas.patent_search_query import PatentSearchQueryPlan

EPO_OPS_CONSUMER_KEY_ENV = "EPO_OPS_CONSUMER_KEY"
EPO_OPS_CONSUMER_SECRET_ENV = "EPO_OPS_CONSUMER_SECRET"

EpoOpsConfigLoader = Callable[[int], EpoOpsConfig]
EpoOpsClientFactory = Callable[[EpoOpsConfig], EpoOpsClient]
EpoOpsSearcherFactory = Callable[[EpoOpsClient], EpoOpsBibliographicSearcher]
EpoOpsAbstractRetrieverFactory = Callable[[EpoOpsClient], EpoOpsAbstractRetriever]


def load_epo_ops_config(maximum_response_bytes: int) -> EpoOpsConfig:
    """Load EPO credentials and bind one request-specific response byte limit."""

    load_dotenv()

    consumer_key = os.getenv(EPO_OPS_CONSUMER_KEY_ENV, "").strip()
    consumer_secret = os.getenv(EPO_OPS_CONSUMER_SECRET_ENV, "").strip()

    if not consumer_key:
        raise RuntimeError(f"{EPO_OPS_CONSUMER_KEY_ENV} is required")
    if not consumer_secret:
        raise RuntimeError(f"{EPO_OPS_CONSUMER_SECRET_ENV} is required")

    return EpoOpsConfig(
        consumer_key=SecretStr(consumer_key),
        consumer_secret=SecretStr(consumer_secret),
        maximum_response_bytes=maximum_response_bytes,
    )


class EpoOpsPatentRuntime:
    """Compose one request-bound EPO OPS execution without legal synthesis."""

    def __init__(
        self,
        *,
        config_loader: EpoOpsConfigLoader | None = None,
        client_factory: EpoOpsClientFactory | None = None,
        searcher_factory: EpoOpsSearcherFactory | None = None,
        abstract_retriever_factory: EpoOpsAbstractRetrieverFactory | None = None,
    ) -> None:
        self._config_loader = config_loader or load_epo_ops_config
        self._client_factory = client_factory or (
            lambda config: EpoOpsClient(config=config)
        )
        self._searcher_factory = searcher_factory or (
            lambda client: EpoOpsBibliographicSearcher(client=client)
        )
        self._abstract_retriever_factory = abstract_retriever_factory or (
            lambda client: EpoOpsAbstractRetriever(client=client)
        )

    def execute(
        self,
        plan: PatentSearchQueryPlan,
    ) -> PatentResearchPlanExecutionResult:
        """Bind the plan request to transport configuration and execute it."""

        config = self._config_loader(plan.request.maximum_bytes)
        if config.maximum_response_bytes != plan.request.maximum_bytes:
            raise RuntimeError(
                "EPO OPS config was not bound to the patent request maximum_bytes"
            )

        client = self._client_factory(config)
        handler = PatentResearchHandler(
            searcher=self._searcher_factory(client),
            abstract_retriever=self._abstract_retriever_factory(client),
        )
        return PatentResearchPlanExecutor(handler=handler).execute(plan)
