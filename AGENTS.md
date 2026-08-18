# AGENTS.md

## Mission

Build AIRA, a reliable Agentic AI research and development assistant,
while teaching the learner every major concept and implementation decision.

## Project Root

`/home/moon/Project/agentic-ai-lab`

## Current Stage

Authoritative current position is defined by `ROADMAP.md`.

```text
Stage 5 — Internet Research Expansion
Patent Research Vertical Slice
Step 3G — Patent User Acceptance Test FINAL PASS

NEXT
Step 4A — Patent Metadata Expansion
```

Historical Phase 0~13, Stage A~I, and Local/Multi-Agent experimental phase numbers
must not be used as the current product stage.

API keys and secrets must never be stored in Git. Implement only the smallest
accepted product work item at a time, test it, inspect the diff, and then move to
the next step.

## Required Behavior

- Read MASTER.md before proposing changes.
- Read DECISIONS.md before choosing technologies.
- Check ROADMAP.md to determine the authoritative current Stage / Vertical Slice / Step.
- Explain changes in beginner-friendly language.
- Prefer minimal and reversible changes.
- Do not add unrelated features.
- Do not perform broad refactoring without an explicit request.
- Do not expose or commit secrets.
- Add tests for behavioral changes.
- Report modified files and executed tests.

## Approval Required

Do not perform the following without explicit user approval:

- Git push
- Production deployment
- Data deletion
- Database migration on production
- External email sending
- Security configuration changes
- Actions that materially increase cost

## Coding Standards

- Python 3.12
- Type hints for public functions
- Pydantic for structured validation where appropriate
- Clear error handling
- Small functions with explicit responsibilities
- Tests for important behavior
- English identifiers
- Korean explanatory documentation when it improves learning

## Completion Report

Every coding task must report:

1. Goal
2. Files changed
3. Design decisions
4. Commands executed
5. Tests executed
6. Results
7. Known limitations
8. Recommended next step
