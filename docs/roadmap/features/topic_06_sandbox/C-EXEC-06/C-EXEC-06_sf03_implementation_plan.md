# C-EXEC-06 SF-03 — Composition-Root Policy + Allow-List Population + Verifiable Proof

**Status**: APPROVED — approved by Steve Bula on 2026-07-20. Audit Q1–Q6 resolved; Red/Blue NFR-2 fix
merged. Implemented 2026-07-20, committed `bd5cedd2` (2026-07-21). · **FRs owned**: FR-5 (populate),
FR-7 (policy/default-off), FR-8 · **Depends on**: SF-01, SF-02 (both committed) · Design:
[C-EXEC-06_design.md](C-EXEC-06_design.md) §Sub-features → SF-03

## Goal

The **producer** half of per-run isolation. SF-01/SF-02 built the consumer, but nothing sets
`session_isolation` or `allowed_paths` — both are always default. SF-03 makes the composition root set
them:

1. **FR-7 policy** — a default-off, opt-in `SandboxSettings` knob; when on, the composition root sets
   `context.session_isolation = True`. Per-step isolation (`enforce_isolation`) is unchanged.
2. **FR-5 populate** — `context.allowed_paths` from the generation targets (AD-2: `src/<stem>.py`,
   `tests/test_<stem>.py`), with a config override.
3. **FR-8 proof** — a multi-step, freshly-generated-file e2e (real git, real subprocess) + NFR-4
   adversarial reconcile-authorization tests.

## Where it plugs in

Line refs as of 2026-07-20 (see As built for where the code lives now).

| Fact | Where |
|---|---|
| The consumer is built. `RunContext` has `session_isolation: bool = False` and `allowed_paths: list[str] = Field(default_factory=list)`. `runner_utils.execute_run` guards on `getattr(context, "session_isolation", False)` (`:38`) and, on `RunStatus.COMPLETED`, runs `worktree_commit` → `strip_merge(branch, allowed_paths=original.allowed_paths)` (`:82-94`). A grep of `src/` shows both fields read, never assigned. | `handlers/base.py:58-59`; `runner_utils.py:30-99` |
| `SandboxSettings` has two fields: `execution_mode: Literal["host","container"]="host"` and `enforce_worktree_isolation: bool=False`, mounted at `SpecWeaverSettings.sandbox` (`:139`). Mirror its opt-in docstring (`:117-118`). | `core/config/settings.py:114-128` |
| TOML load does `SandboxSettings(**toml_data.get("sandbox", {}))` — a new `[sandbox]` key flows through, no loader change. Tests: `TestSandboxSettingsModel` ~`:37-58`, TOML ~`:116-146`. | `_load_toml_sandbox` (`settings_loader.py:73-91`); `tests/unit/core/config/test_settings_loader.py` |
| Two CLI composition sites, same shape. `sw run` → `_execute_run`: `RunContext(...)` at `:251-259` (`output_dir=project_path/"src"`), policy at `:269-272` in a best-effort `try/except`: `context.enforce_isolation = load_settings(db, project_path.name).sandbox.enforce_worktree_isolation`. `sw resume` → `resume`: `RunContext(...)` at `:452-460`, same resolution at `:470-473`. | `flow/interfaces/cli.py` |
| Generation paths come from the spec stem (`spec_path.stem.replace("_spec","")`): source `(context.output_dir or project_path/"src") / f"{stem}.py"`; tests `(context.output_dir or project_path/"tests") / f"test_{stem}.py"`. | `generation.py:111-112`, `generation.py:217-218` |
| **Inside a session `execute_run` sets `isolated.output_dir = None`**, so handlers fall back to `src/<stem>.py` and `tests/test_<stem>.py`. `allowed_paths` MUST derive from those defaults, NOT the composition-root `output_dir=src`. `strip_merge` matches repo-relative strings, so `allowed_paths = ["src/<stem>.py", "tests/test_<stem>.py"]`. | `runner_utils.py:66` |
| `execute_run` sets `isolated.enforce_isolation = False`, so no nested per-step worktree — with both knobs on, session wins (Q4). | `runner_utils.py:67` |
| The per-step INT-US-09 path `execute_in_sandbox` reads `getattr(context, "allowed_paths", [])` — today always `[]`. | `runner_utils.py:274` |
| API composition roots resolve no isolation policy: `start_pipeline_run`/`resume_run`/`submit_gate_decision` never set `enforce_isolation` either (pre-existing INT-US-09 gap). SF-03 does not widen it (Q1). | `interfaces/api/v1/pipelines.py:84-95` |
| E2E pattern (200 lines): `skipif` on `shutil.which("git")/("bash")`; a `_git(cwd,*args)` helper; commit a real repo (init, config user, add README + payload, commit); a real `PipelineDefinition` of `PipelineStep`s run via `asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())`; assert on `run_state.status`, `step_records` and the real repo. It sets `context.enforce_isolation = True`; SF-03 sets `context.session_isolation = True` + `context.allowed_paths = [...]`. Reuse its committed `.worktrees`-cwd **probe** and paired un-isolated **control**. | `tests/e2e/sandbox/test_step_worktree_isolation_e2e.py` |

