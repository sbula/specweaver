# Implementation Plan: Autonomous Feature Decomposition [SF-03: CLI Journey, Verifiable Proof & Registry Closure]

- **Feature ID**: INT-US-21
- **Sub-Feature**: SF-03 — CLI Journey, Verifiable Proof & Registry Closure
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_sf03_implementation_plan.md
- **Status**: APPROVED (user, 2026-07-26)
- **FRs in scope**: FR-8 (CLI journey), FR-10 (verifiable proof) + Guides 1–2 + registry closure
- **Depends on**: SF-01 COMPLETE (`f1de38f1`, `c4c1a109`, `6811a943`, `5ebcc414`),
  SF-02 COMPLETE (`4a42b87a`, `ce00be20`, `5aa20ffa`)

---

## Research Notes

Verified against `main` on 2026-07-26, after SF-02 landed. Two findings are **measured, not read**
— they were the highest-risk unknowns and both would have produced a vacuous e2e if assumed.

### R-1 — `_resolve_spec_path` already accepts an explicit path

`core/flow/interfaces/cli.py`. Order of resolution:

1. `if Path(spec_or_module).exists(): return it` ← **an explicit path works TODAY**
2. `if pipeline_name == "new_feature": return project/specs/<name>_spec.md`
3. try `project/<arg>`; else return the literal path

So `sw run feature_decomposition specs/onboarding_feature_spec.md` already resolves, and only the
**bare-name** form (`sw run feature_decomposition onboarding`) is unsupported. FR-8's fix is
therefore a small addition to branch 2, not a rewrite — and the e2e is not blocked on it.

### R-2 — the suffix constant must be imported, never re-hardcoded

`FEATURE_SPEC_SUFFIX = "_feature_spec.md"` at `handlers/draft.py:24`, consumed at `:246`, `:331`,
`:333`. SF-01 CB-1's `DraftFeatureHandler` **errors loudly** when `spec_path` does not match it. A
second literal in `cli.py` would drift and trip that guard on every drafting run. This is a design
Session-Handoff constraint, restated here because it is easy to miss.

### R-3 — ⚠️ MEASURED: a realistic feature spec passes the battery with warnings

The highest-risk unknown. SF-01 found "a fixture that could not pass its own battery" among five
vacuous proofs; if SF-03's fixture cannot clear `validation_spec_feature`, the journey dies at step
2 and the e2e proves nothing. Probed with `execute_validation_pipeline` against a realistic
candidate:

| | |
|---|---|
| battery | `validation_spec_feature` — 11 rules (default minus `s04_dependency_dir`) |
| result | **8 pass, 3 warn, 0 fail** |
| warnings | S09 (no structured error section), S11 (1 terminology issue), S07 (no Scenarios section → testability 9/12) |

Decisive: `validation.py:97-98` computes
`failed = [r for r in results if r.status == RuleStatus.FAIL]; all_passed = len(failed) == 0`.
**Warnings do not fail the step.** The fixture needs zero FAILs, not 11/11 clean — a materially
easier target, and the difference between a runnable e2e and an impossible one.

> Do **not** chase the three warnings into the fixture. Adding a Scenarios section to satisfy S07
> would make the fixture unrepresentative of what a user actually hands to `feature_decomposition`.

### R-4 — ⚠️ PARKED and COMPLETED both exit 0

`cli.py:404-418`: COMPLETED → `0`, FAILED → `1`, **PARKED → `0`** with the comment *"Not an error,
just parked"*.

This is the precise defect that made INT-US-02's E6/E7 vacuously green. **Every assertion in this
suite must read the persisted run status from the store**, never the process exit code. Exit code
may be asserted *in addition*, never *instead*.

### R-5 — two resume surfaces; the park message advertises one of them

`sw run --resume <run_id>` (option, `cli.py:188-190`) and a separate `resume` command
(`cli.py:422`). `display.py:234` prints exactly `Resume with: sw run --resume <run_id>`.

The design's FR-8 says "`sw resume`". A user follows what the park message prints, so the e2e
should drive `sw run --resume`. See **Q1**.

### R-6 — the INT-US-24 harness is the pattern to copy

`tests/e2e/capabilities/workflows/test_int_us_24_scenario_e2e.py`: module-level
`runner = CliRunner()`, `pytestmark = pytest.mark.e2e`, real `specweaver.interfaces.cli.main.app`,
scripted LLM responses, per-scenario fixtures. Its docstring enumerates E1–E8 with what each proves
— worth imitating, because it makes an unproven claim visible in review.

### R-7 — host posture: `session_isolation` must be OFF

NFR-8. `C-EXEC-06` v1 **raises** on any park inside a session worktree, by design (its AD-4). The
`feature_decomposition` journey parks twice, so it cannot run under session isolation. This is a
documented fact, not a bug to work around here. See **Q3**.

