# Task List — C-EXEC-06 SF-03: Composition-Root Policy + Allow-List Population + Verifiable Proof

- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_sf03_implementation_plan.md
- **FRs**: FR-5 (populate allowed_paths at composition root), FR-7 (opt-in/default-off policy), FR-8 (e2e proof)
- **Commit boundary**: single **CB-1**. Foundation-first (settings → helpers → wiring → e2e proof).
- **(SF-01/SF-02 task records preserved in git history + walkthroughs.)**

## Tasks

- [x] **T1 — Settings knob** (FR-7, FR-5 override)
  - src: `core/config/settings.py` — add to `SandboxSettings`: `enforce_session_isolation: bool = False`,
    `session_allowed_paths: list[str] = Field(default_factory=list)`. Update the opt-in docstring.
  - test: `tests/unit/core/config/test_settings_loader.py` — defaults off/empty; round-trip; TOML load of the
    new keys; wrong-type rejection; malformed TOML falls back to defaults.

- [x] **T2 — `_derive_allowed_paths` helper** (FR-5, AD-2)
  - src: `core/flow/engine/runner_utils.py` — `_derive_allowed_paths(spec_path) -> list[str]`:
    `stem = spec_path.stem.replace("_spec","")` → `["src/<stem>.py", "tests/test_<stem>.py"]`, forward slashes.
    **C1: MUST use `.replace("_spec","")` to byte-match `generation.py:111-112,217-218` — NOT `.removesuffix`**;
    code comment must cite generation.py so it never drifts.
  - test: `tests/unit/core/flow/engine/test_session_policy.py` — [Happy] `foo_spec`→`src/foo.py`+`tests/test_foo.py`;
    [Boundary/C1] `my_special_spec`→`myial` (matches generation.py's `.replace` quirk, NOT `my_special`);
    [Boundary] stem without `_spec`; [Hostile] empty/degenerate stem (`.md`→`src/.py`, safe); [Boundary]
    forward-slash form on all platforms (assert `"/" in`, `os.sep` never used).

- [x] **T3 — `apply_session_policy` helper** (FR-5, FR-7, NFR-2 gating)
  - src: `core/flow/engine/runner_utils.py` — `apply_session_policy(context, settings, logger)`:
    read `enforce_session_isolation` (defensive `getattr`); **when True, compute the allow-list into a LOCAL
    first** (`session_allowed_paths or _derive_allowed_paths(spec_path)`), **then assign both `session_isolation`
    and `allowed_paths`** — C2: never leave a half-applied "session on, allow-list empty" state; a failure
    leaves the context fully default. Best-effort (never raise; the composition `try` is the outer net).
  - test: `test_session_policy.py` — [Happy] on+empty→`session True`+derived; [Happy] override→verbatim
    (derivation not called); **[Boundary/NFR-2] off→`session False` AND `allowed_paths == []`**; [Boundary]
    both-knobs-on→`session True`; [Hostile/C3] override `[""]`→used verbatim, fail-closed (matches nothing);
    [Degradation/C2] derivation raises (patched)→context unchanged (session off, `[]`), no crash; [Degradation]
    `settings.sandbox` missing/None→default off.

- [x] **T4 — Wire at CLI composition roots** (FR-5, FR-7)
  - src: `core/flow/interfaces/cli.py` — call `apply_session_policy(context, settings, logger)` at
    `_execute_run` (after the `enforce_isolation` line ~:272) and `resume` (~:473), inside the best-effort try.
  - test: `tests/integration/core/flow/test_cli_config_integration.py` (real toml → real composition, only
    `PipelineRunner` mocked): [Happy] `enforce_session_isolation=true` → `context.session_isolation is True` +
    `allowed_paths == ["src/test.py","tests/test_test.py"]` (spec `test_spec.md`); [Happy] resume path same;
    **[NFR-2/Boundary] only `enforce_worktree_isolation=true` (session off) → `session_isolation False` AND
    `allowed_paths == []`**; [Boundary] both knobs true → both `enforce_isolation` and `session_isolation` True;
    [Degradation] malformed `[sandbox]` toml → both off (composition never crashes).

- [x] **T5 — Verifiable proof e2e** (FR-8, NFR-4)
  - test: new `tests/e2e/sandbox/test_c_exec_06_session_isolation_e2e.py` (real git+bash, skipif guard).
    [Happy/persistence] multi-step: committed generator script writes `src/foo.py`+`secret.py` into the worktree
    cwd, a later `VALIDATE`/tests step runs a committed pytest probe bounded there that asserts `".worktrees" in
    cwd` AND `src/foo.py` exists in-tree (proves ONE shared worktree across steps; guard `passed==1`);
    [Happy/reconcile] after COMPLETED, real repo HAS `src/foo.py` (landed via authorized strip-merge);
    [Hostile/NFR-4] `secret.py` (not in allowed_paths) is ABSENT from the real repo; [Control] un-isolated run
    → files at the real root + the probe FAILS (discriminator: not a 0-collected false pass); [Degradation]
    non-git `project_path` + session on → run fails loud (FR-6), composition doesn't mask it.

- [x] **T6 — Full suite + pre-commit gate (CB-1)**
  - Full unit/integration/e2e; fix any regression project-wide. Run pre-commit skill. Update
    `pipeline_engine_guide.md §7` (per-run model + allowed_paths). HITL commit stop (direct to master).

## Adversarial Test Matrix (per task — 4 buckets)
| Task | Happy | Boundary/Edge | Graceful Degradation | Hostile/Wrong Input |
|------|-------|---------------|----------------------|---------------------|
| T1 | knob true round-trips | default off/empty | malformed TOML → defaults | non-bool/non-list rejected |
| T2 | `foo_spec`→`src/foo.py`+tests | **C1** `my_special_spec`→`myial` (generation.py parity); stem w/o `_spec`; fwd-slash | degenerate `.md`→`src/.py` (safe) | odd/dotted stem; `os.sep` never used |
| T3 | on→derived allow-list | both-knobs-on→session True | **C2** derivation raises→context default (no half-apply); settings.sandbox None→off | **off→allowed_paths stays `[]` (NFR-2)**; **C3** `[""]` override→fail-closed |
| T4 | toml on→context session+paths | both knobs on→both set | malformed toml→both off, no crash | session off but per-step on→paths still `[]` (NFR-2) |
| T5 | multi-step generated file runs bounded + persists | reconcile lands only allowed | non-git + session on → fails loud (FR-6) | `secret.py` stripped; control probe FAILS at root |

## Progress
- Phase 2 (task breakdown): task list approved (corner/degradation/e2e/integration coverage expanded per HITL).
- T1–T5 complete (TDD red→green→refactor). ruff + mypy + tach clean on all changed source.
- Full suite (Step A): unit 4727 · integration 479 · e2e 147 (5353 passed, 0 failures). No regressions.
- Pre-commit gate (Step B): _running_.
  - Phase 1 (architecture): [x] ✅ no violations (tach clean; no new cross-layer edge — settings passed as `Any`).
  - Phase 2 (test gap): [x] combined analysis; user approved G1 + G2.
  - Phase 3 (implement tests): [x] G1 (docs hard-block e2e) + G2 (full-chain integration, 2 tests). ruff clean.
  - Phase 4 (full suite): [x] unit 4727 · integration 481 · e2e 148 (5356 passed, 0 failures).
  - Phase 5 (code quality): [x] ruff, mypy (303), C901, file-size (0 err), tach — all clean.
  - Phase 6 (docs): [x] pipeline_engine_guide §7 (per-run model), impl-plan as-built, design tracker Dev ✅.
  - Phase 7 (walkthrough): [x] C-EXEC-06_sf03_walkthrough.md.
  - Phase 7.5 (Red/Blue on code): [x] no critical findings (traversal-safe, NFR-2 preserved, C2/C3 fail-closed).
  - Phase 8 (commit boundary): ✅ committed `bd5cedd2` (direct to master, 2026-07-21). Post-commit: C-EXEC-06 → ✅ in capability_matrix + master_story_roadmap (Verifiable Proof recorded); design tracker Pre-Commit ✅ + Committed ✅.

## SF-03 COMPLETE — C-EXEC-06 capability fully delivered (SF-01/02/03 all committed).