External deps: git + bash (existing, e2e only). No new tool, no new dependency, no new module.

## Changes

1. **Settings knob** (FR-7) · `core/config/settings.py` — add to `SandboxSettings`, mirroring
   `enforce_worktree_isolation` (default-off, opt-in docstring):
   - `enforce_session_isolation: bool = False` — when True, the whole run executes in ONE worktree.
   - `session_allowed_paths: list[str] = Field(default_factory=list)` — AD-2 override; **empty ⇒
     derive**, **non-empty ⇒ verbatim**.
2. **Policy helper** (FR-5, FR-7) · `core/flow/engine/runner_utils.py` — pure, no I/O, beside the
   consumer it feeds (`interfaces → engine` is an existing edge):
   - `_derive_allowed_paths(spec_path)`: `stem = spec_path.stem.replace("_spec","")` →
     `return [f"src/{stem}.py", f"tests/test_{stem}.py"]`. **Must** use `.replace("_spec","")`, not
     `.removesuffix`, to byte-match `generation.py` (C1; `my_special_spec` → `myial`); a code comment
     cites `generation.py`. Forward slashes literally — `git diff --name-only` output is forward-slash
     on every platform; never `os.sep`.
   - `apply_session_policy(context, settings, logger)`: read `enforce_session_isolation` (defensive
     `getattr`) → `context.session_isolation = settings.sandbox.enforce_session_isolation`. **Only when
     True**, `context.allowed_paths = settings.sandbox.session_allowed_paths or _derive_allowed_paths(context.spec_path)` —
     computed into a local first, **then** both fields assigned (C2: a failure leaves the context fully
     default, never "session on, allow-list empty", which would drop all generated code). Off →
     `session_isolation = False`, `allowed_paths` stays `[]`. Best-effort; never raises.
3. **CLI wiring** (FR-5, FR-7) · `core/flow/interfaces/cli.py` — both sites (`_execute_run`, `resume`)
   resolve settings once and call `apply_session_policy` right after the `enforce_isolation` line
   (`cli.py:272`, `:473`), inside the existing best-effort `try`. A settings failure never crashes a
   run; policy falls back to off / `allowed_paths=[]`.
4. **Proof** (FR-8, NFR-4) · new `tests/e2e/sandbox/test_session_worktree_isolation_e2e.py` — real
   git + subprocess, no LLM. The "generator" is a **committed** bash script (the worktree checks out
   HEAD); the files it writes (`src/foo.py`, `secret.py`) are the uncommitted, freshly-generated payload.
   Who writes the file does not change the runner/GitAtom path under test.

