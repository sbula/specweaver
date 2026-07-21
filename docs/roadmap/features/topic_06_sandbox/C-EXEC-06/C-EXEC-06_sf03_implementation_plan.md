# Implementation Plan: Per-Run (Session) Worktree Isolation — SF-03: Composition-Root Policy + Allow-List Population + Verifiable Proof

- **Feature ID**: C-EXEC-06
- **Sub-Feature**: SF-03 — Composition-Root Policy + Allow-List Population + Verifiable Proof
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_sf03_implementation_plan.md
- **Status**: APPROVED — approved by Steve Bula on 2026-07-20. Audit Q1–Q6 resolved; Red/Blue NFR-2 fix merged.

## Scope (from the Design Document)
The **producer / composition-root** half of per-run isolation. SF-01 + SF-02 already deliver the *consumer*:
`RunContext.session_isolation` + `allowed_paths` fields exist, and `runner_utils.execute_run` dispatches on
`session_isolation` to run the whole span in one worktree and reconcile via an authorized `strip_merge` keyed
on `allowed_paths`. **Nothing populates either field yet** (both are always default). SF-03 closes that:
1. **FR-7 policy** — a new **default-off, opt-in** `SandboxSettings` knob; when on, the composition root sets
   `context.session_isolation = True`. Per-step single-step isolation (`enforce_isolation`) is left unchanged.
2. **FR-5 populate** — at the composition root, populate `context.allowed_paths` from the pipeline's generation
   targets (AD-2: `src/<stem>.py`, `tests/test_<stem>.py`), with a config override.
3. **FR-8 verifiable proof** — a multi-step, freshly-generated-file e2e (real git, real subprocess) + NFR-4
   adversarial reconcile-authorization tests.
**FRs owned: FR-5, FR-7, FR-8.** Depends on SF-01 + SF-02 (both committed to `main`).
**Commit boundary:** single **CB-1** (settings + policy + population + unit/integration + e2e proof + docs).

## Research Notes (Phase 0)

1. **The consumer is fully built (SF-01/SF-02).** `RunContext` already carries `session_isolation: bool = False`
   and `allowed_paths: list[str] = Field(default_factory=list)` (`handlers/base.py:58-59`).
   `runner_utils.execute_run` (`:30-99`) guards on `getattr(context, "session_isolation", False)` (`:38`) and,
   on `RunStatus.COMPLETED`, runs `worktree_commit` → `strip_merge(branch, allowed_paths=original.allowed_paths)`
   (`:82-94`). **SF-03 only needs to make the composition root set these two fields.** A grep of `src/` confirms
   both fields are read but never assigned anywhere — the producer side is the entire remaining gap.

2. **`SandboxSettings` has exactly two fields today** (`core/config/settings.py:114-128`):
   `execution_mode: Literal["host","container"]="host"` and `enforce_worktree_isolation: bool=False`. Mounted
   at `SpecWeaverSettings.sandbox` (`:139`). The opt-in-only docstring convention (`:117-118`) is the pattern to
   mirror for the new knob. TOML load: `_load_toml_sandbox` (`settings_loader.py:73-91`) does
   `SandboxSettings(**toml_data.get("sandbox", {}))`, so **any new field is parsed automatically** — no loader
   change needed (a new `[sandbox]` key just flows through). Model + TOML tests:
   `tests/unit/core/config/test_settings_loader.py` (`TestSandboxSettingsModel` ~`:37-58`, TOML ~`:116-146`).

3. **The composition root already resolves the per-step policy in the exact place SF-03 extends** — two CLI
   sites, identical shape:
   - `sw run` → `_execute_run` (`flow/interfaces/cli.py`): `RunContext(...)` built `:251-259`
     (`output_dir=project_path/"src"`); policy resolved `:269-272` inside a best-effort `try/except` —
     `context.enforce_isolation = load_settings(db, project_path.name).sandbox.enforce_worktree_isolation`.
   - `sw resume` → `resume` (`cli.py`): `RunContext(...)` built `:452-460`; identical resolution `:470-473`.
   SF-03 adds two more assignments inside that same `try` block at both sites (via one shared helper).

