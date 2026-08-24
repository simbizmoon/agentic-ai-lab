"""Offline tests for bounded grounded-answer factory composition."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.research.bounded_grounded_answer_factory import (
    create_bounded_grounded_answer_orchestrator,
)


class Responses:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(id="unused", output_text="unused", usage=None)


class Client:
    def __init__(self) -> None:
        self.responses = Responses()


class Evaluator:
    def evaluate(self, *, claim_text: str, evidence_excerpt: str):
        raise AssertionError((claim_text, evidence_excerpt))


def test_factory_composes_without_provider_call() -> None:
    client = Client()
    value = create_bounded_grounded_answer_orchestrator(
        client=client,
        model="test-model",
        citation_evaluator=Evaluator(),
    )
    assert value is not None
    assert client.responses.calls == []


def test_factory_rejects_blank_model_without_provider_call() -> None:
    client = Client()
    with pytest.raises(ValueError, match="model must not be blank"):
        create_bounded_grounded_answer_orchestrator(
            client=client,
            model=" ",
            citation_evaluator=Evaluator(),
        )
    assert client.responses.calls == []
