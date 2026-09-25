# INT-US-21 SF-02 CB-3 — Walkthrough: Plan-Bridge Seam Pin (FR-9b) + DAL Summary (FR-7)

**Commit boundary:** 3 of 3 (`5aa20ffa`) — **SF-02 complete** · **Date:** 2026-07-26 · Plan:
[sf02](INT-US-21_sf02_implementation_plan.md) §Changes → CB-3

## Delivered

**FR-9(b) — the plan bridge, pinned to production wiring.** `D-INTL-03` shipped `PlanSpecHandler`,
and `GenerateCodeHandler` enriches its prompt from `context.plan`, but `RunContext.plan` ("(set by
runner hook)") had **zero writes in `src/`** until SF-01 CB-2 added `hydrate_plan_context`.
`test_planning_integration.py` proves `PlanSpecHandler` writes a loadable `_plan.yaml` (I8) and,
separately, that a **hand-seeded** `RunContext(plan=...)` reaches the generator (I9/I10) — both
pass with the bridge missing.

`tests/integration/core/flow/engine/test_seam_pins.py`: a real `plan+spec` step through the real
registry and hook; the value at the next step must equal **the artifact on disk**.

| Test | Claim |
|---|---|
| `test_plan_reaches_the_next_step_without_being_seeded` | the hook populates `context.plan` at all |
| `test_the_value_is_the_artifact_on_disk_not_something_invented` | it came from `plan_path`, not from the capture handler proving itself |
| `test_the_plan_bridge_does_not_populate_the_decomposition_seam` | AD-1: two plan concepts, two fields |
| `test_the_hook_is_what_sets_it` | a `plan_path` pointing at a missing file leaves the field unset and the run degrades rather than crashing |

Scope, stated in the file: the generate step is a capture double — this proves *the hook delivers*,
not *the generator consumes* (I9/I10). The on-disk equality keeps the capture handler from being a
self-fulfilling stub.

**FR-7 — the DAL summary.** Per D2, `build_dal_summary()` puts it in the handler's own output (no
park surface renders `StepResult.output`, R-4); SF-03's CLI journey owns rendering. Naming the
artifact file lets a human review it before resuming (NFR-7):

```
Decomposition artifact: onboarding_feature_spec_decomposition.yaml
2 component(s), proposed DAL per component:
  auth     DAL_B
  billing  DAL_D
Component specs: 2 created
```

**CB-2's two gaps closed:** a component listed twice is created once, then skipped — first
description wins; a component dict with no `component` key is reported as `<unnamed>`, not `"None"`.

**Test file-size threshold: 800** (user, 2026-07-26), set explicitly in `check_file_sizes.py`
instead of `SRC_WARN * 1.5` = 675, reasoning in the script: a thorough test file runs long, and
splitting one contract's file to satisfy a threshold makes coverage harder to audit. Repo-wide
warnings 36 → 24; the four large files (810–841) still warn.

## Proof

| Tier | Count |
|---|---|
| Integration (`test_seam_pins.py`) | 4 |
| Integration (`test_decomposition_artifacts_integration.py`) | 28 |
| Unit (`test_decompose_artifact.py`) | 56 |

Probe: disabling `context.plan = Path(raw_path).read_text(...)` fails exactly the two tests that
assert the bridge; the two asserting *absence* stay green.

ruff · mypy · `tach check` *All modules validated* · C901 · `check_file_sizes` 0 errors ·
`check_roadmap_sync` · `check_skill_sync` — all clean.

| CB | Scope | FR | Commit |
|----|-------|----|--------|
| CB-1 | Decomposition artifact persistence | FR-5, FR-7 data | `4a42b87a` |
| CB-2 | Stub component specs | FR-6 | `ce00be20` |
| CB-3 | Plan-bridge seam pin + DAL summary | FR-9(b), FR-7 | `5aa20ffa` |
