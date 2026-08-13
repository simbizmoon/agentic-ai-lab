# Phase 7 — OpenAI vs Local Single-Agent Worker Backend

## Scope

This phase compares the same AIRA single-agent research architecture with two
bounded-worker backends:

```text
A — OpenAI:
    claim relevance
    semantic citation verification
    answer coverage

B — Local:
    qwen3.5:4b claim relevance
    qwen3.5:4b semantic citation verification
    qwen3.5:4b answer coverage
```

The following remain common architecture components:

- deterministic planning
- Tavily search
- HTTP reading
- source selection
- OpenAI embeddings
- OpenAI evidence relevance
- OpenAI claim generation

## Important experimental limitation

The initial Phase 7 runner performs separate live executions. Therefore search
results and upstream OpenAI generation can vary between A and B even when the
question and CLI parameters are identical.

The benchmark explicitly records this limitation and does not claim that
end-to-end differences are caused only by the bounded-worker backend.

Use repeated paired runs (minimum 3) and inspect source/evidence/claim counts
alongside quality differences.

If backend attribution remains ambiguous, a later controlled replay benchmark
should freeze intermediate claim/evidence inputs and compare only the three
worker stages.

## Primary measurements

- task completion / failure
- research quality score
- source/evidence/claim/citation counts
- citation decisions / support levels
- claim relevance levels
- answer coverage
- total elapsed time
- bounded-worker elapsed time
- total LLM calls/tokens
- bounded-worker calls/tokens
- local provenance
- wall-clock runtime

Raw Phase 7 artifacts belong under:

```text
/mnt/ai-data/experiments/phase7/
```

They are experiment data and should not be committed.
