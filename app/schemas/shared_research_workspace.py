"""Shared workspace schema for multi-agent research collaboration."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_agent import ResearchAgentIdentity
from app.schemas.research_agent_assignment import (
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_message import (
    ResearchAgentMessage,
)
from app.schemas.research_agent_result import (
    ResearchAgentTaskResult,
)
from app.schemas.research_workspace import ResearchWorkspace


class SharedResearchWorkspaceStatus(StrEnum):
    """Overall collaboration status of a shared workspace."""

    CREATED = "created"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    REVIEWING = "reviewing"
    REVISING = "revising"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SharedResearchWorkspace(BaseModel):
    """Immutable multi-agent state layered over a research workspace."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    shared_workspace_id: str
    research_workspace: ResearchWorkspace
    status: SharedResearchWorkspaceStatus = (
        SharedResearchWorkspaceStatus.CREATED
    )
    agents: list[ResearchAgentIdentity] = Field(
        min_length=1
    )
    assignments: list[
        ResearchAgentTaskAssignment
    ] = Field(default_factory=list)
    results: list[ResearchAgentTaskResult] = Field(
        default_factory=list
    )
    messages: list[ResearchAgentMessage] = Field(
        default_factory=list
    )
    active_assignment_ids: list[str] = Field(
        default_factory=list
    )
    revision_count: int = Field(
        default=0,
        ge=0,
    )
    maximum_revisions: int = Field(
        default=2,
        ge=0,
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_shared_workspace(self) -> Self:
        """Validate collaboration identity and references."""

        if not self.shared_workspace_id.strip():
            raise ValueError(
                "shared_workspace_id must not be blank"
            )

        self._validate_agents()
        assignment_by_id = self._validate_assignments()
        self._validate_results(assignment_by_id)
        self._validate_messages()
        self._validate_active_assignments(
            assignment_by_id
        )
        self._validate_revision_limits()
        self._validate_status_semantics()
        self._validate_metadata()

        return self

    def _validate_agents(self) -> None:
        """Validate unique registered agent identities."""

        agent_ids = [
            agent.agent_id.strip().casefold()
            for agent in self.agents
        ]

        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError(
                "agent IDs must be unique"
            )

    def _validate_assignments(
        self,
    ) -> dict[str, ResearchAgentTaskAssignment]:
        """Validate assignments and return them by normalized ID."""

        assignment_by_id: dict[
            str,
            ResearchAgentTaskAssignment,
        ] = {}

        registered_agent_ids = {
            agent.agent_id.strip().casefold()
            for agent in self.agents
        }

        request_id = (
            self.research_workspace.request.request_id
        )
        workspace_id = (
            self.research_workspace.workspace_id
        )

        for assignment in self.assignments:
            assignment_key = (
                assignment.assignment_id
                .strip()
                .casefold()
            )

            if assignment_key in assignment_by_id:
                raise ValueError(
                    "assignment IDs must be unique"
                )

            if assignment.request_id != request_id:
                raise ValueError(
                    "assignment request_id must match "
                    "research workspace"
                )

            if assignment.workspace_id != workspace_id:
                raise ValueError(
                    "assignment workspace_id must match "
                    "research workspace"
                )

            assignee_id = (
                assignment.assignee.agent_id
                .strip()
                .casefold()
            )

            if assignee_id not in registered_agent_ids:
                raise ValueError(
                    "assignment assignee must be "
                    "a registered agent"
                )

            assigner_id = (
                assignment.assigner_profile.agent.agent_id
                .strip()
                .casefold()
            )

            if assigner_id not in registered_agent_ids:
                raise ValueError(
                    "assignment assigner must be "
                    "a registered agent"
                )

            assignment_by_id[assignment_key] = assignment

        return assignment_by_id

    def _validate_results(
        self,
        assignment_by_id: dict[
            str,
            ResearchAgentTaskAssignment,
        ],
    ) -> None:
        """Validate result identity and assignment references."""

        result_ids: set[str] = set()

        for result in self.results:
            result_key = result.result_id.strip().casefold()

            if result_key in result_ids:
                raise ValueError(
                    "result IDs must be unique"
                )

            result_ids.add(result_key)

            assignment_key = (
                result.assignment.assignment_id
                .strip()
                .casefold()
            )

            stored_assignment = assignment_by_id.get(
                assignment_key
            )

            if stored_assignment is None:
                raise ValueError(
                    "result must reference a registered assignment"
                )

            if result.assignment != stored_assignment:
                raise ValueError(
                    "result assignment must match "
                    "the registered assignment"
                )

    def _validate_messages(self) -> None:
        """Validate message identity and registered agents."""

        message_ids: set[str] = set()

        registered_agent_ids = {
            agent.agent_id.strip().casefold()
            for agent in self.agents
        }

        request_id = (
            self.research_workspace.request.request_id
        )
        workspace_id = (
            self.research_workspace.workspace_id
        )

        for message in self.messages:
            message_key = (
                message.message_id.strip().casefold()
            )

            if message_key in message_ids:
                raise ValueError(
                    "message IDs must be unique"
                )

            message_ids.add(message_key)

            sender_id = (
                message.sender.agent_id
                .strip()
                .casefold()
            )

            if sender_id not in registered_agent_ids:
                raise ValueError(
                    "message sender must be a registered agent"
                )

            if message.recipient is not None:
                recipient_id = (
                    message.recipient.agent_id
                    .strip()
                    .casefold()
                )

                if recipient_id not in registered_agent_ids:
                    raise ValueError(
                        "message recipient must be "
                        "a registered agent"
                    )

            if message.request_id != request_id:
                raise ValueError(
                    "message request_id must match "
                    "research workspace"
                )

            if message.workspace_id != workspace_id:
                raise ValueError(
                    "message workspace_id must match "
                    "research workspace"
                )

    def _validate_active_assignments(
        self,
        assignment_by_id: dict[
            str,
            ResearchAgentTaskAssignment,
        ],
    ) -> None:
        """Validate active assignment references."""

        normalized_ids = [
            assignment_id.strip().casefold()
            for assignment_id
            in self.active_assignment_ids
        ]

        if any(
            not assignment_id.strip()
            for assignment_id
            in self.active_assignment_ids
        ):
            raise ValueError(
                "active_assignment_ids must not "
                "contain blank values"
            )

        if len(set(normalized_ids)) != len(
            normalized_ids
        ):
            raise ValueError(
                "active_assignment_ids must not "
                "contain duplicates"
            )

        for assignment_id in normalized_ids:
            assignment = assignment_by_id.get(
                assignment_id
            )

            if assignment is None:
                raise ValueError(
                    "active assignment must reference "
                    "a registered assignment"
                )

            if assignment.is_terminal:
                raise ValueError(
                    "terminal assignment must not be active"
                )

    def _validate_revision_limits(self) -> None:
        """Validate bounded revision count."""

        if self.revision_count > self.maximum_revisions:
            raise ValueError(
                "revision_count must not exceed "
                "maximum_revisions"
            )

    def _validate_status_semantics(self) -> None:
        """Validate workspace status against active work."""

        if (
            self.status
            is SharedResearchWorkspaceStatus.COMPLETED
            and self.active_assignment_ids
        ):
            raise ValueError(
                "completed workspace must not have "
                "active assignments"
            )

        if (
            self.status
            in {
                SharedResearchWorkspaceStatus.FAILED,
                SharedResearchWorkspaceStatus.CANCELLED,
            }
            and self.active_assignment_ids
        ):
            raise ValueError(
                "terminal workspace must not have "
                "active assignments"
            )

        if (
            self.status
            is SharedResearchWorkspaceStatus.REVISING
            and self.revision_count == 0
        ):
            raise ValueError(
                "revising workspace must have "
                "positive revision_count"
            )

    def _validate_metadata(self) -> None:
        """Validate shared workspace metadata."""

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

    @property
    def request_id(self) -> str:
        """Return the underlying research request ID."""

        return self.research_workspace.request.request_id

    @property
    def workspace_id(self) -> str:
        """Return the underlying research workspace ID."""

        return self.research_workspace.workspace_id

    @property
    def is_terminal(self) -> bool:
        """Return whether collaboration has ended."""

        return self.status in {
            SharedResearchWorkspaceStatus.COMPLETED,
            SharedResearchWorkspaceStatus.FAILED,
            SharedResearchWorkspaceStatus.CANCELLED,
        }

    @property
    def can_revise(self) -> bool:
        """Return whether another revision cycle is allowed."""

        return self.revision_count < self.maximum_revisions

    def agent(
        self,
        agent_id: str,
    ) -> ResearchAgentIdentity | None:
        """Return a registered agent by normalized ID."""

        if not agent_id.strip():
            raise ValueError(
                "agent_id must not be blank"
            )

        normalized = agent_id.strip().casefold()

        return next(
            (
                agent
                for agent in self.agents
                if agent.agent_id.strip().casefold()
                == normalized
            ),
            None,
        )

    def assignment(
        self,
        assignment_id: str,
    ) -> ResearchAgentTaskAssignment | None:
        """Return an assignment by normalized ID."""

        if not assignment_id.strip():
            raise ValueError(
                "assignment_id must not be blank"
            )

        normalized = assignment_id.strip().casefold()

        return next(
            (
                assignment
                for assignment in self.assignments
                if assignment.assignment_id
                .strip()
                .casefold()
                == normalized
            ),
            None,
        )

    def results_for_assignment(
        self,
        assignment_id: str,
    ) -> list[ResearchAgentTaskResult]:
        """Return all results for an assignment."""

        if not assignment_id.strip():
            raise ValueError(
                "assignment_id must not be blank"
            )

        normalized = assignment_id.strip().casefold()

        return [
            result
            for result in self.results
            if result.assignment.assignment_id
            .strip()
            .casefold()
            == normalized
        ]

    def messages_for_agent(
        self,
        agent_id: str,
    ) -> list[ResearchAgentMessage]:
        """Return direct and broadcast messages visible to an agent."""

        agent = self.agent(agent_id)

        if agent is None:
            return []

        return [
            message
            for message in self.messages
            if message.is_addressed_to(agent)
        ]
