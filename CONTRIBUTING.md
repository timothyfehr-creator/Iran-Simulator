# Contributing & Development Standards

These rules apply to all contributors — human or AI. They are enforceable constraints, not suggestions.

## Commit Rules

- **Max 500 lines added per commit.** If a feature is larger, split it into sequential commits that each stand alone (build + tests pass at every commit).
- **Max 8 files changed per commit.** If you're touching more, the change is too broad — decompose it.
- **Commit messages use conventional format:** `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- **Message body explains WHY, not WHAT.** The diff shows what changed. The message says why.
- **No empty or ceremony commits.** Every commit must contain meaningful work.
- **Docs updates go in the same commit as the feature**, not as a separate follow-up commit.

## Branch & PR Rules

- **One feature per branch.** Don't combine unrelated changes.
- **PRs should be under 1,000 lines.** If larger, split into stacked PRs that each stand alone.
- **Branch names use format:** `feat/short-description`, `fix/short-description`, `refactor/short-description`.
- **Delete branches after merge.** No stale branches lingering.

## Code Quality

- **Tests must pass before committing.** Verify green before every push.
- **No silent error swallowing.** Every `except` block must either log the error, re-raise, or return a value that the caller explicitly handles. Never `except: pass`.
- **Graceful degradation over hard crashes.** External dependencies (APIs, websites, files) will fail. Code must warn and fall back to defaults, not raise and kill the pipeline.
- **Math must be verified.** Any computation involving probabilities, rates, or time conversions should have a unit test that checks the actual math with known inputs/outputs.
- **Frontend and backend types must match.** If the backend emits a field, the frontend TypeScript interface must declare it. If a field is renamed or added on one side, update the other in the same commit.
- **No dead code.** No unused imports, no unused constants, no commented-out blocks, no "TODO: remove later." Delete it or use it.

## Testing

- **Unit tests for logic.** Any function with branching, math, or state transitions gets a unit test with known inputs and expected outputs.
- **Integration tests for pipelines.** End-to-end flows (ingest → extract → compile → simulate) get at least one happy-path integration test.
- **No tests that call external APIs.** Mock all HTTP calls. Tests must pass offline and in CI without credentials.
- **Tests must be deterministic.** Seed all randomness. No flaky tests that pass sometimes.
- **Test the error paths, not just the happy path.** Missing data, malformed input, network failures, empty responses.

## Dependencies

- **Don't add dependencies without justification.** Every new package in requirements.txt or package.json needs a reason. Prefer standard library when possible.
- **Pin major versions.** Use `>=2.31.0,<3.0.0` not just `>=2.31.0` to avoid surprise breaking changes.
- **No unused dependencies.** If you remove code that used a package, remove the package too.

## Secrets & Security

- **Never commit secrets.** No API keys, tokens, passwords, or credentials in the repo. Use environment variables and `.env` files.
- **`.env` must be in `.gitignore`.** Always. No exceptions.
- **Use `.env.example` for templates.** Show what variables are needed without the actual values.
- **No hardcoded URLs with API keys** in source code. Externalize to config or environment.

## Data Resilience

- **Every external fetcher must have retry logic** with exponential backoff (minimum 3 retries).
- **Every fetcher must have a timeout** (max 30s for HTTP requests).
- **Staleness detection must compare against current time**, not against the fetch timestamp itself.
- **Missing data must produce a warning and a fallback**, not a crash. Pipelines must be runnable with partial data.

## Metrics & Model Integrity

- **Aggregate metrics must be meaningful.** Don't OR together categorically different events into a single rate. Split by tier or weight by impact.
- **Every probability in the output should be sanity-checked.** If a key event rate exceeds 80%, verify that it represents something real and not a modeling artifact.
- **Label fields accurately.** Field names must describe what they actually contain, not what they were copied from.

## AI-Specific Rules

- **No AI scaffolding in the repo.** No skill files, agent briefings, migration handoffs, swarm docs, or model-specific instructions. These belong in prompts, not in version control.
- **CLAUDE.md is the only exception** — it provides project context for Claude Code sessions and must be kept concise and accurate.
- **Review every diff before committing.** If using AI to generate code, the diff must be read and understood before it is committed. The review agent (or human) must explicitly approve.
- **AI-generated code is not trusted by default.** Treat it as a junior engineer's PR — assume subtle bugs exist and look for them actively.

## Review Checklist

Before any commit is approved, verify:

1. [ ] Tests pass
2. [ ] Commit is under 500 lines added / 8 files changed
3. [ ] No dead code or unused imports introduced
4. [ ] Frontend/backend types are consistent
5. [ ] Error handling is present for all external calls
6. [ ] Metrics and computed values make semantic sense
7. [ ] Field names accurately describe their contents
8. [ ] No secrets, credentials, or .env files included
9. [ ] No AI artifacts or scaffolding included
10. [ ] New dependencies are justified and version-pinned
11. [ ] Tests cover error paths, not just happy paths