### R-8 — `C-FLOW-12` is free to mint (investigated, not assumed)

The authoritative source for capability IDs is `capability_matrix.md`, which maxes at **C-FLOW-11**.
`C-FLOW-12` appears in 9 files — all of them forward references from INT-US-21's own docs plus
`TECH-014` and `TECH-016`. Registry-vs-mention disagreements are the exact case the `specweaver-ticket`
skill says to investigate before minting; investigated, benign, free.

### R-9 — what SF-01/SF-02 already guarantee (do not re-implement)

Approve-on-resume (`engine/approval.py`), hydration + rehydration (`engine/hydration.py`), the
artifact and stubs (`handlers/decomposition_artifacts.py`), and the `DECOMPOSITION_PLAN_KEY` seam.
SF-03 **drives** these through the real CLI; it does not re-test them at unit level.

### R-10 — a component name can collide with the feature spec's own filename

Verified arithmetic against `spec_path.with_name(f"{name}_spec.md")`:

| component | writes | |
|---|---|---|
| `auth` | `auth_spec.md` | fine |
| `onboarding` | `onboarding_spec.md` | fine |
| **`onboarding_feature`** | **`onboarding_feature_spec.md`** | **IS the feature spec** |

Never-overwrite (`is_file()`) protects the file, but the report classifies it as **`skipped`** —
which a reader takes to mean "a component spec already exists". It does not; what is sitting there
is the user's own feature spec, and no stub was produced. The user is told they have something they
do not have. Found during SF-03 planning; the code is SF-02's (`ce00be20`). See **D1**.

### R-11 — the entire loop-back arm is unexercised

`feature_decomposition.yaml`: `validate_feature` carries `on_fail: loop_back`,
`loop_target: draft_feature`, `max_retries: 3`. A spec that **FAILS** the battery therefore loops
back to drafting, which headless-parks.

Nothing in the suite drives that arm. SF-02's coverage tests exercise `coverage < 1.0` at the
*decompose* step — a different gate on a different step. Compounding it, NFR-2 records an inherited
limit: `_execute_loop` re-initialises `attempts` on every entry (`runner.py:210`), so **each resume
grants a fresh 3 strikes**. Documented, unpinned.

### R-12 — teardown is real work, and unproven on this platform

`runner.py:138-140` and `:191-193` — **both** `run()` and `resume()` end in
`finally: await self._save_handover(run); self._flush_telemetry()`. The CLI advertises the result:
*"Interrupted. Run state saved. Resume with: sw run --resume"*.

No test checks that claim for this journey. `TECH-017` already found graceful shutdown effectively
unproven repo-wide, and the single SIGINT e2e opens with
`pytest.skip("SIGINT testing requires POSIX signals or complex Windows workaround.")` — so the
interrupt path is untested **on the platform in use today**, and will begin running, unexercised,
on the Ubuntu migration.

### R-13 — the interrupt hint cannot name the run, and the fix is structural

`cli.py:221-236`: `except KeyboardInterrupt` sits *outside* `_execute_run(...)`, which has already
raised — so the run_id generated inside it is **out of scope**. The message prints
`sw run --resume` with no id, while the park message (`display.py:234`) prints
`sw run --resume <run_id>`. A user who presses Ctrl-C is handed an instruction they cannot follow.

Not a one-line fix: the run_id must be surfaced out of `_execute_run`. See **D2**.

---

## Architecture Verification (Phase 3)

| Mechanism | Where | Category | Constraint check | Verdict |
|---|---|---|---|---|
| Bare-name → `specs/<name>_feature_spec.md` | `core/flow/interfaces/cli.py` | delivery-mechanism logic | `interfaces` may own CLI argument resolution; extends an existing branch | ✅ |
| Import `FEATURE_SPEC_SUFFIX` from `handlers/draft.py` | `cli.py` | intra-`core/flow` import | `interfaces` → `handlers`, same module, existing direction | ✅ |
| e2e suite | `tests/e2e/capabilities/workflows/` | test | mirrors INT-US-24's placement | ✅ |
| Guides 1–2 | `docs/dev_guides/`, `docs/user_guides/` | docs | no code impact | ✅ |

**Zero new tach edges. Zero new `consumes`.** No new module, so no cycle and no stability-direction
change is possible.

---

## Design Coverage Map

