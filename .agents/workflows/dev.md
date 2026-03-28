---
description: "TDD development workflow for implementing features. Read spec → break down → red/green/refactor → pre-commit gate → commit."
---

# Development Workflow (TDD)

// turbo-all

> [!CAUTION]
> **STRICT RULES — NO EXCEPTIONS:**
> 1. **NO guessing or assuming.** If anything is unclear, STOP and ask the user (HITL).
> 2. **NO single-shot implementations.** Break work into small, manageable tasks.
> 3. **TDD: red tests first.** Every task starts with a failing test.
> 4. **Pre-commit gate before EVERY commit.** Run `/pre-commit` — no shortcuts.
> 5. **Always re-read a file before editing it.** Never rely on memory.

> [!IMPORTANT]
> **All test and lint commands MUST run autonomously.**
> Set `SafeToAutoRun: true` for ALL `pytest`, `ruff`, and `python -m pytest` commands.
> NEVER prompt the user for confirmation to run tests or linting. Just run them.

## Phase 1: Read the Spec

1.1. Read the implementation plan / spec for the feature being implemented.
     Understand the full scope, interfaces, and dependencies.

1.2. **Red flag check**: Can you implement this without guessing?
     - Are all interfaces defined?
     - Are all data models clear?
     - Are all edge cases specified?
     - Are dependencies on other modules clear?

     If ANY answer is "no" → **STOP. Call the HITL. Ask the user.**
     Do NOT proceed with assumptions.

## Phase 2: Task Breakdown

2.1. Break the feature into small, independently testable tasks.
     Each task should be completable in one TDD cycle (red → green → refactor).

2.2. Order tasks by dependency — implement foundations first, consumers last.

2.3. Write the task list to `task.md`. Each task should have:
     - A clear, one-line description
     - The source file(s) to create/modify
     - The test file(s) to create/modify

2.4. Present the task list to the user for review (HITL).
     Wait for approval before proceeding.

## Phase 3: TDD Cycle (repeat for each task)

For each task in the breakdown:

### 3.1 Red — Write Failing Tests First

- Write the test(s) for the task. Include:
  - Happy path
  - Edge cases / corner cases (but keep it simple — avoid over-engineering!)
  - Error paths where relevant
- Run the test(s) — they MUST fail (red). If they pass, the test is wrong.
// turbo
```
python -m pytest tests/unit/<relevant_test_file>.py -v --tb=short
```

### 3.2 Green — Implement the Minimum Code

- **Re-read the target file** before editing (mandatory).
- Write the simplest code that makes the tests pass.
- Do NOT add code that isn't needed by a test. YAGNI.
- Run the tests — they MUST pass (green).
// turbo
```
python -m pytest tests/unit/<relevant_test_file>.py -v --tb=short
```

### 3.2a Debugging — When Tests Fail Unexpectedly

When a test fails and you need to debug, run targeted tests autonomously.
All these commands auto-run — no human interaction needed:
// turbo
```
# Single test by node ID
python -m pytest tests/unit/test_foo.py::TestClass::test_method -v --tb=long

# Keyword filter
python -m pytest tests/unit/test_foo.py -k "test_specific_case" -v --tb=long

# All tests in a specific file with full traceback
python -m pytest tests/unit/test_foo.py -v --tb=long

# Re-run only previously failed tests
python -m pytest --lf -v --tb=long
```

Debug loop: read error → re-read source → fix → re-run failing test → repeat until green.

### 3.3 Refactor (if needed)

- Clean up duplication, naming, structure.
- Run tests again — still green.
- Run lint — fix any issues immediately.
// turbo
```
python -m pytest tests/unit/<relevant_test_file>.py -v --tb=short
ruff check src/ tests/
```

### 3.4 Update task.md

- Mark the completed task as `[x]`.

## Phase 4: Integration Check

4.1. After all tasks are done, run the full test suite:
// turbo
```
python -m pytest --tb=short -q
```

4.2. Fix any regressions immediately.

## Phase 5: Pre-Commit Quality Gate

5.1. Execute the full `/pre-commit` workflow. This is MANDATORY.
     No commit is allowed without passing all 7 phases.

## Phase 6: Commit

6.1. Stage and commit with a descriptive message following conventional commits:
     ```
     feat(X.Y): short description
     ```

6.2. Push to remote.

---

## Principles

| Principle | Rule |
|-----------|------|
| **No guessing** | If unclear → HITL. Never assume. |
| **TDD** | Red → Green → Refactor. Every task. |
| **Small tasks** | One logical unit per TDD cycle. |
| **KISS** | Keep it simple. Think of corner cases but don't over-engineer. |
| **Re-read before edit** | Always read the file immediately before modifying it. |
| **Lint early** | Run ruff after each green step. Don't accumulate debt. |
| **Architecture** | Check imports respect layer boundaries. No cross-layer violations. |
| **Coverage** | Target 70-90% test coverage. |
| **Pre-commit gate** | Mandatory before every commit. No exceptions. |
| **Tests run freely** | `SafeToAutoRun: true` for all test/lint commands. No exceptions. |