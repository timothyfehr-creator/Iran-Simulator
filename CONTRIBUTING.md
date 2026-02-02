# Contributing & Development Standards

These rules apply to all contributors — human or AI. They are enforceable constraints, not suggestions.

## Commit Rules

- **Max 500 lines added per commit.** If a feature is larger, split it into sequential commits that each stand alone (build + tests pass at every commit).
- **Max 8 files changed per commit.** If you're touching more, the change is too broad — decompose it.
- **Commit messages use conventional format:** `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- **Message body explains WHY, not WHAT.** The diff shows what changed. The message says why.
- **No empty or ceremony commits.** Every commit must contain meaningful work.
- **Docs updates go in the same commit as the feature**, not as a separate follow-up commit.

## Code Quality

- **Tests must pass before committing.** Run `PYTHONPATH=.:src python -m pytest tests/ -x --timeout=30` and verify green.
- **No silent error swallowing.** Every `except` block must either log the error, re-raise, or return a value that the caller explicitly handles. Never `except: pass`.
- **Graceful degradation over hard crashes.** External dependencies (APIs, websites, files) will fail. Code must warn and fall back to defaults, not raise and kill the pipeline.
- **Math must be verified.** Any computation involving probabilities, rates, or time conversions should have a unit test that checks the actual math with known inputs/outputs.
- **Frontend and backend types must match.** If the backend emits a field, the frontend TypeScript interface must declare it. If a field is renamed or added on one side, update the other in the same commit.
- **No dead code.** No unused imports, no unused constants, no commented-out blocks, no "TODO: remove later." Delete it or use it.

## Data Resilience

- **Every external fetcher must have retry logic** with exponential backoff (minimum 3 retries).
- **Every fetcher must have a timeout** (max 30s for HTTP requests).
- **Staleness detection must compare against current time**, not against the fetch timestamp itself.
- **Missing data must produce a warning and a fallback**, not a crash. The simulation must be runnable with partial data.

## Metrics & Model Integrity

- **Aggregate metrics must be meaningful.** Don't OR together categorically different events (e.g., info ops and kinetic strikes) into a single rate. Split by tier or weight by impact.
- **Every probability in the output should be sanity-checked.** If a key event rate exceeds 80%, verify that it represents something real and not a modeling artifact (e.g., compounding daily probabilities over a long window).
- **Label fields accurately.** If a field is called `rial_usd_rate`, it must contain the Rial/USD rate, not a USDT/IRT crypto rate from a different source.

## AI-Specific Rules

- **No AI scaffolding in the repo.** No skill files, agent briefings, migration handoffs, swarm docs, or model-specific instructions committed to the codebase. These belong in prompts, not in version control.
- **No CLAUDE.md, GEMINI.md, or similar files.** Session context goes in the conversation, not the repo.
- **Review every diff before committing.** If using AI to generate code, the diff must be read and understood before it is committed. This means the review agent (or human) must explicitly approve.
- **AI-generated code is not trusted by default.** Treat it as a junior engineer's PR — assume subtle bugs exist and look for them actively.

## Review Checklist

Before any commit is approved, verify:

1. [ ] Tests pass
2. [ ] No files over the size limit
3. [ ] No dead code or unused imports introduced
4. [ ] Frontend/backend types are consistent
5. [ ] Error handling is present for all external calls
6. [ ] Probabilities and metrics make semantic sense
7. [ ] Field names accurately describe their contents
8. [ ] No AI artifacts or scaffolding included
