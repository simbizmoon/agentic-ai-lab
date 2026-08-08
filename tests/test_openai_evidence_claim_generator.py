"""Tests for OpenAI evidence-backed claim proposal generation."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from app.research.openai_evidence_claim_generator import (
    GENERATIVE_CLAIM_BATCH_INSTRUCTIONS,
    GENERATIVE_CLAIM_INSTRUCTIONS,
    ClaimGenerationProviderError,
    OpenAIEvidenceClaimGenerator,
    OpenAIEvidenceClaimGeneratorError,
)
from app.schemas.generated_claim_proposal import (
    GeneratedClaimProposal,
    GeneratedClaimProposalBatch,
    GeneratedClaimProposalBatchItem,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)


@dataclass
class FakeResponses:
    response: Any

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response: Any) -> None:
        self.responses = FakeResponses(response)


def evidence() -> ResearchEvidence:
    return ResearchEvidence(
        evidence_id="evidence-001",
        request_id="request-001",
        task_id="task-001",
        source_id="source-001",
        document_id="document-001",
        excerpt=(
            "The SDK can turn Python functions into tools "
            "by inspecting signatures and docstrings."
        ),
        start_character=10,
        end_character=94,
        evidence_type=ResearchEvidenceType.METHOD,
        stance=ResearchEvidenceStance.SUPPORTS,
        relevance_score=0.95,
        confidence_score=0.9,
        rationale="The excerpt describes function tool construction.",
    )


def response(
    *,
    output_parsed: object | None = None,
    status: str = "completed",
    refusal: str | None = None,
) -> SimpleNamespace:
    content = []
    if refusal is not None:
        content = [
            SimpleNamespace(refusal=refusal),
        ]

    return SimpleNamespace(
        id="resp-001",
        _request_id="req-provider-001",
        status=status,
        output_parsed=(
            GeneratedClaimProposal(
                text=(
                    "The SDK can expose Python functions "
                    "as callable tools."
                ),
                rationale=(
                    "The claim preserves the evidence's "
                    "described capability without adding scope."
                ),
            )
            if output_parsed is None
            else output_parsed
        ),
        output=[
            SimpleNamespace(
                content=content,
            )
        ],
        usage=None,
    )


def test_generator_returns_structured_proposal() -> None:
    client = FakeClient(response())
    generator = OpenAIEvidenceClaimGenerator(
        client=client,  # type: ignore[arg-type]
        model="gpt-5",
    )

    result = generator.generate(evidence())

    assert (
        result.proposal.text
        == "The SDK can expose Python functions as callable tools."
    )
    assert result.response_id == "resp-001"
    assert result.request_id == "req-provider-001"
    assert result.usage is None
    assert result.elapsed_seconds >= 0.0


def test_generator_sends_only_meaning_inputs_to_model() -> None:
    client = FakeClient(response())
    generator = OpenAIEvidenceClaimGenerator(
        client=client,  # type: ignore[arg-type]
        model="gpt-5",
    )

    generator.generate(evidence())

    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]

    assert call["model"] == "gpt-5"
    assert (
        call["instructions"]
        == GENERATIVE_CLAIM_INSTRUCTIONS
    )
    assert (
        call["text_format"]
        is GeneratedClaimProposal
    )
    assert call["store"] is False

    model_input = call["input"]

    assert '"evidence_type": "method"' in model_input
    assert '"excerpt":' in model_input
    assert "evidence-001" not in model_input
    assert "source-001" not in model_input
    assert "document-001" not in model_input
    assert "request-001" not in model_input
    assert "task-001" not in model_input


def test_generator_rejects_blank_model() -> None:
    with pytest.raises(
        ValueError,
        match="model must not be blank",
    ):
        OpenAIEvidenceClaimGenerator(
            client=FakeClient(response()),  # type: ignore[arg-type]
            model="   ",
        )


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (
            "incomplete",
            "response was incomplete",
        ),
        (
            "failed",
            "response was not completed",
        ),
    ],
)
def test_generator_rejects_noncompleted_response(
    status: str,
    message: str,
) -> None:
    generator = OpenAIEvidenceClaimGenerator(
        client=FakeClient(
            response(status=status)
        ),  # type: ignore[arg-type]
        model="gpt-5",
    )

    with pytest.raises(
        OpenAIEvidenceClaimGeneratorError,
        match=message,
    ):
        generator.generate(evidence())


def test_generator_rejects_refusal() -> None:
    generator = OpenAIEvidenceClaimGenerator(
        client=FakeClient(
            response(refusal="Cannot comply.")
        ),  # type: ignore[arg-type]
        model="gpt-5",
    )

    with pytest.raises(
        OpenAIEvidenceClaimGeneratorError,
        match="refused",
    ):
        generator.generate(evidence())


def test_generator_rejects_missing_output() -> None:
    raw_response = response()
    raw_response.output_parsed = None

    generator = OpenAIEvidenceClaimGenerator(
        client=FakeClient(
            raw_response
        ),  # type: ignore[arg-type]
        model="gpt-5",
    )

    with pytest.raises(
        OpenAIEvidenceClaimGeneratorError,
        match="response was empty",
    ):
        generator.generate(evidence())


def test_generator_rejects_wrong_output_type() -> None:
    generator = OpenAIEvidenceClaimGenerator(
        client=FakeClient(
            response(
                output_parsed={
                    "text": "not a model",
                }
            )
        ),  # type: ignore[arg-type]
        model="gpt-5",
    )

    with pytest.raises(
        OpenAIEvidenceClaimGeneratorError,
        match="invalid type",
    ):
        generator.generate(evidence())


def test_generator_normalizes_provider_failure() -> None:
    class FailingResponses:
        def parse(self, **kwargs: Any) -> Any:
            raise RuntimeError("provider unavailable")

    client = SimpleNamespace(
        responses=FailingResponses(),
    )

    generator = OpenAIEvidenceClaimGenerator(
        client=client,  # type: ignore[arg-type]
        model="gpt-5",
    )

    with pytest.raises(
        OpenAIEvidenceClaimGeneratorError,
        match="request failed",
    ):
        generator.generate(evidence())


def test_batch_generator_uses_one_structured_request() -> None:
    batch = GeneratedClaimProposalBatch(
        items=[
            GeneratedClaimProposalBatchItem(
                item_id="item-002",
                proposal=GeneratedClaimProposal(text="Claim two.", rationale="Bounded two."),
            ),
            GeneratedClaimProposalBatchItem(
                item_id="item-001",
                proposal=GeneratedClaimProposal(text="Claim one.", rationale="Bounded one."),
            ),
        ]
    )
    client = FakeClient(response(output_parsed=batch))
    generator = OpenAIEvidenceClaimGenerator(client=client, model="gpt-5")  # type: ignore[arg-type]
    second = evidence().model_copy(update={"evidence_id": "evidence-002", "excerpt": "Second independent evidence."})

    result = generator.generate_batch([("item-001", evidence()), ("item-002", second)])

    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]
    assert call["text_format"] is GeneratedClaimProposalBatch
    assert call["instructions"] == GENERATIVE_CLAIM_BATCH_INSTRUCTIONS
    assert result.proposals["item-001"].text == "Claim one."
    assert "evidence-001" not in call["input"]
    assert "source-001" not in call["input"]


def test_batch_provider_failure_is_distinguishable() -> None:
    class FailingResponses:
        def parse(self, **kwargs: Any) -> Any:
            raise RuntimeError("provider unavailable")

    generator = OpenAIEvidenceClaimGenerator(
        client=SimpleNamespace(responses=FailingResponses()),  # type: ignore[arg-type]
        model="gpt-5",
    )

    with pytest.raises(ClaimGenerationProviderError, match="request failed"):
        generator.generate_batch([("item-001", evidence())])
