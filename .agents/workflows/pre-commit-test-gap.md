---
description: Run a pre-commit quality gate for the current feature before marking it done.
---

# Pre-Commit Quality Gate

Before we commit, run a full pre-commit quality gate for the feature we just built.
This workflow covers architecture verification, test gap analysis, linting, complexity,
file size, and documentation.

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES!**
>
> This workflow has 6 phases that MUST be executed **in strict order**.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Re-read this workflow file to confirm which phase is next
> 2. Update `task.md` to mark the current phase as `[/]` in-progress
> 3. After completing a phase, mark it `[x]` in `task.md`
>
> **Phase 3 has a HITL gate (step 3.9)** — you MUST stop and present the
> gap analysis to the user. Do NOT continue until the user responds.
>
> If you catch yourself about to run `pytest` or "verify everything works"
> before completing Phase 3 and Phase 4 — **STOP immediately**.
> That is Phase 5. You are skipping phases.

## Phase 1: Architecture Verification

1.1. Read the architecture reference in full:
     ```
     docs/architecture/architecture_reference.md
     ```

1.2. Identify ALL source files that were created or modified for this feature.

1.3. For EACH changed/new file, verify:
     - **Layer placement**: Does the file live in the correct module per the
       architecture? Check the module's `context.yaml` for `purpose` and `archetype`.
     - **Dependency direction**: Do its imports respect `consumes` and `forbids`
       rules declared in the nearest `context.yaml`?
     - **Archetype compliance**: Does the code follow the structural constraints
       of its archetype (e.g., `pure-logic` has no I/O, `adapter` wraps externals,
       `orchestrator` delegates)?
     - **No parallel mechanisms**: Does the change duplicate existing
       infrastructure (e.g., creating a new security layer when FolderGrant exists)?

1.4. **Zoom-out test** — for EACH new module, file, or capability added:
     - Does a similar capability already exist elsewhere in the codebase?
       (e.g., a "research search" function vs the existing `filesystem/` grep)
     - Would extending an existing module be a better fit than creating a new one?
     - Is the new code named by what the *agent does* ("research") rather than
       what the *code is* ("filesystem search")? If so, it likely belongs in an
       existing module.
     - Check the Feature Map in the architecture reference for precedent.

     > A feature may look correct in isolation, but the whole picture may reveal
     > a better home already exists. Always verify against the full architecture
     > before accepting new module placement.

1.5. **Acyclic Dependencies** — verify the change does NOT introduce circular
     imports between modules. Dependencies must form a DAG (directed acyclic
     graph) pointing downward. If module A imports from B, B must NEVER import
     from A (directly or transitively). Check with:
     - Follow the import chain of every new `import`/`from` statement
     - If a cycle exists, break it with an interface in a lower-level module

1.6. **Common Closure** — things that change together should live together.
     If the feature required modifying files in 3+ different modules, ask:
     - Are those changes tightly coupled? If so, should they be co-located?
     - Conversely, if one module has mixed concerns (some parts change with
       feature A, others with feature B), it may need splitting.

1.7. **Stability Direction** — depend toward stable modules, not away from them.
     - Stable modules: `config/`, `context/`, `validation/` (pure-logic, rarely change)
     - Volatile modules: `drafting/`, `review/`, `implementation/` (orchestrators, change often)
     - A stable module must NEVER depend on a volatile one
     - New code in a stable module must not introduce volatile dependencies

1.8. For EACH violation found (whether pre-existing or newly introduced):
     - **Fix it** if possible within the scope of this feature.
     - If the fix requires a separate task, **document the violation** in the
       architecture reference (`docs/architecture/architecture_reference.md`)
       under "Known Boundary Violations" with: what, where, which rule is broken.
     - **No violation may be silently skipped.** Every issue must be either
       fixed or documented — this is non-negotiable.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 1 is complete. Update `task.md`.
> The NEXT phase is Phase 2 (Code Quality Checks) — NOT running pytest!

## Phase 2: Code Quality Checks

// turbo-all

2.1. Run **ruff lint** on the entire repo:
     ```
     python -m ruff check src/ tests/
     ```
     Every error MUST be fixed — no exceptions, regardless of whether the error
     is pre-existing or newly introduced!

2.2. Run **mypy type check** on the source tree:
     ```
     python -m mypy src/
     ```
     Every error MUST be fixed — no exceptions!

2.3. Run **file complexity** check (C901 max complexity = 10):
     ```
     python -m ruff check src/ --select C901
     ```
     Every violation MUST be fixed by extracting helper functions!

