from app.schemas.research_run_metrics import ResearchRunMetrics, ResearchStageMetrics


def test_run_metrics_aggregate_llm_calls_and_tokens() -> None:
    metrics = ResearchRunMetrics(
        total_elapsed_seconds=10.0,
        round_1_claim_generation=ResearchStageMetrics(
            call_count=2, recorded_tokens=100, elapsed_seconds=2.0
        ),
        round_1_answer_coverage=ResearchStageMetrics(
            call_count=1, recorded_tokens=50, elapsed_seconds=1.0
        ),
        coverage_claim_generation=ResearchStageMetrics(
            call_count=2, recorded_tokens=120, elapsed_seconds=3.0
        ),
    )
    assert metrics.llm_call_count == 5
    assert metrics.recorded_tokens == 270

def test_run_metrics_defaults_are_zero() -> None:
    metrics = ResearchRunMetrics(total_elapsed_seconds=0.0)
    assert metrics.search_provider_calls == 0
    assert metrics.llm_call_count == 0
    assert metrics.recorded_tokens == 0


def test_run_metrics_include_evidence_semantic_usage() -> None:
    metrics = ResearchRunMetrics(
        total_elapsed_seconds=10.0,
        round_1_evidence_semantic=ResearchStageMetrics(
            call_count=3,
            recorded_tokens=1200,
            elapsed_seconds=8.0,
        ),
    )

    assert metrics.llm_call_count == 3
    assert metrics.recorded_tokens == 1200