4. **AD-2 generation targets — the derivation and a critical session subtlety.** Generation handlers derive
   paths from the spec stem (`spec_path.stem.replace("_spec","")`):
   - source: `generation.py:111-112` → `(context.output_dir or project_path/"src") / f"{stem}.py"`.
   - tests: `generation.py:217-218` → `(context.output_dir or project_path/"tests") / f"test_{stem}.py"`.
   **Inside a session, `execute_run` sets `isolated.output_dir = None` (`runner_utils.py:66`)**, so the handlers
   fall back to their *defaults*: `src/<stem>.py` and `tests/test_<stem>.py`. Therefore `allowed_paths` MUST be
   derived from those defaults (`src/`, `tests/`), NOT from the composition-root `output_dir=src`. `strip_merge`
   matches **repo-relative** path strings, so `allowed_paths = ["src/<stem>.py", "tests/test_<stem>.py"]`.

5. **API composition roots do NOT resolve isolation policy at all** (`interfaces/api/v1/pipelines.py:84-95`) —
   a documented pre-existing INT-US-09 backlog gap: `start_pipeline_run`/`resume_run`/`submit_gate_decision`
   never set `enforce_isolation` either. SF-03 stays consistent with that boundary (see Q1) and does not widen it.

6. **The e2e pattern to mirror** — `tests/e2e/sandbox/test_int_us_09_isolation_e2e.py` (200 lines): `skipif`
   on `shutil.which("git")/("bash")`; a `_git(cwd,*args)` subprocess helper; commit a real repo (init, config
   user, add README + payload, commit) so the worktree checkout carries the payload; build a real
   `PipelineDefinition` of `PipelineStep`s; run via `asyncio.run(PipelineRunner(pipeline, context,
   registry=StepHandlerRegistry()).run())`; assert on `run_state.status`, `step_records`, and the **real** repo.
   It sets the per-step policy with `context.enforce_isolation = True`; the SF-03 e2e sets
   `context.session_isolation = True` + `context.allowed_paths = [...]` instead. It uses a committed
   `.worktrees`-cwd **probe** test and a paired un-isolated **control** (proves the probe genuinely runs and is
   not a 0-collected false pass) — SF-03 reuses both devices.

7. **`session_isolation` neutralizes per-step isolation inside the span**: `execute_run` sets
   `isolated.enforce_isolation = False` (`:67`) so no nested per-step worktree is created inside the session.
   The two knobs therefore compose safely — session takes precedence; no error needed if both are on (see Q4).

### External deps: git + bash (existing, e2e only). No new tool, no new dependency.

## Implementation Approach
> Pseudocode / ordered steps only.

### Change 1 — new opt-in settings knob (FR-7) · `core/config/settings.py`
Add to `SandboxSettings` (mirroring `enforce_worktree_isolation`, default-off, opt-in docstring):
- `enforce_session_isolation: bool = False` — when True, the whole run executes in ONE worktree (per-run mode).
- `session_allowed_paths: list[str] = Field(default_factory=list)` — AD-2 config override; **empty ⇒ derive**
  from generation targets, **non-empty ⇒ use verbatim**.
No `settings_loader.py` change (the `[sandbox]` TOML section already splats into `SandboxSettings(**...)`).

### Change 2 — composition-root policy + allow-list population (FR-5, FR-7) · shared helper + `cli.py`
Add one testable helper — proposed `apply_session_policy(context, settings, logger)` in
`core/flow/engine/runner_utils.py` (co-located with the session consumer; `interfaces → engine` is an existing
edge). Steps (pure, no I/O):
1. `context.session_isolation = settings.sandbox.enforce_session_isolation`.
2. **Only when `context.session_isolation` is True**, populate the allow-list:
   `context.allowed_paths = settings.sandbox.session_allowed_paths or _derive_allowed_paths(context.spec_path)`.
   When session isolation is **off**, leave `allowed_paths` at its default `[]` — do NOT populate it (see the
   CAUTION below: the per-step INT-US-09 path also reads `allowed_paths`, so populating it when session is off
   would silently change per-step `strip_merge` behavior — an NFR-2 violation).
3. `_derive_allowed_paths(spec_path)`: `stem = spec_path.stem.replace("_spec","")` →
   `return [f"src/{stem}.py", f"tests/test_{stem}.py"]` (the session-default layout, Research Note 4).
   Use **forward slashes** literally — `strip_merge` compares against `git diff --name-only` output, which is
   forward-slash on every platform including Windows; never `os.sep`.
