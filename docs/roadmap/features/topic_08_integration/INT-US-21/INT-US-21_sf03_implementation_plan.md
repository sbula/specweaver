# INT-US-21 SF-03 — CLI Journey, Verifiable Proof & Registry Closure

**Status**: APPROVED (user, 2026-07-26). COMPLETE — committed 2026-07-28 (`8fff2470`, `d0c020f4`,
`ccdda8f8`, `39aa3860`, CB-5). · **FRs owned**: FR-8 (CLI journey), FR-10 (verifiable proof) +
Guides 1–2 + registry closure · **Depends on**: SF-01 COMPLETE (`f1de38f1`, `c4c1a109`, `6811a943`,
`5ebcc414`), SF-02 COMPLETE (`4a42b87a`, `ce00be20`, `5aa20ffa`) · Design:
[INT-US-21_design.md](INT-US-21_design.md) §Sub-features → SF-03

## Goal

Prove the full journey on the real CLI, bring the guides current, close the US-21 epic.

## Where it plugs in

Verified against `main` on 2026-07-26, after SF-02. R-3 and R-4 are **measured, not read** — both
would have produced a vacuous e2e if assumed.

### R-1 — `_resolve_spec_path` already accepts an explicit path

`core/flow/interfaces/cli.py`, in order:

1. `if Path(spec_or_module).exists(): return it` ← an explicit path works already
2. `if pipeline_name == "new_feature": return project/specs/<name>_spec.md`
3. try `project/<arg>`; else return the literal path

`sw run feature_decomposition specs/onboarding_feature_spec.md` resolves; only the bare-name form
(`sw run feature_decomposition onboarding`) does not. FR-8 is a small addition to branch 2; the e2e
is not blocked on it.

### R-2 — Import the suffix constant, never re-hardcode it

`FEATURE_SPEC_SUFFIX = "_feature_spec.md"` at `handlers/draft.py:24`, used at `:246`, `:331`,
`:333`. `DraftFeatureHandler` **errors loudly** when `spec_path` does not match it; a second literal
in `cli.py` would drift and trip that guard on every drafting run.

### R-3 — A realistic feature spec passes the battery with warnings (measured)

SF-01 found "a fixture that could not pass its own battery"; if this fixture cannot clear
`validation_spec_feature`, the journey dies at step 2. Probed with `execute_validation_pipeline`:

| | |
|---|---|
| battery | `validation_spec_feature` — 11 rules (default minus `s04_dependency_dir`) |
| result | **8 pass, 3 warn, 0 fail** |
| warnings | S09 (no structured error section), S11 (1 terminology issue), S07 (no Scenarios section → testability 9/12) |

`validation.py:97-98`: `failed = [r for r in results if r.status == RuleStatus.FAIL]; all_passed =
len(failed) == 0`. **Warnings do not fail the step** — the fixture needs zero FAILs, not 11/11 clean. Do **not**
chase the warnings (a Scenarios section for S07 would make the fixture unrepresentative).

### R-4 — PARKED and COMPLETED both exit 0 (measured)

`cli.py:404-418`: COMPLETED → `0`, FAILED → `1`, **PARKED → `0`** (*"Not an error, just parked"*) —
the defect behind INT-US-02's vacuous E6/E7. **Every assertion reads the persisted run status from
the store**; exit code only *in addition*.

### R-5 — Two resume surfaces; the park message advertises one

`sw run --resume <run_id>` (option, `cli.py:188-190`) and a separate `resume` command
(`cli.py:422`). `display.py:234` prints `Resume with: sw run --resume <run_id>`. FR-8 says
"`sw resume`" (Q1).

### R-6 — The INT-US-24 harness is the pattern

`tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py`: module-level
`runner = CliRunner()`, `pytestmark = pytest.mark.e2e`, real `specweaver.interfaces.cli.main.app`,
scripted LLM responses, per-scenario fixtures. Its docstring lists E1–E8 with what each proves —
imitate it.

### R-7 — Host posture: `session_isolation` must be OFF

NFR-8. `C-EXEC-06` v1 **raises** on any park inside a session worktree (its AD-4); this journey
parks twice (Q3).

