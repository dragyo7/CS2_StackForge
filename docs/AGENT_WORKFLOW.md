# Fast, Smart Vibe-Coding Workflow

## Goal
Use an AI coding agent as a disciplined implementation partner. Optimize for small verified increments, not giant prompts or speculative scaffolding.

## Before every task
1. Read `HANDOVER.md`, root `Rules.md`, `DECISIONS.md` and the relevant feature spec.
2. Inspect actual code, git status, tests, migrations and package versions.
3. Identify what already exists. Never recreate completed modules.
4. State the exact outcome and acceptance tests.
5. List files expected to change.
6. Ask one clarifying question only if a blocker cannot be resolved from repository/docs.

## Task size
One vertical slice per task. Examples:
- SteamID parser + tests.
- Player import transaction + tests.
- Match-room roster API + tests.
- Partition generator + tests.
Do not ask the agent to implement all providers, demo analysis, Discord and frontend in one task.

## Required implementation loop
1. Inspect.
2. Plan (short).
3. Implement minimal complete path.
4. Add/update tests.
5. Run formatting/lint/type checks.
6. Run targeted tests.
7. Run full relevant tests.
8. Inspect diff for unrelated changes/secrets.
9. Update docs and decisions.
10. Report files changed, commands/results, known limitations and next step.

## Agent response format
- **Implemented**
- **Files changed**
- **Tests run and results**
- **Security/data implications**
- **Known gaps**
- **Next exact task**

## Avoid
- Empty placeholder folders/services.
- Duplicate abstractions.
- Premature microservices.
- Unnecessary dependencies.
- Fake sample data in production paths.
- Catch-all exceptions that hide provider errors.
- Hardcoded API keys.
- Silent schema changes.
- Reformatting unrelated files.
- "Production ready" claims without tests and deployment evidence.

## Definition of smart progress
A task is complete when a user-visible path works end-to-end and is covered by tests. A large code diff without a verified workflow is not progress.
