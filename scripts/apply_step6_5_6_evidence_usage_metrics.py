from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(path, old, new):
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'anchor not found: {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

def main():
    adapter = ROOT / 'app/research/pipeline_analysis_adapters.py'
    replace_once(adapter, 'from __future__ import annotations\n\n', 'from __future__ import annotations\n\nfrom app.budget import BudgetUsage\n\n')
    replace_once(adapter, '        self._validator.validate_extractor(extractor)\n\n    @property\n    def extractor', '        self._validator.validate_extractor(extractor)\n        self._last_usage = BudgetUsage()\n\n    @property\n    def extractor')
    replace_once(adapter, '        return self._extractor\n\n    def extract(', '        return self._extractor\n\n    @property\n    def last_usage(self) -> BudgetUsage:\n        """Return semantic LLM usage from the most recent extract call."""\n        return self._last_usage\n\n    def extract(')
    replace_once(adapter, '        evidence: list[ResearchEvidence] = []\n\n        for document in document_set.successful_documents():', '        evidence: list[ResearchEvidence] = []\n        attempts = 0\n        recorded_tokens = 0\n        elapsed_seconds = 0.0\n\n        for document in document_set.successful_documents():')
    replace_once(adapter, '            evidence.extend(result.ordered_evidence())\n\n        return ResearchEvidenceSet(', '            evidence.extend(result.ordered_evidence())\n\n            metadata = result.metadata\n            attempts += int(metadata.get("semantic_budget_attempts", "0"))\n            recorded_tokens += int(metadata.get("semantic_budget_recorded_tokens", "0"))\n            elapsed_seconds += float(metadata.get("semantic_budget_elapsed_seconds", "0"))\n\n        self._last_usage = BudgetUsage(\n            attempts=attempts,\n            recorded_tokens=recorded_tokens,\n            elapsed_seconds=elapsed_seconds,\n        )\n\n        return ResearchEvidenceSet(')

    schema = ROOT / 'app/schemas/research_run_metrics.py'
    replace_once(schema, '    round_1_evidence_extraction_elapsed_seconds: float = Field(default=0.0, ge=0.0)\n    round_1_claim_generation:', '    round_1_evidence_extraction_elapsed_seconds: float = Field(default=0.0, ge=0.0)\n    round_1_evidence_semantic: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)\n    round_1_claim_generation:')
    replace_once(schema, '    coverage_evidence_extraction_elapsed_seconds: float = Field(default=0.0, ge=0.0)\n    coverage_claim_generation:', '    coverage_evidence_extraction_elapsed_seconds: float = Field(default=0.0, ge=0.0)\n    coverage_evidence_semantic: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)\n    coverage_claim_generation:')
    text = schema.read_text(encoding='utf-8')
    text = text.replace('        stages = (\n            self.round_1_claim_generation,', '        stages = (\n            self.round_1_evidence_semantic,\n            self.round_1_claim_generation,', 2)
    text = text.replace('            self.coverage_claim_generation,', '            self.coverage_evidence_semantic,\n            self.coverage_claim_generation,', 2)
    schema.write_text(text, encoding='utf-8')

    pipeline = ROOT / 'app/research/single_research_agent_pipeline.py'
    replace_once(pipeline, '        round_1_evidence_extraction_elapsed_seconds = max(0.0, time.perf_counter() - evidence_started_at)\n\n        replanning_metadata:', '        round_1_evidence_extraction_elapsed_seconds = max(0.0, time.perf_counter() - evidence_started_at)\n        round_1_evidence_semantic = self._component_usage_metrics(\n            self._evidence_extractor\n        )\n\n        replanning_metadata:')
    replace_once(pipeline, '        coverage_evidence_extraction_elapsed_seconds = 0.0\n        coverage_claim_generation = ResearchStageMetrics()', '        coverage_evidence_extraction_elapsed_seconds = 0.0\n        coverage_evidence_semantic = ResearchStageMetrics()\n        coverage_claim_generation = ResearchStageMetrics()')
    replace_once(pipeline, '                    coverage_evidence_extraction_elapsed_seconds = max(0.0, time.perf_counter() - coverage_evidence_started_at)\n                    new_evidence_ids = {', '                    coverage_evidence_extraction_elapsed_seconds = max(0.0, time.perf_counter() - coverage_evidence_started_at)\n                    coverage_evidence_semantic = self._component_usage_metrics(\n                        self._evidence_extractor\n                    )\n                    new_evidence_ids = {')
    replace_once(pipeline, '                round_1_evidence_extraction_elapsed_seconds=(\n                    round_1_evidence_extraction_elapsed_seconds\n                ),\n                round_1_claim_generation=', '                round_1_evidence_extraction_elapsed_seconds=(\n                    round_1_evidence_extraction_elapsed_seconds\n                ),\n                round_1_evidence_semantic=round_1_evidence_semantic,\n                round_1_claim_generation=')
    replace_once(pipeline, '                coverage_evidence_extraction_elapsed_seconds=(\n                    coverage_evidence_extraction_elapsed_seconds\n                ),\n                coverage_claim_generation=', '                coverage_evidence_extraction_elapsed_seconds=(\n                    coverage_evidence_extraction_elapsed_seconds\n                ),\n                coverage_evidence_semantic=coverage_evidence_semantic,\n                coverage_claim_generation=')

    test_path = ROOT / 'tests/test_research_run_metrics.py'
    text = test_path.read_text(encoding='utf-8')
    marker = 'test_run_metrics_include_evidence_semantic_usage'
    if marker not in text:
        text += '\n\ndef test_run_metrics_include_evidence_semantic_usage() -> None:\n    metrics = ResearchRunMetrics(\n        total_elapsed_seconds=10.0,\n        round_1_evidence_semantic=ResearchStageMetrics(\n            call_count=3,\n            recorded_tokens=1200,\n            elapsed_seconds=8.0,\n        ),\n    )\n\n    assert metrics.llm_call_count == 3\n    assert metrics.recorded_tokens == 1200\n'
        test_path.write_text(text, encoding='utf-8')

    print('Step 6.5.6 evidence usage metrics applied.')

if __name__ == '__main__':
    main()