### R-8 — `C-FLOW-12` is free to mint

`capability_matrix.md` — the authoritative ID source — maxes at **C-FLOW-11**. `C-FLOW-12` appears
in 9 files, all forward references from INT-US-21's docs plus `TECH-014` and `TECH-016`.
Investigated per the `specweaver-ticket` skill; benign.

### R-9 — What SF-01/SF-02 guarantee (do not re-implement)

Approve-on-resume (`engine/approval.py`), hydration + rehydration (`engine/hydration.py`), artifact
and stubs (`handlers/decomposition_artifacts.py`), the `DECOMPOSITION_PLAN_KEY` seam. SF-03
**drives** them through the real CLI.

### R-10 — A component name can collide with the feature spec

Against `spec_path.with_name(f"{name}_spec.md")`:

| component | writes | |
|---|---|---|
| `auth` | `auth_spec.md` | fine |
| `onboarding` | `onboarding_spec.md` | fine |
| **`onboarding_feature`** | **`onboarding_feature_spec.md`** | **IS the feature spec** |

Never-overwrite (`is_file()`) protects the file, but the report says **`skipped`** — "a component
spec already exists" — when what sits there is the user's feature spec and no stub was produced.
Code from SF-02 (`ce00be20`). D1.

### R-11 — The loop-back arm is unexercised

`feature_decomposition.yaml`: `validate_feature` has `on_fail: loop_back`,
`loop_target: draft_feature`, `max_retries: 3`. A spec that **FAILS** the battery loops back to
drafting, which headless-parks. Nothing drives that arm (SF-02's `coverage < 1.0` tests hit the
*decompose* gate). NFR-2: `attempts` re-initialises per `_execute_loop` entry (`runner.py:210`), so
**each resume grants a fresh 3 strikes**.

### R-12 — Teardown is unproven on this platform

`runner.py:138-140` and `:191-193` — both `run()` and `resume()` end in
`finally: await self._save_handover(run); self._flush_telemetry()`. The CLI prints *"Interrupted.
Run state saved. Resume with: sw run --resume"*. No test checks that for this journey; `TECH-017`
found graceful shutdown unproven repo-wide, and the one SIGINT e2e opens with
`pytest.skip("SIGINT testing requires POSIX signals or complex Windows workaround.")` — so it would
start running, unexercised, on the Ubuntu migration.

### R-13 — The interrupt hint cannot name the run

`cli.py:221-236`: `except KeyboardInterrupt` sits *outside* `_execute_run(...)`, so the run_id
generated inside it is out of scope. The message prints `sw run --resume` with no id; the park
message (`display.py:234`) prints `sw run --resume <run_id>`. D2.

### Architecture check

| Mechanism | Where | Category | Constraint check | Verdict |
|---|---|---|---|---|
| Bare-name → `specs/<name>_feature_spec.md` | `core/flow/interfaces/cli.py` | delivery-mechanism logic | `interfaces` may own CLI argument resolution | ✅ |
| Import `FEATURE_SPEC_SUFFIX` from `handlers/draft.py` | `cli.py` | intra-`core/flow` import | `interfaces` → `handlers`, existing direction | ✅ |
| e2e suite | `tests/e2e/capabilities/workflows/` | test | mirrors INT-US-24's placement | ✅ |
| Guides 1–2 | `docs/dev_guides/`, `docs/user_guides/` | docs | no code impact | ✅ |

Zero new tach edges, zero new `consumes`, no new module.

## Changes

Five commit boundaries — more than the original three, deliberately: every gate run in this feature
had surfaced a live defect, and smaller diffs review better.

### CB-1 — Bare-name resolution + `kind` passthrough (FR-8)

Files: `[MODIFY] core/flow/interfaces/cli.py`,
`[NEW] tests/integration/interfaces/cli/test_feature_spec_resolution.py`

1. Extend `_resolve_spec_path` branch 2 for `feature_decomposition`:
   `project/specs/<name>{FEATURE_SPEC_SUFFIX}` — imported (R-2).
