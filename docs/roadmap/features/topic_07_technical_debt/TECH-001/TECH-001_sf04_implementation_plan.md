# Implementation Plan: Domain-Driven Design Unification [SF-04: Eliminate `core.config` Circular Dependencies]
- **Feature ID**: TECH-001
- **Sub-Feature**: SF-04 — Eliminate `core.config` Circular Dependencies
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-001/TECH-001_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-001/TECH-001_sf04_implementation_plan.md
- **Status**: APPROVED (2026-08-02, after 2-cycle Red/Blue review, 1 CRITICAL fixed pre-implementation)

## Preconditions

`python scripts/check_story_preconditions.py TECH-001` is green (2026-08-02). Two real blockers
were found and fixed on the way here, both landed as their own commits before this plan:
1. The script didn't recognize `TECH-NNN` IDs at all (`86133657`).
2. TECH-001's declared e2e proof suite had a Windows-only skip with no working replacement signal
   (`1f90cfc5`) — fixed by wiring Ctrl+Break (`SIGBREAK`) through the same graceful-shutdown path
   as SIGINT/SIGTERM, since Windows cannot deliver SIGINT to a child process without also
   signalling the caller.

## Research Notes (Phase 0)

**Note on Phase 1.2**: `docs/architecture/architecture_reference.md` (the file this skill's Phase
1.2 step names) was deleted by TECH-008 and replaced by the numbered `docs/architecture/NN_*/`
directory structure — this is the exact dangling reference `TECH-019` documents across six skill
instruction sites. Substituted the current structure below; not fixing the skill file itself here
(out of scope, already tracked by TECH-019).

### The declared cycle, traced to exact files

`tach.toml` declares (verified against `src/`, not just the toml):
- `core.config` → depends_on → `core.flow`, `infrastructure.llm` (tach.toml:34)
- `core.flow` → depends_on → `core.config` (tach.toml:42) — natural direction, flow needs settings
- `infrastructure.llm` → depends_on → `core.config` (tach.toml:54) — natural direction, LLM adapters need `SpecWeaverSettings`/`LLMSettings`

**A third cycle, found during this plan's own Red/Blue review (RED-1.2), never named anywhere
before**: `specweaver.workspace` → depends_on → `specweaver.core.config` (tach.toml:126) —
`workspace/store.py` and `workspace/memory/store.py` import `StrictISODateTime`,
`register_fk_pragma_listener`, `get_profile` from `core.config.database`/`core.config.profiles`.
`core.config`'s own `depends_on` (tach.toml:34) already includes `workspace`/`workspace.memory` too
— same two files as below cause it. This was never flagged by TECH-001, TECH-022, or the
2026-07-31 registry audit; all three only checked `core.config ⇄ infrastructure.llm` and
`core.config ⇄ core.flow`. **The fix below resolves all three cycles, not two** — confirmed
`db_bootstrap.py`/`settings_loader.py` are the *only* two files in `core.config` (excluding the
separate `.interfaces` sub-boundary) touching `workspace` at all, so moving both files to
`core.config.bootstrap` drops `workspace`/`workspace.memory` from `core.config`'s `depends_on`
entirely, same as `core.flow`/`infrastructure.llm`. `core.config`'s `depends_on` becomes `[]`
after this SF — matching its `context.yaml`'s `consumes: []` claim exactly, for the first time.

`core.config`'s own `context.yaml` declares `archetype: pure-logic` and `consumes: []` — the module
is supposed to be a pure leaf. It is not, in code, today. Two files cause the entire
`core.config → {core.flow, infrastructure.llm, workspace, workspace.memory}` edge (see the third
cycle note above for the `workspace` half):

1. **`core/config/db_bootstrap.py`** (lines 13-15):
   ```python
   from specweaver.core.flow.store import Base as FlowBase
   from specweaver.infrastructure.llm.store import Base as LlmBase
   from specweaver.infrastructure.llm.store import LlmProfile
   ```
   Used only to call `.metadata.create_all()` for every domain's SQLAlchemy `Base` in one place
   (`bootstrap_database()`), plus seed default `LlmProfile` rows. This single file causes BOTH
   cycle edges by itself.

