# AGENTS.md

## Mission

Build AIRA, a reliable Agentic AI research and development assistant,
while teaching the learner every major concept and implementation decision.

## Project Root

`/home/moon/Project/agentic-ai-lab`

## Current Stage

Phase 0. Do not implement application features until the project foundation
and learning documents have been reviewed and committed.

## Required Behavior

- Read MASTER.md before proposing changes.
- Read DECISIONS.md before choosing technologies.
- Check ROADMAP.md to determine the current phase.
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