2. `new_feature` resolution unchanged (NFR-1 regression).
3. **`kind` passthrough proof** — the YAML sets `params: kind: feature` and `ValidateSpecHandler`
   selects `validation_spec_feature` from it. The reachability test proves the handler resolves,
   not which **battery** runs; a silent fallback to `validation_spec_default` would leave every
   downstream assertion green.

### CB-2 — Two defects found during planning

Files: `[MODIFY] handlers/decomposition_artifacts.py`, `[MODIFY] core/flow/interfaces/cli.py`

1. **R-10** — a component whose stub path equals `context.spec_path` is reported distinctly (D1).
2. **R-13** — the interrupt message names the run (D2).

Both in code committed earlier (`ce00be20`; `cli.py` inherited). SF-02's walkthroughs are **not**
edited — they record what was true at that commit.

### CB-3 — Verifiable proof: the journey (FR-10)

Files: `[NEW] tests/e2e/capabilities/workflows/test_feature_decomposition_e2e.py`

| # | Scenario | Proves |
|---|---|---|
| E1 | happy 3-session journey | both approve-on-resume advances, artifact + stub inventory, **persisted status** (R-4), one decompose LLM call |
| E2 | coverage < 1.0 | FAILED with the coverage message; resume re-executes decompose |
| E3 | garbage LLM JSON | loud failure, no artifact |
| E4 | spec missing | headless park, no crash |
| E5 | cross-session rehydration | fresh `CliRunner` per session |
| E6 | zero-component plan | artifact written, no stubs, COMPLETED |
| E7 | stub no-overwrite | a hand-authored component spec is byte-identical afterwards |
| **E8** | **validate FAILS -> loop_back -> draft park** | the R-11 arm, plus the 3-strike bound |
| **E9** | **component named `<feature>_feature`** | R-10, through the CLI |
| **E10** | **journey re-run on the same spec** | uuid stable, stubs skipped, still COMPLETED |
| **E11** | **resume a run that never parked** | refuses cleanly rather than double-approving |

### CB-4 — Teardown & interrupt survival (R-12)

Files: same e2e module, separate scenario group

| # | Scenario | Proves |
|---|---|---|
| E12 | interrupt mid-journey | the run is resumable afterwards — the `finally:` handover claim |
| E13 | the interrupt hint | carries a run_id a user can actually paste (depends on CB-2) |
| E14 | telemetry flush on interrupt | `_flush_telemetry()` ran; no half-written artifact |

Write these POSIX-first with an explicit Windows conditional, never a blanket `pytest.skip` — a
skip that hides a gap is the failure mode this feature corrects.

### CB-5 — Docs currency + registry closure

Files: `[MODIFY] docs/dev_guides/pipeline_engine_guide.md`,
`[MODIFY] docs/user_guides/4_interactive_hitl_gates.md`,
`[MODIFY] docs/roadmap/capability_matrix.md`, `topic_03_*`, `US-21_integration.md`

1. Guide-1: journey block — CLI, exit codes (incl. **PARKED -> 0**), artifact contract,
   approve-on-resume, the R-7 host-posture fact.
2. Guide-2: resume **is** approval of a gate-park.
3. Mint `C-FLOW-12` (R-8) and `INT-US-21-SF02`; US-21 -> green.
4. Closure gate: `check_fr_coverage.py INT-US-21` exits 0 **and** a green full suite.

### Design coverage

| Design item | Discharged by | Note |
|---|---|---|
| NFR-1 delivered-journey compat | CB-1 regression | `new_feature` resolution unchanged |
| NFR-3 LLM economy | CB-3 | decompose LLM call count == 1 for the happy journey |
| NFR-7 observability | CB-3 | `approved_on_resume` marker on both advances |
| NFR-8 host posture | CB-5 docs | Guide-1, not worked around (R-7) |
| AD-9 → `TECH-018` | — | no longer gates closure; SF-03 does not run the audit |

## Tests

| Bucket | Case |
|---|---|
| Happy | E1, E6, E7, E10 |
| Boundary | bare-name vs explicit-path vs non-existent name; a spec already ending in `_feature_spec`; zero components; `coverage_score` exactly 1.0; **E9**; **E11** |
| Degradation | E2, E4, E5, **E8** (and the 3-strike bound NFR-2 says resets per session); a deleted artifact between park and resume; **E12–E14** |
| Hostile | E3; a spec path outside the project; a bare name containing a path separator (must not escape `specs/`); an LLM that raises rather than returning malformed output |