2. **`core/config/settings_loader.py`** (line 20):
   ```python
   from specweaver.infrastructure.llm.store import LlmRepository
   ```
   Used in `load_settings_async()` to read the project's LLM profile/routing config from the DB
   as part of building `SpecWeaverSettings`. Causes the `core.config → infrastructure.llm` edge
   independently of (1).

`core/config/interfaces/cli.py` also imports `LlmRepository`/`TaskType`, but that file is on the
**separate** `specweaver.core.config.interfaces` tach boundary (tach.toml:37-38), which already
legally depends on `infrastructure.llm`. It is not part of the `core.config` pure-logic violation
and is out of scope for this SF.

`core/config/database.py` and `core/config/settings.py` do **not** import `infrastructure.llm` or
`core.flow` today — confirmed by direct grep, zero matches. `docs/architecture/06_lessons_and_future/known_boundary_violations.md` names exactly these two files ("Inline Imports (Monolith
Purge)" and "Stability Direction Violation" rows) as the site of this violation; that doc is stale
— the violation is real but moved to `db_bootstrap.py`/`settings_loader.py` at some point (most
likely during TECH-001 SF-01's own "Deconstruct Config Monolith" extraction). **Flagged as a Phase
2 finding below (#9), not fixed in this plan** — updating that architecture doc is not in SF-04's
scope, but leaving it pointing at the wrong files misleads the next reader the same way TECH-019
describes for the skill references.

### Blast radius — every caller of the two files

**Production code — 8 call sites**, all already in `interfaces/*` layers (CLI, API, or
workflow-interfaces), none inside `core.config` or `core.flow`'s core modules:

```
src/specweaver/interfaces/cli/_core.py:27          from ...db_bootstrap import get_db
src/specweaver/assurance/validation/interfaces/cli_drift.py:90   from ...settings_loader import load_settings
src/specweaver/assurance/standards/interfaces/cli.py:64          from ...settings_loader import load_settings
src/specweaver/core/flow/interfaces/cli.py:91,307,512             from ...settings_loader import load_settings
src/specweaver/interfaces/api/v1/review.py:37                    from ...settings_loader import load_settings_async
src/specweaver/interfaces/api/v1/implement.py:38                 from ...settings_loader import load_settings_async
src/specweaver/workflows/review/interfaces/cli.py:166,260         from ...settings_loader import load_settings
src/specweaver/workflows/implementation/interfaces/cli.py:185     from ...settings_loader import load_settings
```

**Tests — 62 files, not 8.** `interfaces.cli`, `interfaces.api`, and the various `*.interfaces`
boundaries are already permitted (per `docs/architecture/03_system_topology/hard_dependency_rules.md`)
to depend on everything the production call sites touch, so those 8 are genuinely mechanical
import-path swaps. But a broader grep across `tests/` for the same module paths returns **62
files**, not 8 — most patch these functions directly by their old string path, e.g.:
```python
monkeypatch.setattr("specweaver.core.config.db_bootstrap.get_db", lambda: db)
patch("specweaver.core.config.settings_loader.load_settings", return_value=sentinel)
```
Every one of these needs its string path (and, where present, its `from ... import` line) updated
to the new `core.config.bootstrap.*` location alongside the move. This is still a uniform,
mechanical sweep — and any miss fails loudly (the patched attribute simply won't exist at the old
path, `AttributeError` at test setup, not a silent pass) — but it is a meaningfully larger diff
than the original 8-site estimate suggested. Flagging the corrected size rather than understating
it going into dev.

Only one dedicated unit test file exists for either module today:
`tests/unit/core/config/test_settings_loader.py` (no `test_db_bootstrap.py` — `db_bootstrap.py`'s
behavior is instead covered indirectly through the many integration/e2e files above, plus
`tests/e2e/test_cli_bootstrap_e2e.py` by name). Both move to `tests/unit/core/config/bootstrap/`.

`migrate_legacy_config()` (also in `settings_loader.py`, also uses `LlmRepository`) has **zero**
callers anywhere in `src/` today — confirmed by a dedicated grep beyond the 8-site sweep. It moves
with the rest of the file; no separate caller-side fix needed.

### Precedent: this is not a new decision, it's a known-deferred one

`known_boundary_violations.md` already lists this exact class of problem as **DEFERRED, direction
already chosen**: *"Pending dependency injection refactoring to pass domain stores dynamically"*
and *"Pending dependency injection refactoring for DB initialization."* Separately, **ADR-002**
(`docs/architecture/07_architectural_decision_records/adr_002_composition_root_vs_factories.md`,
accepted for TECH-006) already established the pattern for exactly this shape of problem: the
**Composition Root** (the outermost delivery-mechanism layer — CLI/API) is the layer legally
allowed to reach into every domain's concrete stores; domain-internal code stays ignorant of where
its dependencies come from and receives them pre-hydrated. This plan follows both: dependency
injection, with the composition root (`interfaces.cli._core`, which already imports `get_db`)
supplying the concrete cross-domain pieces.

## Proposed Approach

Move the *cross-domain-store-touching* code out of `core.config`'s pure-logic boundary into a new
`core.config.bootstrap` sub-module (mirroring the existing `core.config.interfaces` sub-boundary
pattern) that is explicitly allowed to depend on `core.flow`, `infrastructure.llm`, `workspace`,
`workspace.memory` — exactly `core.config`'s *current* (over-broad) `depends_on` list, narrowed
down to live in the one place that actually needs it. `core.config` itself drops those 4 entries
from `tach.toml` entirely, matching its own `context.yaml`'s `consumes: []` claim for the first
time.

- `core/config/bootstrap/__init__.py` — new package.
- `core/config/bootstrap/db_bootstrap.py` — moved verbatim from `core/config/db_bootstrap.py`
  (no logic change — same function signatures, same behavior).
- `core/config/bootstrap/settings_loader.py` — moved verbatim from `core/config/settings_loader.py`.
- `core/config/bootstrap/context.yaml` — new, `archetype: pure-logic` is wrong here (it does real
  I/O — DB reads/writes); `archetype: adapter` matching `core.config.interfaces`'s own archetype,
  `consumes: [core.flow, infrastructure.llm, workspace, workspace.memory]`.
- `tach.toml`: remove `core.config`'s 4 `depends_on` entries; add a new `[[modules]]` block for
  `specweaver.core.config.bootstrap` with those same 4 entries.
- Update the 8 call sites above: `from specweaver.core.config.db_bootstrap import get_db` →
  `from specweaver.core.config.bootstrap.db_bootstrap import get_db` (and the `settings_loader`
  equivalent). Pure import-path edits, zero logic changes.
- Keep `core/config/db_bootstrap.py` and `core/config/settings_loader.py` as thin re-export shims
  for one commit cycle? **No** — Phase 2 question #3 below asks whether to keep backward-compat
  shims; default proposal is NOT to, since every call site is being updated in the same commit
  and grep confirms there are no other consumers.

No behavior changes anywhere. This is a pure move-and-rename plus a `tach.toml`/`context.yaml`
boundary correction. TDD proof: existing tests for `db_bootstrap.py`/`settings_loader.py` (find
and move alongside), plus a new architecture test asserting `core.config`'s own module-level
imports contain no reference to `infrastructure.llm` or `core.flow` (the regression guard — so
this cycle cannot silently regrow, the same failure mode TECH-006's Finding 3 shows can happen
when there's no such guard).

## Test Plan

- Move `tests/unit/core/config/test_settings_loader.py` to
  `tests/unit/core/config/bootstrap/test_settings_loader.py` (no `test_db_bootstrap.py` exists —
  confirmed via Glob, that module's behavior is covered indirectly through the integration/e2e
  files listed above).
- Update all 62 test files that reference `specweaver.core.config.db_bootstrap` /
  `specweaver.core.config.settings_loader` by string path (`monkeypatch.setattr(...)`,
  `patch(...)`) or direct import, to the new `specweaver.core.config.bootstrap.*` paths.
- New unit test: `core.config`'s package (excluding the new `bootstrap` sub-package) contains no
  `import specweaver.infrastructure.llm` / `import specweaver.core.flow` at module scope —
  AST-based, same technique as `scripts/check_coupling.py`'s cycle detector, so it survives
  refactors that a plain grep would miss (e.g. import aliasing). Lands in
  `tests/unit/test_architecture.py` (Resolved Decision #5).
- `tach check` must pass with `core.config`'s new, narrower `depends_on`.
- Full existing suite must pass unmodified (NFR: zero regression, same bar as SF-01/02/03).

## Proposed Changes (file-tagged)

| File | Tag | Change |
|---|---|---|
| `src/specweaver/core/config/bootstrap/__init__.py` | NEW | Empty package init |
| `src/specweaver/core/config/bootstrap/db_bootstrap.py` | NEW | Verbatim move of `core/config/db_bootstrap.py` |
| `src/specweaver/core/config/bootstrap/settings_loader.py` | NEW | Verbatim move of `core/config/settings_loader.py` |
| `src/specweaver/core/config/bootstrap/context.yaml` | NEW | `archetype: adapter`, `consumes: [core.flow, infrastructure.llm, workspace, workspace.memory]`, `forbids: [specweaver/sandbox/*]` (RED-1.3) |
| `src/specweaver/core/config/db_bootstrap.py` | DELETE | Superseded by `bootstrap/db_bootstrap.py`. **Preserve line 9's `import specweaver.workspace.memory.store  # noqa: F401` exactly** — side-effect-only import for SQLAlchemy model registration, not dead code (RED-1.5) |
| `src/specweaver/core/config/settings_loader.py` | DELETE | Superseded by `bootstrap/settings_loader.py` |
| `src/specweaver/core/config/context.yaml` | MODIFY | `exposes` drops `load_settings` (moves to the new package's `exposes`); `depends_on` becomes `[]` — matches its own `consumes: []` claim for the first time, since `db_bootstrap.py`/`settings_loader.py` were the *only* two files touching `workspace` from this boundary too (RED-1.2, see Research Notes) |
| `tach.toml` | MODIFY | Remove `core.flow`/`infrastructure.llm`/`workspace`/`workspace.memory` from `specweaver.core.config`'s `depends_on` (→ `[]`); add a new `[[modules]]` block for `specweaver.core.config.bootstrap` with those 4; add an `[[interfaces]] expose=[...]` allowlist entry mirroring `core.config.interfaces`'s (tach.toml:177-178), naming exactly: `db_bootstrap.get_db`, `db_bootstrap.bootstrap_database`, `settings_loader.load_settings`, `settings_loader.load_settings_async`, `settings_loader.load_settings_for_active`, `settings_loader.migrate_legacy_config` — recommended hardening matching the `.interfaces` sibling's stricter convention, NOT strictly required for `tach check` to pass: verified `core.config` itself currently has no such block at all and `tach check` passes clean regardless, so this allowlist is opt-in precision, not a correctness requirement (RED-1.4, downgraded from an earlier draft that conflated it with RED-1.1 — see RED-2.1); **add `specweaver.core.config.bootstrap` to the `depends_on` list of all 7 consumer boundaries** — `interfaces.cli`, `interfaces.api`, `assurance.validation.interfaces`, `assurance.standards.interfaces`, `core.flow.interfaces`, `workflows.review.interfaces`, `workflows.implementation.interfaces` (RED-1.1, CRITICAL, and the ONLY tach.toml change that is strictly required for `tach check` to pass — omitting it fails `tach check` for all 7 immediately after the move) |
| 8 production call sites (listed in Blast Radius) | MODIFY | Import path only: `core.config.db_bootstrap`/`settings_loader` → `core.config.bootstrap.db_bootstrap`/`settings_loader` |
| 62 test files (pattern documented in Blast Radius) | MODIFY | Same import-path swap, including string-literal `monkeypatch.setattr(...)`/`patch(...)` targets |
| `tests/unit/core/config/test_settings_loader.py` → `tests/unit/core/config/bootstrap/test_settings_loader.py` | MODIFY (relocate) | Path + internal import updates only, no test-logic change |
| `tests/unit/test_architecture.py` | MODIFY | New test: no module-scope `infrastructure.llm`/`core.flow` import inside `core.config` (excluding `bootstrap/`) |
| `docs/architecture/06_lessons_and_future/known_boundary_violations.md` | DEFERRED | Backlog item — not touched by this SF |

## Phase 5: Final Consistency Check

**5.0 — FR/NFR/AD/RT coverage**: SF-04's single FR (FR-9, added to the design doc alongside this
plan) is fully covered by the Proposed Changes table above. No NFRs beyond the ticket's blanket
"zero regression" (NFR-1 in the parent design doc) apply — this SF introduces no new external
dependency, no new data model, no new pipeline surface. No prior Architectural Decisions in the
TECH-001 design doc conflict with this SF (AD-1/AD-2 concern CLI root and `loom`→`sandbox`
renaming, unrelated to this boundary). No Risk/Trade-off table exists for SF-04 specifically
(none was carried over from the design doc, which predates this SF); the equivalent risk content
lives in this plan's own Blast Radius section instead.

**5.1 — Open questions**: All decisions are resolved and documented inline in the Resolved
Decisions section above (9/9, including 2 independently re-verified during merge). No
unresolved ambiguities remain.

**5.1a — Agent handoff risk**: A fresh agent starting only from this document has everything
needed: exact file paths (Research Notes, Proposed Changes table), the exact grep patterns used
to derive the 8+62 file lists (`from specweaver\.core\.config\.db_bootstrap import|...settings_loader import|...` for production, plus the broader `db_bootstrap|settings_loader` sweep across
`tests/` for the 62), the exact new `context.yaml`/`tach.toml` shape, and the rejected alternatives
with reasons (so the agent doesn't reconsider and re-litigate option (B)/(C) mid-implementation).
One residual risk: the plan does not enumerate all 62 test file paths verbatim (only the pattern
and 2 confirmed examples) — a fresh agent MUST re-run the grep rather than trust a stale hardcoded
list, which is intentional (a hardcoded list would itself rot the moment a new test is added before
dev starts).

**5.2 — Architecture and future compatibility**: `core.config.bootstrap` depends on `core.flow`,
`infrastructure.llm`, `workspace`, `workspace.memory` — none of those (nor anything they
transitively depend on) import `core.config.bootstrap` back; all 8 production callers of the
moved functions are already in `interfaces/*` layers, never inside `core.flow`'s or
`infrastructure.llm`'s core modules. Genuinely acyclic, verified by tracing the actual call sites
(not just trusting the tach.toml declaration, per this whole session's own standard). Checked
against the next two roadmap candidates in the Active Routing Queue (`C-VAL-05`, `E-VAL-03`) and
TECH-005/TECH-006 (the next two items in this same audit pass) — none touch `core.config`,
`db_bootstrap`, or `settings_loader`.

**5.2a — Architecture principles**:
- *DDD*: bounded contexts respected — `core.config` (pure settings model) vs. `core.config.bootstrap`
  (DB/composition wiring across domains) are now two distinct, correctly-named contexts instead of
  one conflated one. Ubiquitous language matches the sibling `core.config.interfaces` precedent.
- *KISS*: the smallest change that removes the declared cycle — a move plus a boundary edit, no
  new abstraction layer, no Protocol/DI machinery invented (Resolved Decision #1 explicitly
  rejected the heavier "true DI" option for exactly this reason).
- *DRY*: no redundancy introduced; the plan's Backlog item removes a second source of truth
  (`known_boundary_violations.md`'s stale file names) as a documented follow-up.
- *Hexagonal*: `core.config.bootstrap` is explicitly typed `archetype: adapter` (Resolved Decision
  #2) — the DB/IO-touching piece is now honestly an adapter, not disguised as pure-logic.
- *Separation of Concerns*: `core.config` changes for one reason (settings shape);
  `core.config.bootstrap` changes for a different one (cross-domain DB wiring) — previously one
  file conflated both.

**5.2b — Red/Blue Team Analysis**: see below (run via `specweaver-red-blue-review`).

**5.3 — Internal consistency**: Proposed Changes table above tags every file NEW/MODIFY/DELETE.
No DB migration is involved (this SF moves Python modules, not schema). The one new test
(`test_architecture.py` addition) is named consistently with what it verifies. No contradictions
found between the Research Notes, Resolved Decisions, and Proposed Changes sections.

**5.3a — Code detail limit**: The plan contains exactly one code block (the `db_bootstrap.py`
import excerpt in Research Notes) — a verbatim quote of *existing* code, not authored new code, so
it is a research finding, not a design overreach. No full function/class bodies are written for
the new `core.config.bootstrap` package; its contents are specified as "verbatim move, no logic
change" rather than re-authored, which needs no pseudocode at all.

---

# Red/Blue Team Review Report

## Summary
- **Target**: This implementation plan (TECH-001 SF-04)
- **Cycles**: 2
- **Findings**: 6 (1 CRITICAL, 3 MEDIUM, 2 LOW)
- **Critical/High fixes applied**: 1/1 CRITICAL, all MEDIUM/LOW also applied

## Corrections Made
- Added `specweaver.core.config.bootstrap` to the `depends_on` list of all 7 consumer tach
  boundaries (RED-1.1, CRITICAL — without this, `tach check` fails immediately post-move).
- Documented a third, previously-unnamed circular dependency (`core.config ⇄ workspace`,
  tach.toml:126) that this plan's fix also resolves as a side effect (RED-1.2).
- Added explicit `forbids: [specweaver/sandbox/*]` to the new `context.yaml` (RED-1.3).
- Spelled out the exact 6 function names for the `[[interfaces]] expose=[...]` allowlist, and
  corrected its framing from "required" to "recommended hardening" after verifying `core.config`
  itself has no such block today and `tach check` still passes (RED-1.4, refined by RED-2.1).
- Added an explicit note to preserve `db_bootstrap.py`'s side-effect-only
  `import specweaver.workspace.memory.store  # noqa: F401` during the move (RED-1.5).

## Accepted Risks
None. All findings were fixed, not accepted as residual risk.

## Cycle Log

### Cycle 1
- 🔴 RED-1.1 / 🔵 BLUE-1.1 — CRITICAL — 7 consumer tach boundaries never gain
  `core.config.bootstrap` in `depends_on`. VALID — FIX REQUIRED. Fixed.
- 🔴 RED-1.2 / 🔵 BLUE-1.2 — LOW (informational) — undiscovered third cycle
  (`core.config ⇄ workspace`), which this plan's fix happens to also resolve, undocumented.
  VALID — FIX REQUIRED. Documented in Research Notes and Proposed Changes.
- 🔴 RED-1.3 / 🔵 BLUE-1.3 — MEDIUM — new `context.yaml` omits explicit `forbids`. VALID — FIX
  REQUIRED. Fixed.
- 🔴 RED-1.4 / 🔵 BLUE-1.4 — MEDIUM — `expose=[...]` allowlist symbols not spelled out. VALID —
  FIX REQUIRED. Fixed (later refined in Cycle 2).
- 🔴 RED-1.5 / 🔵 BLUE-1.5 — LOW — side-effect-only import could be mistaken for dead code during
  the move. VALID — FIX REQUIRED. Fixed.

Cycle 1 totals: 1 CRITICAL, 0 HIGH, 2 MEDIUM, 2 LOW → CRITICAL ≥ 1 met → continue to Cycle 2.

### Cycle 2
- Re-verified Blue Team's Cycle 1 claim that `interfaces.cli` already depends on `core.config`
  (tach.toml:66) — confirmed correct, not just asserted.
- 🔴 RED-2.1 / 🔵 BLUE-2.1 — MEDIUM — Cycle 1's RED-1.4 fix conflated "required for `tach check`"
  with "recommended precision": empirically, `core.config` itself has no `[[interfaces]]
  expose=[...]` block today and `tach check` still passes clean, so the new allowlist for
  `core.config.bootstrap` is opt-in hardening, not a correctness requirement. VALID — FIX
  REQUIRED. Fixed — reworded in the Proposed Changes table to distinguish the one strictly-required
  tach.toml change (RED-1.1) from the recommended one (RED-1.4).
- Swept remaining focus areas with no new findings: DDD/Hexagonal/SoC/KISS/DRY/YAGNI (no change
  from Phase 5.2a's assessment), Security (N/A — no credentials or sensitive data touched),
  Input validation / Resource limits / Privilege escalation (N/A — no new external input surface),
  Error handling / Race conditions / Zombie processes (N/A — moves existing code unchanged),
  Platform differences (N/A — no new platform-specific code), Testability / Readability /
  Extension points (confirmed fine, matches existing precedent).

Cycle 2 totals: 0 CRITICAL, 0 HIGH, 1 MEDIUM, 0 LOW → all below continuation thresholds → **STOP**.

Review complete after 2 cycles.

## Backlog (deferred, not this SF)

- `docs/architecture/06_lessons_and_future/known_boundary_violations.md`'s "Inline Imports" and
  "Stability Direction Violation" rows name `core/config/database.py`/`settings.py`, which no
  longer contain the violation — needs a wording fix pointing at the current files, once this SF
  lands (so the update can also mark the row RESOLVED rather than DEFERRED). Not done here because
  it's a documentation-only follow-up, unrelated to shipping the actual fix.

---

## Resolved Decisions (Phase 4 — merged 2026-08-02)

User directed the agent to proceed using its own proposals for all 9 findings ("PLEASE GO ON"),
after independently verifying #7 and #8 rather than leaving them open. No proposal was overridden.

| # | Decision | Severity |
|---|----------|----------|
| 1 | Relocation strategy: **(A)** new `core.config.bootstrap` sub-boundary, mirroring `core.config.interfaces`. Rejected (B) (moves `get_db`/`load_settings` out of `core.config`'s declared public API entirely) and (C) (true per-call DI multiplies cross-domain-type knowledge across 8+ sites instead of concentrating it in one). | CRITICAL |
| 2 | `core.config.bootstrap`'s `context.yaml` archetype: **`adapter`** (matches sibling `core.config.interfaces`; honestly describes DB/IO-touching code, unlike `pure-logic`). | HIGH |
| 3 | No backward-compat shims at the old file paths — delete `db_bootstrap.py`/`settings_loader.py` from `core/config/` in the same commit that updates every caller. No consumer outside `src/`/`tests/` exists. | MEDIUM |
| 4 | Test file locations confirmed via `Glob`: only `tests/unit/core/config/test_settings_loader.py` exists (no dedicated `db_bootstrap` unit test) → moves to `tests/unit/core/config/bootstrap/`. | LOW |
| 5 | New `core.config` acyclicity regression test lands in **`tests/unit/test_architecture.py`** (already this repo's home for structural-invariant tests, per `TECH-016`'s precedent there). | MEDIUM |
| 6 | `tach.toml` boundary for `core.config.bootstrap`'s consumers: use the **`[[interfaces]] expose=[...]` allowlist pattern**, matching `core.config.interfaces` (tach.toml:177-178) rather than leaving it open-ended. | MEDIUM |
| 7 | **Verified during merge**: `grep -r "from specweaver.core.config import.*load_settings"` across `src/` returns zero matches — nothing imports `load_settings` from the top-level `specweaver.core.config` package, only from `specweaver.core.config.settings_loader` directly. `context.yaml`'s `exposes` list drops `load_settings` from `core.config` and gains it on the new `core.config.bootstrap`. | HIGH |
| 8 | **Verified during merge**: `migrate_legacy_config()` has zero callers anywhere in `src/` today (dedicated grep beyond the 8-site sweep). Moves with the rest of `settings_loader.py`; no separate fix needed. | LOW |
| 9 | Deferred to Backlog (above) — `known_boundary_violations.md`'s stale file references get fixed as a single follow-up edit once SF-04 lands and the row can be marked RESOLVED, not fixed twice. | LOW |

**Additional finding surfaced during merge** (not one of the original 9, found while verifying #7/#8):
the test-side blast radius is **62 files**, not the 8 production call sites originally scoped —
most patch `db_bootstrap`/`settings_loader` by hardcoded string path
(`monkeypatch.setattr("specweaver.core.config.db_bootstrap.get_db", ...)`). Folded into the Blast
Radius and Test Plan sections above rather than left as a silent gap. Still fully mechanical and
self-detecting (any miss is a loud `AttributeError` at test setup, not a silent regression).