Call it at BOTH CLI sites, inside the existing best-effort `try` block, right after the `enforce_isolation`
line (`cli.py:272` and `:473`). Keep it best-effort: a settings-resolution failure must never crash a run
(policy falls back to off / `allowed_paths=[]`).

> [!CAUTION]
> **NFR-2 — do not populate `allowed_paths` when session isolation is off.** `execute_in_sandbox` (the
> **per-step** INT-US-09 path) reads `getattr(context, "allowed_paths", [])` (`runner_utils.py:274`); today it
> is always `[]`. Populating it unconditionally would give a per-step-isolated run (`enforce_worktree_isolation`
> on, session off) a non-empty allow-list and silently alter INT-US-09's `strip_merge` — a backward-compat
> regression. Gate the population on `context.session_isolation` being True.

### Change 3 — verifiable proof (FR-8) + adversarial authorization (NFR-4) · new e2e
New `tests/e2e/sandbox/test_c_exec_06_session_isolation_e2e.py`, mirroring the INT-US-09 e2e devices. See Test
Plan. Real git + real subprocess, no LLM (the "generation" is a committed/bash-written file, as the INT-US-09
e2e does — the runner/GitAtom path under test is unchanged by whether a human or an LLM wrote the file).

### Files to modify
| File | Change | FR |
|------|--------|----|
| `src/specweaver/core/config/settings.py` | `SandboxSettings.enforce_session_isolation` + `session_allowed_paths` | FR-7, FR-5 |
| `src/specweaver/core/flow/engine/runner_utils.py` | `apply_session_policy` + `_derive_allowed_paths` helpers | FR-5, FR-7 |
| `src/specweaver/core/flow/interfaces/cli.py` | call `apply_session_policy` at both composition sites | FR-5, FR-7 |
| `tests/unit/core/config/test_settings_loader.py` | new-field model + TOML tests | FR-7 |
| `tests/unit/core/flow/engine/...` | `apply_session_policy` / `_derive_allowed_paths` direct unit tests | FR-5, FR-7 |
| `tests/e2e/sandbox/test_c_exec_06_session_isolation_e2e.py` | multi-step proof + adversarial + control | FR-8, NFR-4 |
No new module.

## Test Plan (4 Adversarial Buckets — DAL-C rigor)

**Unit — settings knob (`SandboxSettings`):** [Happy] `enforce_session_isolation=True` round-trips;
[Boundary] default is `False` and `session_allowed_paths=[]`; [Hostile] a non-bool / non-list is rejected by
Pydantic; [Degradation] a malformed `[sandbox]` TOML falls back to defaults (existing `_load_toml_sandbox`
`except`).

**Unit — `_derive_allowed_paths` (direct, per memory: test the branch directly):** [Happy] `foo_spec.md` →
`["src/foo.py","tests/test_foo.py"]`; [Boundary] a stem without `_spec` (`foo.md` → `foo`); [Edge] a dotted /
unusual stem; the derivation matches `generation.py`'s session-default layout (Research Note 4).

**Unit — `apply_session_policy` (direct):** [Happy] setting on + empty override → `session_isolation=True` and
derived `allowed_paths`; [Happy-override] non-empty `session_allowed_paths` → used **verbatim** (derivation not
called); **[Boundary — NFR-2 guard] setting off → `session_isolation=False` AND `allowed_paths` stays `[]`
(NOT populated)** — the regression guard for the per-step INT-US-09 path (see the Change-2 CAUTION); [Boundary]
both knobs on → `session_isolation=True` (the outer `enforce_isolation` line is independent; `execute_run`
suppresses per-step nesting); [Degradation] `load_settings`/derivation raises → best-effort catch leaves
defaults (off, `[]`), run not crashed.

**E2E — verifiable proof (FR-8, real git + subprocess, no LLM):**
- **[Happy / multi-step persistence]** session on; step 1 (bash) writes `src/foo.py` **and** `tests/test_foo.py`
  into the worktree cwd; step 2 (`VALIDATE`/tests) runs pytest which imports `foo` and asserts its cwd is inside
  `.worktrees` — PASSES only if both steps shared ONE worktree and ran bounded there (guard `passed == 1`).
- **[Happy / authorized reconcile]** `allowed_paths=["src/foo.py","tests/test_foo.py"]`; after a COMPLETED run
  the real repo **has** `src/foo.py` committed (landed via the authorized strip-merge).