## Decisions (audit)

All six adopted as recommended (user, 2026-07-26).

| # | Decision | Why |
|---|---|---|
| D1 | **A fifth stub-report key, `collided`** — a component whose stub path equals `context.spec_path`. The report was `{created, skipped, rejected, failed}` | `rejected` = "fix the LLM output"; `collided` = "rename the component". `skipped` lies (claims a component spec exists where the user's feature spec sits). AD-4 freezes `context.decomposition`, the artifact schema, stub paths and `proposed_dal` — **not** the report shape |
| D2 | **Handle `KeyboardInterrupt` inside `_execute_run`**, where `run` is in scope | The outer handler cannot see the run_id (R-13). A mutable holder threaded outward leaves the id's provenance implicit. `--resume <id>` runs already know their id; only fresh runs need this |
| Q1 | **The e2e drives `sw run --resume <run_id>`** — what the park message prints | A user follows what they are shown (`display.py:234`); the design's "`sw resume`" wording is the stale half; Guide-2 documents the surface the park advertises |
| Q2 | **No in-session drafting scenario** | AD-5: zero drafting-UX investment, spec-pre-exists posture (INT-US-24 E6 precedent). E1 pre-creates the spec so `draft_feature` exists-skips. `FeatureDrafter` is a `D-INTL-07` supersession target |
| Q3 | **Document the `session_isolation` limit, do not assert it** | Asserting `C-EXEC-06` raises couples this suite to another capability's internals; Guide-1 records it (R-7) |
| Q4 | **US-21 goes green in CB-5** | `TECH-018` no longer gates closure (AD-9); the base contract is what US-21's Core-Required MVS asked for. `INT-US-21-SF02` and `C-FLOW-12` minted Pending Design |

## As built

| CB | Scope | FR | Commit |
|----|-------|----|--------|
| CB-1 | Bare-name resolution + `kind` battery passthrough | FR-8 | `8fff2470` |
| CB-2 | Spec-name collision reporting + interrupt run id (R-10, R-13) | — | `d0c020f4` |
| CB-3 | Verifiable proof: the journey | FR-10 | `ccdda8f8` |
| CB-4 | Interrupt survival & teardown | FR-10 | `39aa3860` |
| CB-5 | Guides + registry closure | — | see [CB-5 walkthrough](INT-US-21_sf03_cb5_walkthrough.md) |

From the commit messages (CB-1–CB-4 have no walkthrough):

- **CB-1**: resolution lives in `core/flow/interfaces/spec_path_resolution.py` (`resolve_spec_path`)
  — `cli.py` hit 619 lines against the 600 RED threshold. `kind=feature` → 11 rules without S04;
  no `kind` → 12 with S04, proven handler-driven.
- **CB-2**: `collided` is checked before `is_file()`. D2 as written did not work — `PipelineRunner.run()`
  keeps its run local — so the runner exposes a read-only `current_run_id`; the outer handler stays
  as a fallback for interrupts before a run exists. `sw resume <id>` and `sw run --resume <id>` both
  stay; the enforced contract is that every resume instruction carries a run id (an AST scan).
- **CB-3**: 18 scenarios. E2/E3 park at the HITL review gate rather than FAIL — a HITL gate parks
  unconditionally, the AD-2 *failed* gate-park flavour. E11 found a resume of a COMPLETED run left
  it stuck in RUNNING forever; now refused by `engine/resumability.py` + `interfaces/resume_policy.py`.
  E8 found the loop-back arm unbounded across sessions (NFR-2) and the failing result discarded →
  `TECH-021`, pinned by a strict `xfail`. `check_fr_coverage.py INT-US-21` exits 0.
- **CB-4**: written in-process (Python surfaces SIGINT as `KeyboardInterrupt`), not by a real
  signal; OS-level delivery is the stated gap. Resumability is proven; the handover/telemetry flush
  is **not** (disabling both leaves the tests green) — `TECH-017`'s repo-wide finding.
