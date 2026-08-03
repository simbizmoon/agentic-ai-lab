"""Policy-driven archiving for recorded planning-agent traces."""

from __future__ import annotations

from app.schemas.agent_trace_archive_policy import (
    AgentTraceArchivePolicy,
)
from app.schemas.agent_trace_file import (
    AgentTraceFileWriteRequest,
)
from app.schemas.agent_trace_policy_archive import (
    AgentTracePolicyArchiveResult,
)
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
)
from app.tracing.agent_trace_archive_service import (
    AgentTraceArchiveService,
)
from app.tracing.agent_trace_read_service import (
    AgentTraceReadService,
)


class AgentTracePolicyArchiveService:
    """Archive traces according to configured outcome rules."""

    def __init__(
        self,
        *,
        read_service: AgentTraceReadService,
        archive_service: AgentTraceArchiveService,
        policy: AgentTraceArchivePolicy,
    ) -> None:
        self._read_service = read_service
        self._archive_service = archive_service
        self._policy = policy

    @property
    def read_service(self) -> AgentTraceReadService:
        """Return the configured trace read service."""

        return self._read_service

    @property
    def archive_service(self) -> AgentTraceArchiveService:
        """Return the configured archive service."""

        return self._archive_service

    @property
    def policy(self) -> AgentTraceArchivePolicy:
        """Return the configured archive policy."""

        return self._policy

    def archive(
        self,
        trace_id: str,
    ) -> AgentTracePolicyArchiveResult:
        """Apply the archive policy to one recorded trace."""

        if not trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        summary = self.read_service.summary(trace_id)

        if not self._should_archive(summary.outcome):
            return AgentTracePolicyArchiveResult(
                trace_id=trace_id,
                outcome=summary.outcome,
                archived=False,
                files=[],
                reason=(
                    "Trace outcome is disabled by "
                    "the archive policy."
                ),
            )

        files = [
            self.archive_service.archive(
                trace_id=trace_id,
                format=format,
                request=AgentTraceFileWriteRequest(
                    overwrite=self.policy.overwrite
                ),
            )
            for format in self.policy.formats
        ]

        return AgentTracePolicyArchiveResult(
            trace_id=trace_id,
            outcome=summary.outcome,
            archived=True,
            files=files,
            reason=(
                "Trace archived according to "
                "the configured policy."
            ),
        )

    def _should_archive(
        self,
        outcome: AgentTraceOutcome,
    ) -> bool:
        """Return whether an outcome should be archived."""

        decisions = {
            AgentTraceOutcome.COMPLETED: (
                self.policy.archive_completed
            ),
            AgentTraceOutcome.FAILED: (
                self.policy.archive_failed
            ),
            AgentTraceOutcome.INCOMPLETE: (
                self.policy.archive_incomplete
            ),
        }

        return decisions[outcome]
