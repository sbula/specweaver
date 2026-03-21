---
description: Run a pre-commit quality gate for the current feature before marking it done.
---

# Pre-Commit Quality Gate

Before we commit, run a full pre-commit quality gate for the feature we just built.
This workflow covers test gap analysis, linting, complexity, file size, and documentation.

## Phase 1: Code Quality Checks

// turbo-all

1. Run **ruff lint** on the entire repo:
   ```
   python -m ruff check src/ tests/
   ```
   Every error MUST be fixed — no exceptions, regardless of whether the error
   is pre-existing or newly introduced!

2. Run **mypy type check** on the source tree:
   ```
   python -m mypy src/
   ```
   Every error MUST be fixed — no exceptions!

3. Run **file complexity** check (C901 max complexity = 10):
   ```
   python -m ruff check src/ --select C901
   ```
   Every violation MUST be fixed by extracting helper functions!

4. Run **lines-of-code per file** check (max 500 lines per source file):
   ```
   python -c "from pathlib import Path; files = [f for f in Path('src').rglob('*.py') if f.stat().st_size > 0]; big = [(f, len(f.read_text(encoding='utf-8').splitlines())) for f in files if len(f.read_text(encoding='utf-8').splitlines()) > 500]; [print(f'{loc} lines: {f}') for f, loc in sorted(big, key=lambda x: -x[1])]; print(f'{len(big)} file(s) over 500 lines') if big else print('All files within 500-line limit')"
   ```
   Files over 500 lines MUST be refactored by splitting into smaller modules!

## Phase 2: Test Gap Analysis

5. Read EVERY source file that was created or modified for this feature.
6. For each file, go line-by-line and identify EVERY branch, guard clause,
   error path, boundary condition, edge case, and fallback. Reference
   the source line numbers.
7. Read EVERY existing test file that covers these modules (unit, integration,
   e2e). Do NOT guess — actually read the test files and list what scenarios
   they already cover.
8. Produce a gap table per source module with columns:
   `[#, Scenario, Why It Matters, Source Line, Layer (Unit/Integ/E2E), Status (✅ covered / ❌ missing)]`
9. Propose integration tests that exercise the seams between modules
   (e.g., CLI → service → DB round-trip, service → prompt builder → adapter).
10. Propose e2e tests for the user-facing workflows this feature enables.
11. Do NOT invent arbitrary test counts. Every scenario must trace to real code.
12. Present the FULL list — do NOT limit to 10 items.
13. **STOP and wait for the HITL response.** Present the gap analysis to the
    user and wait for their feedback before proceeding. Do NOT continue
    until the user confirms or provides changes.

## Phase 3: Implement Missing Tests

14. Implement ALL missing tests identified in Phase 2 (after HITL confirmation).
    Follow existing test patterns (fixtures, helpers, naming conventions)
    already established in the test files.
15. Run ruff on any new or modified test files to ensure lint-clean:
    ```
    python -m ruff check tests/
    ```
    Fix any errors immediately!

## Phase 4: Run Full Test Suite

16. Run the full test suite:
    ```
    python -m pytest --tb=short -q
    ```
    ALL tests MUST pass — no exceptions!

## Phase 5: Documentation Updates

17. Update `docs/test_coverage_matrix.md` with the corrected test count and
    any new entries for modules added or modified in this feature.

18. Review and update these documents if they are affected by the feature:
    - `README.md` — features list, CLI commands table, project structure
    - `docs/quickstart.md` — new workflows or commands
    - `docs/testing_guide.md` — new test patterns or quality gates
    - `docs/proposals/specweaver_roadmap.md` — feature completion status
    - `docs/proposals/roadmap/phase_3_feature_expansion.md` — milestone tracking
    - Any feature-specific implementation plan or design doc

> [!IMPORTANT]
> Every bug, lint error, complexity violation, or oversized file MUST be fixed
> regardless of whether it is pre-existing or introduced by this feature.
> No inherited problems are acceptable!