| File | Change | FR |
|------|--------|----|
| `src/specweaver/core/config/settings.py` | `SandboxSettings.enforce_session_isolation` + `session_allowed_paths` | FR-7, FR-5 |
| `src/specweaver/core/flow/engine/runner_utils.py` | `apply_session_policy` + `_derive_allowed_paths` | FR-5, FR-7 |
| `src/specweaver/core/flow/interfaces/cli.py` | call `apply_session_policy` at both composition sites | FR-5, FR-7 |
| `tests/unit/core/config/test_settings_loader.py` | new-field model + TOML tests | FR-7 |
| `tests/unit/core/flow/engine/...` | direct `apply_session_policy` / `_derive_allowed_paths` tests | FR-5, FR-7 |
| `tests/e2e/sandbox/test_session_worktree_isolation_e2e.py` | multi-step proof + adversarial + control | FR-8, NFR-4 |

> [!CAUTION]
> **NFR-2 — do not populate `allowed_paths` when session isolation is off.** The per-step path reads
> it (`runner_utils.py:274`). Populating it unconditionally gives a per-step-isolated run
> (`enforce_worktree_isolation` on, session off) a non-empty allow-list and silently changes
> INT-US-09's `strip_merge`. Gate population on `context.session_isolation`.

> [!CAUTION]
> **Allow-list source of truth:** derive from the session-default layout (`src/<stem>.py`,
> `tests/test_<stem>.py`), because `execute_run` nulls `output_dir` inside the span. Deriving from the
> composition-root `output_dir=src` would mis-authorize the tests path and silently strip generated tests.

## Tests

DAL-C rigor. The e2e sets `session_isolation`/`allowed_paths` directly (FR-8 runtime behavior); the
settings → context wiring (FR-5/FR-7) is proven by the `apply_session_policy` unit tests. Two concerns,
two levels.

| Tier | Bucket | Case |
|---|---|---|
| Unit — `SandboxSettings` | Happy | `enforce_session_isolation=True` round-trips |
| | Boundary | default `False`, `session_allowed_paths=[]` |
| | Hostile | non-bool / non-list rejected by Pydantic |
| | Degradation | malformed `[sandbox]` TOML → defaults (existing `_load_toml_sandbox` `except`) |
| Unit — `_derive_allowed_paths` (direct) | Happy | `foo_spec.md` → `["src/foo.py","tests/test_foo.py"]` |
| | Boundary | stem without `_spec` (`foo.md` → `foo`); C1 `my_special_spec` → `myial`; forward slashes on all platforms |
| | Edge | dotted / degenerate stem |
| Unit — `apply_session_policy` (direct) | Happy | on + empty override → `session_isolation=True`, derived paths |
| | Happy | non-empty `session_allowed_paths` → used **verbatim**, derivation not called |
| | Boundary (NFR-2) | off → `session_isolation=False` AND `allowed_paths` stays `[]` |
| | Boundary | both knobs on → `session_isolation=True` |
| | Hostile (C3) | override `[""]` → verbatim, fail-closed (matches nothing) |
| | Degradation (C2) | derivation raises / `settings.sandbox` missing → context default (off, `[]`), no crash |
| Integration — CLI composition, real toml | Happy | `enforce_session_isolation=true` → `session_isolation is True` + `allowed_paths == ["src/test.py","tests/test_test.py"]` (spec `test_spec.md`); `resume` the same |
| | Boundary (NFR-2) | only `enforce_worktree_isolation=true` → `session_isolation False`, `allowed_paths == []` |
| | Boundary | both knobs true → `enforce_isolation` and `session_isolation` both True |
| | Degradation | malformed `[sandbox]` toml → both off, no crash |
| E2E — real git + bash | Happy | step 1 writes `src/foo.py` + `tests/test_foo.py` in the worktree; step 2 (`VALIDATE`/tests) runs pytest importing `foo` and asserting cwd is inside `.worktrees` — passes only if both steps share ONE worktree (guard `passed == 1`) |
| | Happy | `allowed_paths=["src/foo.py","tests/test_foo.py"]`; after COMPLETED the real repo **has** `src/foo.py` committed |
| | Hostile (NFR-4) | `secret.py` (not allowed) **absent** from the real repo; `docs/x.md` hard-blocked even if allow-listed |
| | Control | un-isolated run (`session_isolation=False`) → files at the real root, the probe FAILS (not a 0-collected false pass) |
| | Degradation | non-git `project_path` + session on → fails loud (FR-6); the wiring does not mask it |

