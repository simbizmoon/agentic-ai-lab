"""End-to-end application service for idempotent research."""

from __future__ import annotations

from pydantic import ValidationError

from app.application.execution_repository import (
    ApplicationExecutionRepository,
)
from app.application.idempotency_service import (
    ApplicationIdempotencyService,
    ApplicationIdempotencyStartRequest,
)
from app.application.research_application_flow import (
    ApplicationResearchFlowRequest,
    ApplicationResearchFlowResult,
    ApplicationResearchFlowStoredResult,
)
from app.application.research_application_flow_error import (
    ApplicationResearchFlowStateError,
)
from app.application.research_execution import (
    ApplicationResearchExecutionResult,
)
from app.application.research_execution_service import (
    ApplicationResearchExecutionService,
)
from app.application.research_execution_service_error import (
    ApplicationResearchExecutionFailedError,
)
from app.application.transaction import (
    ApplicationTransactionManager,
)


class ApplicationResearchFlowService:
    """Coordinate one transactional idempotent research flow."""

    OPERATION = "research.execute"

    def __init__(
        self,
        *,
        transaction_manager: ApplicationTransactionManager,
        idempotency_service: ApplicationIdempotencyService,
        research_execution_service: (
            ApplicationResearchExecutionService
        ),
        execution_repository: ApplicationExecutionRepository,
    ) -> None:
        self._transaction_manager = transaction_manager
        self._idempotency_service = idempotency_service
        self._research_execution_service = (
            research_execution_service
        )
        self._execution_repository = execution_repository

    def execute(
        self,
        request: ApplicationResearchFlowRequest,
    ) -> ApplicationResearchFlowResult:
        """Execute or reuse one research application flow."""

        flow_result: ApplicationResearchFlowResult | None = None
        execution_error: (
            ApplicationResearchExecutionFailedError | None
        ) = None

        with self._transaction_manager.transaction():
            started = self._idempotency_service.begin(
                ApplicationIdempotencyStartRequest(
                    workspace_id=request.research.workspace_id,
                    operation=self.OPERATION,
                    idempotency_key=request.idempotency_key,
                    payload=request.research.model_dump(
                        mode="json"
                    ),
                    metadata=dict(request.metadata),
                )
            )

            if not started.execute_operation:
                flow_result = self._restore_reused_result(
                    idempotency_record_id=(
                        started.record.idempotency_record_id
                    ),
                    reused_result=started.reused_result,
                )
            else:
                try:
                    research_result = (
                        self._research_execution_service.execute(
                            request.research
                        )
                    )
                except (
                    ApplicationResearchExecutionFailedError
                ) as error:
                    self._idempotency_service.fail(
                        idempotency_record_id=(
                            started.record
                            .idempotency_record_id
                        ),
                        code=type(error).__name__,
                        message=error.failure_message,
                        retryable=False,
                    )
                    execution_error = error
                else:
                    stored_result = (
                        ApplicationResearchFlowStoredResult(
                            execution_id=(
                                research_result.execution
                                .execution_id
                            ),
                            output=research_result.output,
                        )
                    )

                    self._idempotency_service.succeed(
                        idempotency_record_id=(
                            started.record
                            .idempotency_record_id
                        ),
                        result=stored_result.model_dump(
                            mode="json"
                        ),
                    )

                    flow_result = ApplicationResearchFlowResult(
                        idempotency_record_id=(
                            started.record
                            .idempotency_record_id
                        ),
                        reused=False,
                        research_result=research_result,
                    )

        if execution_error is not None:
            raise execution_error

        if flow_result is None:
            raise ApplicationResearchFlowStateError(
                "research flow completed without a result"
            )

        return flow_result

    def _restore_reused_result(
        self,
        *,
        idempotency_record_id: str,
        reused_result: object,
    ) -> ApplicationResearchFlowResult:
        """Restore a successful result from idempotency state."""

        try:
            stored = (
                ApplicationResearchFlowStoredResult
                .model_validate(reused_result)
            )
        except ValidationError as error:
            raise ApplicationResearchFlowStateError(
                "stored idempotency result is invalid"
            ) from error

        execution = self._execution_repository.get(
            stored.execution_id
        )

        if execution is None:
            raise ApplicationResearchFlowStateError(
                "stored idempotency execution was not found"
            )

        research_result = ApplicationResearchExecutionResult(
            execution=execution,
            output=stored.output,
        )

        return ApplicationResearchFlowResult(
            idempotency_record_id=idempotency_record_id,
            reused=True,
            research_result=research_result,
        )