2.4. Run **lines-of-code per file** check (max 500 lines per source file):
     ```
     python -c "from pathlib import Path; files = [f for f in Path('src').rglob('*.py') if f.stat().st_size > 0]; big = [(f, len(f.read_text(encoding='utf-8').splitlines())) for f in files if len(f.read_text(encoding='utf-8').splitlines()) > 500]; [print(f'{loc} lines: {f}') for f, loc in sorted(big, key=lambda x: -x[1])]; print(f'{len(big)} file(s) over 500 lines') if big else print('All files within 500-line limit')"
     ```
     Files over 500 lines MUST be refactored by splitting into smaller modules!

> [!IMPORTANT]
> **CHECKPOINT:** Phase 2 is complete. Update `task.md`.
> The NEXT phase is Phase 3 (Test Gap Analysis) — NOT running pytest!

## Phase 3: Test Gap Analysis

3.1. Read EVERY source file that was created or modified for this feature.
3.2. For each file, go line-by-line and identify EVERY branch, guard clause,
     error path, boundary condition, edge case, and fallback. Reference
     the source line numbers.
3.3. Read EVERY existing test file that covers these modules (unit, integration,
     e2e). Do NOT guess — actually read the test files and list what scenarios
     they already cover.
3.4. Produce a gap table per source module with columns:
     `[#, Scenario, Why It Matters, Source Line, Layer (Unit/Integ/E2E), Status (✅ covered / ❌ missing)]`
3.5. Propose integration tests that exercise the seams between modules
     (e.g., CLI → service → DB round-trip, service → prompt builder → adapter).
3.6. Propose e2e tests for the user-facing workflows this feature enables.
3.7. Do NOT invent arbitrary test counts. Every scenario must trace to real code.
3.8. Present the FULL list — do NOT limit to 10 items.
3.9. **STOP and wait for the HITL response.** Present the gap analysis to the
     user and wait for their feedback before proceeding. Do NOT continue
     until the user confirms or provides changes.
     Include in the HITL notification:
     - The full gap table
     - Your reasoning for each gap's priority
     - Any recommendations for deferral vs. immediate fix
     - Any pre-existing issues discovered during the analysis

> [!CAUTION]
> **HARD GATE:** You MUST use `notify_user` to present the gap analysis
> and WAIT for the user's response. Do NOT proceed to Phase 4 without
> explicit user confirmation. This is non-negotiable.

## Phase 4: Implement Missing Tests

// turbo-all

4.1. Implement ALL missing tests identified in Phase 3 (after HITL confirmation).
     Follow existing test patterns (fixtures, helpers, naming conventions)
     already established in the test files.
4.2. Run ruff on any new or modified test files to ensure lint-clean:
     ```
     python -m ruff check tests/
     ```
     Fix any errors immediately!

## Phase 5: Run Full Test Suite

// turbo-all

5.1. Run the full test suite:
     ```
     python -m pytest --tb=short -q
     ```
     ALL tests MUST pass — no exceptions!

## Phase 6: Documentation Updates

// turbo-all

6.1. Update `docs/test_coverage_matrix.md` with the corrected test count and
     any new entries for modules added or modified in this feature. Do not forget
     to update the story -> unit/integr/e2e/... matrices!

6.2. Review and update these documents if they are affected by the feature:
     - `README.md` — features list, CLI commands table, project structure
     - `docs/quickstart.md` — new workflows or commands
     - `docs/testing_guide.md` — new test patterns or quality gates
     - `docs/proposals/specweaver_roadmap.md` — feature completion status
     - `docs/proposals/roadmap/phase_3_feature_expansion.md` — milestone tracking
     - Any feature-specific implementation plan or design doc

6.3. **MANDATORY: Update the architecture reference** if this feature changed
     any module placement, dependency direction, layer boundaries, security
     patterns, or dispatch mechanisms:
     ```
     docs/architecture/architecture_reference.md
     ```
     Add new anti-patterns discovered during this feature. Update the sub-layer
     structure diagram if new modules were added or moved.

> [!IMPORTANT]
> Every bug, lint error, complexity violation, or oversized file MUST be fixed
> regardless of whether it is pre-existing or introduced by this feature.
> No inherited problems are acceptable!

## Phase 7: Walkthrough

7.1. Write or update the walkthrough artifact documenting:
     - What was changed and why
     - All test results
     - **HITL gate decisions**: For EVERY HITL gate (steps 1.8 and 3.9),
       document what was found, the reasoning presented to the user,
       and the user's decision. If a gate was skipped or auto-approved,
       document the justification and flag it so the user can
       retroactively review the decision.

> [!WARNING]
> The walkthrough MUST transparently document all HITL gate interactions.
> If a gate was bypassed, explain why and what the user should review.