## Decisions (audit)

Resolved by Steve Bula, 2026-07-20.

| # | Question | Chosen |
|---|----------|--------|
| Q1 | Session policy on the **API** composition root too, or CLI-only? | **CLI-only for v1.** The API gap (both `enforce_isolation` and the session policy) is **`TECH-013`** (minted 2026-07-20, roadmap STUB); `apply_session_policy` is written to be reused there verbatim |
| Q2 | Settings field name | **`enforce_session_isolation`** (mirrors `enforce_worktree_isolation`) |
| Q3 | Override shape | flat **`session_allowed_paths: list[str]`**, empty ⇒ derive, non-empty ⇒ verbatim |
| Q4 | Both isolation knobs on | **Session wins**, per-step suppressed inside the span (`runner_utils.py:67`). Documented; no error |
| Q5 | Pipelines generating beyond `src/<stem>.py`/`tests/test_<stem>.py` | **Accept for v1** — extras are stripped (safe); `session_allowed_paths` handles non-standard layouts |
| Q6 | Commit boundary | **Single CB-1** — settings + policy + population + unit/integration + e2e + docs |

Red/Blue (2 cycles, 2026-07-20) found the NFR-2 leak (populating `allowed_paths` when session is off);
fixed by gating, pinned by a direct unit test.

Architecture check: additive fields on an existing `core.config` model; pure helpers in
`core.flow.engine`; `cli.py` (`core.flow.interfaces`) already imports `load_settings` and mutates the
context there. No new cross-layer import, no new edge. ADR-002 respected — config resolved once at the
composition root and frozen onto the context, like `enforce_isolation`. `settings` is passed as `Any`, so no `core.flow.engine → core.config` edge. `strip_merge`/`execute_run`
reused verbatim. `tach`/`ruff`/`mypy --strict` must stay green. Verdict: no CRITICAL violation.

## As built (2026-07-20)

Delivered as planned, no deviations.

| Where | What |
|---|---|
| `core/config/settings.py` | `enforce_session_isolation: bool = False` + `session_allowed_paths: list[str]`, parsed by the existing `[sandbox]` TOML splat |
| `core/flow/engine/runner_utils.py` | `_derive_allowed_paths` + `apply_session_policy` (compute-then-assign C2; gated population NFR-2; never raises) |
| `core/flow/interfaces/cli.py` | `_execute_run` and `resume` resolve settings once and call `apply_session_policy` beside the `enforce_isolation` line |

- `Path(".md").stem == ".md"` (pathlib: no suffix on a leading-dot name), so a dotfile spec derives
  `src/.md.py` — safe, matches nothing real.
- Since moved: `c3f36d54` retired `runner_utils` — `execute_run` now lives in
  `core/flow/engine/session.py`, `apply_session_policy`/`_derive_allowed_paths` in
  `core/flow/engine/isolation.py`; the e2e tests are under `tests/e2e/capabilities/sandbox/`.

Proof and test counts: [walkthrough](C-EXEC-06_sf03_walkthrough.md).

Deferred:
- **`TECH-013`** — API composition roots (`start_pipeline_run`/`resume_run`/`submit_gate_decision`) set
  neither `enforce_isolation` nor the session policy. See
  `docs/roadmap/features/topic_07_technical_debt/TECH-013/TECH-013_design.md`.
- **Shared generation-target derivation** — one function used by both `generation.py` and the
  allow-list. Larger, low-urgency.

Next: `INT-US-09-SF05` → `INT-US-03 SF-03` → US-3 closes.