| Design item | Discharged by | Note |
|---|---|---|
| FR-8 CLI journey | CB-1 | bare-name resolution + display/exit-code parity |
| FR-10 verifiable proof | CB-2 | the e2e suite; the FIRST test to drive a bundled pipeline through a HITL gate |
| NFR-1 delivered-journey compat | CB-1 regression | `new_feature` resolution must not change |
| NFR-3 LLM economy | CB-2 | assert decompose LLM call count == 1 for the happy journey |
| NFR-7 observability | CB-2 | assert the `approved_on_resume` marker on both advances |
| NFR-8 host posture | CB-3 docs | documented in Guide-1, not worked around (R-7) |
| AD-9 → `TECH-018` | — | no longer gates closure; SF-03 does not run the audit |
| Guides 1–2 | CB-3 | `pipeline_engine_guide.md`, `4_interactive_hitl_gates.md` |
| Registry closure | CB-3 | US-21 🟢, `C-FLOW-12` minted, `INT-US-21-SF02` minted |

---

## Work Breakdown — Commit Boundaries

Five boundaries. More ceremony than the original three, deliberately: every gate run in this
feature so far has surfaced a live defect, and smaller diffs review better.

### CB-1 — Bare-name resolution + `kind` passthrough (FR-8)

**Files**: `[MODIFY] core/flow/interfaces/cli.py`,
`[NEW] tests/integration/interfaces/cli/test_feature_spec_resolution.py`

1. Extend `_resolve_spec_path` branch 2 for `feature_decomposition`:
   `project/specs/<name>{FEATURE_SPEC_SUFFIX}` — **imported**, per R-2.
2. `new_feature` resolution unchanged (NFR-1 regression).
3. **`kind` passthrough** — the bundled YAML sets `params: kind: feature` and `ValidateSpecHandler`
   selects `validation_spec_feature` from it. Nothing proves that today: the reachability test
   proves the handler *resolves*, not that the right **battery** runs. If it silently fell back to
   `validation_spec_default`, every downstream assertion still passes while the wrong rules ran.

### CB-2 — Two defects found during planning

**Files**: `[MODIFY] handlers/decomposition_artifacts.py`, `[MODIFY] core/flow/interfaces/cli.py`

1. **R-10 collision** — a component whose stub path equals `context.spec_path` is reported
   distinctly instead of as `skipped` (D1).
2. **R-13 interrupt hint** — the message names the run (D2).

> Both are defects in code committed earlier today (`ce00be20`; `cli.py` inherited). SF-02's
> walkthroughs are **not** edited — they record what was true at that commit. The fixes land here
> with their origin stated.

### CB-3 — Verifiable proof: the journey (FR-10)

**Files**: `[NEW] tests/e2e/capabilities/workflows/test_int_us_21_decomposition_e2e.py`

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

**Files**: same e2e module, separate scenario group

| # | Scenario | Proves |
|---|---|---|
| E12 | interrupt mid-journey | the run is resumable afterwards — the `finally:` handover claim |
| E13 | the interrupt hint | carries a run_id a user can actually paste (depends on CB-2) |
| E14 | telemetry flush on interrupt | `_flush_telemetry()` ran; no half-written artifact |

> **Write these POSIX-first with an explicit Windows conditional, never a blanket
> `pytest.skip`.** The existing SIGINT e2e skips wholesale on Windows, which is why this path is
> unproven today and why it would surface, unexercised, on the Ubuntu migration. A skip that hides
> a gap is the failure mode this feature exists to correct.

### CB-5 — Docs currency + registry closure

**Files**: `[MODIFY] docs/dev_guides/pipeline_engine_guide.md`,
`[MODIFY] docs/user_guides/4_interactive_hitl_gates.md`,
`[MODIFY] docs/roadmap/capability_matrix.md`, `topic_03_*`, `US-21_integration.md`

1. Guide-1: journey block — CLI, exit codes (incl. **PARKED -> 0**), artifact contract,
   approve-on-resume, the R-7 host-posture fact.
2. Guide-2: resume **is** approval of a gate-park.
3. Mint `C-FLOW-12` (R-8) and `INT-US-21-SF02`; US-21 -> green.
4. Closure gate: `check_fr_coverage.py INT-US-21` exits 0 **and** a green full suite.

---

## Decisions needed (Phase 4 HITL)

**D1 — how should a feature-spec name collision be reported (R-10)?**
The stub report is `{created, skipped, rejected, failed}`. A collision is neither: the name is
*valid* (so not `rejected`) and no component spec exists (so `skipped` is a lie).
*Recommendation: a fifth key `collided`.* `rejected` means "fix the LLM output"; `collided` means
"rename the component" — different user actions deserve different buckets. AD-4 freezes
`context.decomposition`, the artifact schema, stub paths and `proposed_dal` — **not** the stub
report shape — so adding a key breaks no frozen seam.

**D2 — how does the interrupt handler learn the run_id (R-13)?**
*Recommendation: move the `KeyboardInterrupt` handling into `_execute_run`,* where `run` is in
scope, rather than threading a mutable holder out to the caller. Note that `--resume <id>` runs
already know their id at the outer level; only fresh runs need this.

