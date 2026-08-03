"""End-to-end retrieval and prompt composition for agent memory."""

from __future__ import annotations

from app.memory.memory_prompt_composer import (
    MemoryPromptComposer,
)
from app.memory.memory_retrieval_service import (
    MemoryRetrievalService,
)
from app.schemas.agent_memory_pipeline import (
    AgentMemoryPipelineRequest,
)
from app.schemas.agent_memory_pipeline_result import (
    AgentMemoryPipelineResult,
)


class AgentMemoryPipeline:
    """Retrieve relevant memories and compose an agent prompt."""

    def __init__(
        self,
        *,
        retrieval_service: MemoryRetrievalService,
        prompt_composer: MemoryPromptComposer | None = None,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._prompt_composer = (
            prompt_composer or MemoryPromptComposer()
        )

    @property
    def retrieval_service(
        self,
    ) -> MemoryRetrievalService:
        """Return the configured retrieval service."""

        return self._retrieval_service

    @property
    def prompt_composer(
        self,
    ) -> MemoryPromptComposer:
        """Return the configured prompt composer."""

        return self._prompt_composer

    def run(
        self,
        request: AgentMemoryPipelineRequest,
    ) -> AgentMemoryPipelineResult:
        """Run memory retrieval and prompt composition."""

        retrieval = self.retrieval_service.retrieve(
            request.retrieval
        )

        prompt = self.prompt_composer.compose(
            system_instructions=(
                request.system_instructions
            ),
            user_query=request.user_query,
            retrieval=retrieval,
        )

        return AgentMemoryPipelineResult(
            retrieval=retrieval,
            prompt=prompt,
        )