- **[Hostile / NFR-4]** the same step-1 also writes `secret.py` (NOT in `allowed_paths`) → **absent** from the
  real repo after the run (stripped); and a `docs/x.md` write is hard-blocked even if it were allow-listed.
- **[Control]** the paired **un-isolated** run (`session_isolation=False`) → files land at the real root
  directly and the worktree-cwd probe FAILS (the discriminator proving the isolated pass isn't a 0-collected
  false pass and that isolation is what moved cwd + gated the write-back).
- **[Degradation]** a non-git `project_path` with session on → the run fails loud (FR-6, already in
  `execute_run`) — a light e2e assertion that the composition wiring doesn't mask it.

## Audit (Phase 2) — resolved at Phase 4 HITL (Steve Bula, 2026-07-20)
| # | Question | Resolution |
|---|----------|-----------|
| Q1 | Wire session policy on the **API** composition root too, or CLI-only? | **CLI-only for v1.** The API gap (both `enforce_isolation` and the new session policy) is documented + planned as **`TECH-013`** (minted 2026-07-20; STUB in the roadmap). SF-03's `apply_session_policy` helper is written to be reused verbatim there. |
| Q2 | New settings field name. | **`enforce_session_isolation`** (mirrors `enforce_worktree_isolation`). |
| Q3 | `allowed_paths` override shape. | Flat **`session_allowed_paths: list[str]`**, empty ⇒ derive, non-empty ⇒ verbatim. |
| Q4 | Precedence when BOTH isolation knobs are on. | **Session wins**, per-step suppressed inside the span (already `enforce_isolation=False` at `runner_utils.py:67`). Document the precedence; no error. |
| Q5 | Pipelines that generate files **beyond** `src/<stem>.py`/`tests/test_<stem>.py`. | **Accept for v1** — AD-2 tight default; the extras are stripped (safe); the `session_allowed_paths` override handles non-standard layouts. |
| Q6 | Commit-boundary shape for SF-03. | **Single CB-1** — settings + policy + population + unit/integration + e2e proof + docs, all in one commit. |

## Architecture Verification (Phase 3)
- **Mechanism × constraint:** `settings.py` — additive fields on an existing model in `core.config` (correct
  layer; no new import). `runner_utils.py` — pure helpers in `core.flow.engine` beside the session consumer
  they feed. `cli.py` (`core.flow.interfaces`) already imports `load_settings` and mutates the context here;
  the new calls add no edge. **No new cross-layer import; no boundary violation.** ADR-002 respected — config
  is resolved once at the composition root and frozen onto the context (same pattern as `enforce_isolation`).
- **Zoom-out / duplication:** `apply_session_policy` centralizes the two-line wiring so the `run` and `resume`
  sites don't drift (they already duplicate the `enforce_isolation` line — the helper could later absorb that
  too, out of scope). `_derive_allowed_paths` mirrors `generation.py`'s stem convention; a full shared
  target-derivation refactor of `generation.py` is a larger change deferred (noted as a follow-up). Reuses
  `strip_merge`/`execute_run` verbatim — no parallel policy logic.
- **Acyclic imports / stability:** no new edge; all additive. `tach`/`ruff`/`mypy --strict` must stay green.
  **Verdict:** no CRITICAL violation.

## Consistency + Red/Blue (Phase 5)
- **FR/NFR coverage:** FR-5 (populate at composition root, AD-2 + override), FR-7 (opt-in/default-off, per-step
  unchanged, park-guard already in SF-01), FR-8 (multi-step generated-file e2e); NFR-2 (byte-identical when
  off — the helper is a no-op that leaves `session_isolation=False`), NFR-4 (adversarial reconcile
  authorization), NFR-7 (architecture/tach/mypy).