---

## Test Plan (4 adversarial buckets)

**Happy** — E1, E6, E7, E10.
**Boundary** — bare-name vs explicit-path vs non-existent name; a spec whose name already ends in
`_feature_spec`; zero components; `coverage_score` exactly 1.0; **E9** the feature-spec name
collision; **E11** resume of a non-parked run.
**Degradation** — E2, E4, E5, **E8** (validate fails -> loop_back -> park, and the 3-strike bound
NFR-2 says resets per session); a deleted artifact between park and resume; **E12–E14** interrupt
and teardown.
**Hostile** — E3; a spec path outside the project; a bare name containing a path separator (must
not escape `specs/`); an LLM that raises rather than returning malformed output.

---

## Open Questions (Phase 4 HITL)

**Q1 (MED) — which resume surface is the contract?** FR-8 says `sw resume`; the shipped park message
prints `sw run --resume <run_id>` (R-5). Both exist.
*Recommendation: the e2e drives what the park message prints,* since that is what a user follows,
and Guide-2 documents that one. Making them diverge in docs would be a new defect.

**Q2 (MED) — does the e2e cover in-session drafting?** AD-5 mandates zero drafting-UX investment and
the spec-pre-exists posture (INT-US-24 E6 precedent).
*Recommendation: no.* E1 pre-creates the spec so `draft_feature` takes the exists-skip path. Adding
a drafting scenario would test `FeatureDrafter`, which is a `D-INTL-07` supersession target.

**Q3 (LOW) — should the e2e prove the `session_isolation` limit (R-7)?** Asserting that
`C-EXEC-06` raises on a park under isolation would pin a documented constraint.
*Recommendation: document only.* Asserting another capability's raise here couples this suite to
`C-EXEC-06`'s internals, and Guide-1 already records the fact.

**Q4 (LOW) — does US-21 go 🟢 in CB-3?** `TECH-018` no longer gates closure (the AD-9 relocation),
and `INT-US-21-SF02`/`C-FLOW-12` are minted as Pending Design.
*Recommendation: yes* — the base contract is what US-21's MVS required; the add-on is separately
tracked.

---

## Resolved Decisions (Phase 4/5 — user, 2026-07-26)

All six were presented with a recommendation and adopted as recommended.

| # | Decision | Rationale |
|---|---|---|
| D1 | **A fifth stub-report key, `collided`** — a component whose stub path equals `context.spec_path` | `rejected` means "fix the LLM output"; `collided` means "rename the component". Different user actions deserve different buckets, and `skipped` actively lies (it claims a component spec exists where the user's own feature spec sits). AD-4 freezes `context.decomposition`, the artifact schema, stub paths and `proposed_dal` — **not** the report shape — so the new key breaks no frozen seam |
| D2 | **Handle `KeyboardInterrupt` inside `_execute_run`**, where `run` is in scope | The outer handler cannot see the run_id because `_execute_run` has already raised (R-13). Threading a mutable holder outward would work but leaves the run_id's provenance implicit. `--resume <id>` runs already know their id; only fresh runs need this |
| Q1 | **The e2e drives `sw run --resume <run_id>`** — what the park message prints | A user follows the instruction they are shown (`display.py:234`). The design's "`sw resume`" wording is the stale half; Guide-2 documents the surface the park advertises. Leaving them divergent would create a new defect rather than close one |
| Q2 | **No in-session drafting scenario** | AD-5 mandates zero drafting-UX investment and the spec-pre-exists posture (INT-US-24 E6 precedent). `FeatureDrafter` is a `D-INTL-07` supersession target — testing it here buys coverage of code scheduled for replacement |
| Q3 | **Document the `session_isolation` limit, do not assert it** | Asserting that `C-EXEC-06` raises would couple this suite to another capability's internals. Guide-1 records the fact (R-7) |
| Q4 | **US-21 goes green in CB-5** | `TECH-018` no longer gates closure (the AD-9 relocation), and the base contract is exactly what US-21's Core-Required MVS asked for. `INT-US-21-SF02` and `C-FLOW-12` are minted Pending Design |

---

## Progress

| CB | Scope | FR | Status |
|----|-------|----|--------|
| CB-1 | Bare-name resolution + `kind` passthrough | FR-8 | ⬜ |
| CB-2 | Two defects found in planning (R-10, R-13) | — | ⬜ |
| CB-3 | Verifiable proof: the journey (E1–E11) | FR-10 | ⬜ |
| CB-4 | Teardown & interrupt survival (E12–E14) | FR-10 | ⬜ |
| CB-5 | Docs currency + registry closure | — | ⬜ |
