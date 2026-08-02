# Task List: TECH-001 SF-04 — Eliminate `core.config` Circular Dependencies

- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-001/TECH-001_sf04_implementation_plan.md
- **Commit Boundaries**: 1 (single atomic commit — a partial move would leave the repo in a
  half-broken state, same reasoning TECH-006 SF-01 used for its own single-atomic-commit choice)

## Tasks

- [x] **T1 (RED)**: Add the acyclicity regression test to `tests/unit/test_architecture.py` —
  asserts no module-scope `import specweaver.infrastructure.llm` / `import specweaver.core.flow`
  / `import specweaver.workspace` inside `core/config/*.py` (excluding `core/config/bootstrap/`
  and `core/config/interfaces/`, both separately-scoped boundaries). Must FAIL right now — the
  cycle is still live. Run it, confirm red, before touching anything else.

  **Test matrix** (Red/Blue task-list review, Cycle 1):
  - *Happy path*: `core.config` has zero forbidden imports → test passes (post-move state).
  - *Boundary/edge*: an empty `.py` file in the scanned tree doesn't crash the AST walk; a file
    with only docstrings/comments (no imports at all) is handled the same way.
  - *Graceful degradation*: N/A for a static self-check with no external I/O beyond reading its
    own repo's source files — justified, not skipped.
  - *Hostile/wrong input*: N/A — no user-controlled input, this is a repo-structure invariant
    check, not a function processing external data — justified, not skipped.
  - **Critical correctness detail**: exclude `if TYPE_CHECKING:`-guarded imports from the scan,
    the same fix `check_coupling.py` already had to make (see its own test file's docstring: naive
    AST import-counting flagged 3 cycles that didn't exist at runtime). Use the same AST-walk
    technique — skip any `Import`/`ImportFrom` node whose parent `If` test is `TYPE_CHECKING` (or
    `typing.TYPE_CHECKING`).

> [!NOTE]
> **T2–T9 intentionally leave the suite red mid-sequence** — this is a single atomic commit
> (see header), not 8 independent green checkpoints. `db_bootstrap.py`/`settings_loader.py` are
> moved (T3/T4) before every caller is updated (T7/T8), so imports will fail if you run the suite
> between those steps. That's expected. Do not treat it as a regression to fix task-by-task; only
> T1 (before) and T10 (after) are real red/green checkpoints.
>
> **`core/config/interfaces/cli.py` is explicitly out of scope for T7/T8.** It imports
> `LlmRepository`/`TaskType` directly (not via `db_bootstrap`/`settings_loader`), and lives on the
> already-permitted, separate `core.config.interfaces` tach boundary. T7/T8's grep pattern won't
> match it — leave it untouched.

- [x] **T2**: Scaffold `src/specweaver/core/config/bootstrap/` — `context.yaml` only, NO
  `__init__.py` (corrected during dev: the repo uses implicit namespace packages throughout,
  confirmed `core/config/interfaces/` has none either — matching that convention instead of the
  plan's original text).

- [x] **T3**: Move `core/config/db_bootstrap.py` → `core/config/bootstrap/db_bootstrap.py`
  verbatim. Preserve line 9's `import specweaver.workspace.memory.store  # noqa: F401` exactly
  (side-effect-only, not dead code — Red/Blue RED-1.5).

- [x] **T4**: Move `core/config/settings_loader.py` → `core/config/bootstrap/settings_loader.py`
  verbatim.

- [ ] **T5**: Update `tach.toml`:
  - `specweaver.core.config`'s `depends_on` → `[]`.
  - New `[[modules]]` block: `specweaver.core.config.bootstrap`, `depends_on = [core.flow,
    infrastructure.llm, workspace, workspace.memory]`.
  - New `[[interfaces]]` block exposing the 6 functions (optional hardening, not required for
    `tach check` — Red/Blue RED-2.1 — but do it, matches the `.interfaces` sibling convention).
  - Add `specweaver.core.config.bootstrap` to the `depends_on` list of all 7 consumer boundaries:
    `interfaces.cli`, `interfaces.api`, `assurance.validation.interfaces`,
    `assurance.standards.interfaces`, `core.flow.interfaces`, `workflows.review.interfaces`,
    `workflows.implementation.interfaces` (Red/Blue RED-1.1, CRITICAL — the one strictly-required
    tach.toml change).

- [ ] **T6**: Update `core/config/context.yaml`: `exposes` drops `load_settings`.

- [ ] **T7**: Update the 8 production call sites (import path only, `core.config.db_bootstrap` /
  `settings_loader` → `core.config.bootstrap.db_bootstrap` / `settings_loader`):
  `interfaces/cli/_core.py`, `assurance/validation/interfaces/cli_drift.py`,
  `assurance/standards/interfaces/cli.py`, `core/flow/interfaces/cli.py` (3 sites),
  `interfaces/api/v1/review.py`, `interfaces/api/v1/implement.py`,
  `workflows/review/interfaces/cli.py` (2 sites), `workflows/implementation/interfaces/cli.py`.

- [ ] **T8**: Update all test files referencing the old paths. Re-run the grep from the plan's
  Blast Radius section (`db_bootstrap|settings_loader` across `tests/`) at the start of this task
  — do not trust the "62" count as a hardcoded list, re-derive it, since new tests may have landed
  since the plan was written. Update both `from ... import` lines and string-literal
  `monkeypatch.setattr("specweaver.core.config.db_bootstrap...", ...)` /
  `patch("specweaver.core.config.settings_loader...", ...)` targets.

- [ ] **T9**: Move `tests/unit/core/config/test_settings_loader.py` →
  `tests/unit/core/config/bootstrap/test_settings_loader.py` (path + internal imports only, no
  test-logic change).

- [x] **T10 (GREEN)**: Re-run T1's regression test — PASSED. `tach check` — 2 real gaps found by
  actually running it (neither the plan's nor the task-list's Red/Blue review caught these by
  reasoning alone — empirical verification beat analysis):
  1. `settings_loader.py` also imports `SpecWeaverSettings`/`LLMSettings`/etc. from
     `specweaver.core.config.settings` (the parent module) — missed entirely in Research Notes,
     which only checked for `infrastructure.llm`/`core.flow`/`workspace` imports. Added
     `specweaver.core.config` to `core.config.bootstrap`'s `depends_on`.
  2. 3 of the 7 consumer boundaries (`assurance.standards.interfaces`,
     `workflows.implementation.interfaces`, `workflows.review.interfaces`) had their *only* real
     runtime use of `core.config` be via `settings_loader` (now `.bootstrap`) — their remaining
     `core.config` references were `TYPE_CHECKING`-only, which tach correctly doesn't count as
     real usage. Removed the now-genuinely-unused `specweaver.core.config` entry from all 3.

  `tach check` → `[OK] All modules validated!` after both fixes.

  **Unplanned detour (2026-08-02, user-directed):** `python scripts/tests.py cb TECH-001 --kind
  refactor --all` then BLOCKED on "a refactor modified 66 test file(s)" — the check flags ANY
  diff to a test `.py` file, with no way to distinguish a `git mv`-triggered import-path update
  from an assertion quietly weakened to hide a bug. User explicitly rejected both silently
  bypassing it and leaving it as-is ("it blocks us to extend existing tests... think of something
  else"). Fixed `scripts/tests.py`'s `refactor_violations` (TDD, `tests/unit/scripts/test_tests_runner.py`,
  67 tests): a hunk is now "safe" (does not block) if it's either a pure addition (new test
  coverage, nothing existing touched) or a 1:1 line pairing that differs only by dotted-path
  tokens (a relocated import). Any assertion/logic change or deletion still blocks, proven by
  dedicated adversarial tests. Re-ran the gate — 191 tests pass, 0 blocked (down from 66 flagged,
  correctly, to 0).

  Full test suite: 191 passed at the commit-boundary gate.

  **Phase 5 (code quality, `python scripts/quality.py cb`)**: found and fixed everything
  attributable to this commit:
  - 57 ruff `I001` import-sort errors (sed left imports unsorted) — `ruff check --fix`.
  - 6 files needing `ruff format`.
  - `scripts/tests.py` pushed from under-600 to 662 lines (RED threshold) by the refactor-check
    fix — extracted `_parse_hunks`/`_is_safe_hunk`/`_is_import_path_only_change`/
    `refactor_violations` into a new `scripts/_refactor_diff_safety.py` (105 lines), loaded via a
    path-based `_load_sibling()` helper (typed `-> ModuleType`, which mypy permits arbitrary
    attribute access on — no suppression needed). `tests.py` now 584 lines.
  - `suppressions` ratchet `type-ignore:attr-defined: 7 -> 8`: traced to my own earlier SIGBREAK
    commit's `# type: ignore[attr-defined]` on `signal.SIGBREAK` in `_signals.py` — turned out
    fully redundant, since that file already carries a file-level `# mypy: ignore-errors`. Removed
    the inline ignore entirely; verified `mypy` still reports zero issues for the file.

  **Confirmed pre-existing and unrelated** (via `git stash` — identical failures with or without
  any of this session's changes applied, across ~50 files in domains never touched: graph/
  topology, standards analyzers, LLM adapters, sandbox): `complexipy` (98 functions/68 files) and
  `cycles` (4 dependency cycles). Per user direction, minted **`TECH-023`** (complexipy) and
  **`TECH-024`** (cycles) to track this rather than unilaterally fixing ~50 unrelated files inline
  or silently ignoring the pre-commit skill's "no inherited problems are acceptable" instruction.
  `TECH-023` excludes `TECH-020`'s and `TECH-006` SF-02's already-owned functions; `TECH-024`
  notes its cycle-of-6 overlaps `TECH-020`/`TECH-015`'s files (coordinate, don't duplicate).

  **After minting the tickets, the refactor gate itself still had 3 more real bugs**, each found
  by re-running `python scripts/tests.py cb TECH-001 --kind refactor --all` for real and reading
  what actually blocked, not by reasoning about it in the abstract:
  1. `_is_safe_hunk`'s whole-hunk-side blob comparison couldn't see an import-sorter split a
     single line-move into a separate addition hunk and deletion hunk elsewhere in the same file
     — fixed by adding `_is_safe_file_diff` (multiset-matching hunk signatures across the WHOLE
     file, not just within one hunk).
  2. That first fix over-joined: a hunk-side with TWO independent relocated import lines got
     treated as one blob, so neither could match its own separate counterpart elsewhere — fixed
     by `_logical_line_groups` (bracket-depth-aware splitting: a formatter's genuine multi-line
     reflow of ONE statement stays one unit; two balanced, independent statements bundled into the
     same hunk split apart).
  3. Two formatting-only artifacts still tripped exact-string comparison after grouping was fixed:
     `ruff format`'s Black-style trailing comma before a closing bracket, and Python's *required*
     wrapping parens for a multi-line `from x import (...)` that the single-line form never needs.
     Both are pure line-wrap syntax, not content — fixed by stripping `()[]{},` entirely from each
     signature once grouping has already used bracket depth to decide the groups.
  4. Found only via direct debugging (not test-writing): whitespace was being stripped BEFORE
     dotted-path tokens, gluing adjacent words across the join (`"from specweaver.x"` ->
     `"fromspecweaver.x"`) and making the path regex misidentify `from` as part of the path,
     over-stripping. Fixed by reordering: strip paths first (spaces still separate words), THEN
     whitespace, THEN wrapping punctuation.

  Final state: `scripts/_refactor_diff_safety.py` — 81 tests in
  `tests/unit/scripts/test_tests_runner.py`, `python scripts/tests.py cb TECH-001 --kind refactor
  --all` exits 0, 191 tests passed, zero files blocked.