- **Red/Blue notes to carry (2 cycles run, 2026-07-20):**
  1. **[NFR-2 regression — corrected]** populating `allowed_paths` when session isolation is off would leak a
     non-empty allow-list into the per-step INT-US-09 `strip_merge` (`runner_utils.py:274`). Fixed: gate the
     population on `session_isolation` (Change 2 + CAUTION); pinned by a direct `apply_session_policy`
     [Boundary] unit test.
  2. **[Research Note 4 trap]** the `output_dir=None`-inside-session subtlety — the allow-list must match
     `src/`+`tests/` defaults, not the composition `output_dir=src`; the direct `_derive_allowed_paths` unit
     test pins this.
  3. **[Windows path form]** `_derive_allowed_paths` must emit forward slashes (git `--name-only` form), never
     `os.sep` — else the allow-list never matches on Windows and every file is stripped.
  4. **[e2e authoring]** the step-1 "generator" is a **committed** bash script (the worktree checks out HEAD);
     the files it writes (`src/foo.py`, `secret.py`) are the *uncommitted, freshly-generated* payload under
     test. Mirror the INT-US-09 e2e's commit-the-script / assert-on-the-generated-file split.
  5. **[FR split]** the e2e sets `session_isolation`/`allowed_paths` directly (proves FR-8 runtime behavior);
     the settings→context wiring (FR-5/FR-7) is proven by the `apply_session_policy` unit tests. Two concerns,
     two test levels — intentional, not a coverage gap.
  6. Keep the wiring inside the existing best-effort `try` so a settings failure can never crash a run (NFR-2);
     the e2e includes the un-isolated control so an isolated "pass" can't be a 0-collected false pass.

> [!CAUTION]
> **Allow-list source of truth (Research Note 4):** derive `allowed_paths` from the session-default layout
> (`src/<stem>.py`, `tests/test_<stem>.py`), because `execute_run` nulls `output_dir` inside the span. Deriving
> from the composition-root `output_dir=src` would mis-authorize the tests path and silently strip generated
> tests.

## Implementation Notes (as-built, 2026-07-20)

Delivered exactly as planned; no deviations. Source:
- `core/config/settings.py` — `SandboxSettings.enforce_session_isolation: bool = False` +
  `session_allowed_paths: list[str]` (opt-in docstring; parsed by the existing `[sandbox]` TOML splat, no
  loader change).
- `core/flow/engine/runner_utils.py` — `_derive_allowed_paths` (byte-matches `generation.py`'s
  `.replace("_spec","")`, forward slashes) + `apply_session_policy` (compute-then-assign C2 hardening; gated
  population NFR-2; best-effort, never raises).
- `core/flow/interfaces/cli.py` — both composition sites (`_execute_run`, `resume`) now resolve settings once
  and call `apply_session_policy` alongside the existing `enforce_isolation` line.

Tests: `test_settings_loader.py` (+11), `test_session_policy.py` (13 unit, direct), `test_cli_config_integration.py`
(+7 integration), `test_session_policy_fullchain.py` (2 integration, real git — G2), and the FR-8 e2e
`tests/e2e/sandbox/test_c_exec_06_session_isolation_e2e.py` (4 e2e incl. G1 docs hard-block). Full suite green:
unit 4727 · integration 481 · e2e 148 (5356 passed, 0 failures). ruff/mypy(303)/C901/tach/file-size clean.

One test-expectation correction during dev: `Path(".md").stem == ".md"` (pathlib treats a leading-dot name as
having no suffix), so a degenerate dotfile spec derives `src/.md.py` — safe (matches nothing real); the test
now asserts the true value.

**Verifiable Proof (FR-8):** `tests/e2e/sandbox/test_c_exec_06_session_isolation_e2e.py` +
`tests/integration/core/flow/engine/test_session_policy_fullchain.py`.

## Backlog (deferred — not SF-03 scope)
- **`TECH-013` — API composition roots don't resolve isolation policy.** The API run sites
  (`start_pipeline_run`/`resume_run`/`submit_gate_decision`) set neither `enforce_isolation` nor the new
  session policy (a pre-existing INT-US-09 gap). Minted as a roadmap STUB on 2026-07-20; SF-03's
  `apply_session_policy` helper is designed to be reused there. See
  `docs/roadmap/features/topic_07_technical_debt/TECH-013/TECH-013_design.md`.
- **Shared generation-target derivation.** `_derive_allowed_paths` mirrors `generation.py`'s stem convention;
  a full refactor extracting one shared target-derivation function used by both the handlers and the allow-list
  is deferred (larger, low-urgency).

## Session Handoff
**Current status**: APPROVED (2026-07-20). Ready for `/specweaver-dev` — single commit boundary CB-1.
**Next step**: On approval → `/specweaver-dev` for SF-03 (CB-1 then CB-2). SF-03 completes C-EXEC-06; then
`INT-US-09-SF05` → `INT-US-03 SF-03` → US-3 closes.