## Commit Boundary 1 (all tasks T1–T10)

Test gate: `python scripts/tests.py cb TECH-001 --kind refactor --all`

> [!NOTE]
> **`--all`, not the default `cb` scoping** (Red/Blue task-list review, Cycle 2): this commit
> touches ~70 files across ~10 different packages (`core.config`, `core.config.bootstrap`,
> `interfaces.cli`, `interfaces.api`, `core.flow.interfaces`, `assurance.validation.interfaces`,
> `assurance.standards.interfaces`, `workflows.review.interfaces`,
> `workflows.implementation.interfaces`, plus the moved test files). Trusting the default
> package-touched scoping risks under-selecting given the breadth — this is exactly the case the
> `dev` skill's own guidance names: "if a batch touched a widely-depended-on module and you want
> the sweep now, `--all` is the honest way to ask for it." `core.config` is about as
> widely-depended-on as a module gets.

Pre-commit: full `specweaver-pre-commit` skill, all 7 phases.

---

## Red/Blue Team Review (task list, Phase 2.4)

**Cycle 1**: 1 MEDIUM (T1's regression test needed a TYPE_CHECKING exclusion, matching
`check_coupling.py`'s own established fix for the same false-positive class) + 3 LOW (adversarial
test matrix for T1 unspecified; mid-sequence red state unexplained; `core/config/interfaces/cli.py`
scope not explicitly confirmed out-of-scope). All 4 fixed inline above.

**Cycle 2**: Re-verified Cycle 1 fixes are correctly applied. 1 new finding: default `cb` test
scoping risks under-selecting given ~70 files across ~10 packages — fixed by specifying `--all`
above. Swept remaining focus areas (task granularity, dependency ordering, YAGNI — e.g. considered
and rejected an explicit "old import path raises ImportError" negative test as redundant with T1's
structural guard) with no further findings.

Cycle 2 totals: 0 CRITICAL, 0 HIGH, 0 MEDIUM, 1 LOW → below all continuation thresholds → **STOP**.
Review complete after 2 cycles.
