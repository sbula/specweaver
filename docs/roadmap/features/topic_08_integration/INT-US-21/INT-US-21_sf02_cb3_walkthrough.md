# Walkthrough: INT-US-21 SF-02 CB-3 — Plan-Bridge Seam Pin (FR-9b) + DAL Summary (FR-7)

- **Feature**: INT-US-21 — Autonomous Feature Decomposition (base integration contract)
- **Sub-feature**: SF-02 — Decomposition Artifacts & Frozen Seams
- **Commit boundary**: 3 of 3 — **SF-02 complete**
- **Implementation plan**: `INT-US-21_sf02_implementation_plan.md` §Work Breakdown → CB-3
- **Date**: 2026-07-26

## FR-9(b) — the plan bridge, pinned to production wiring

`D-INTL-03` shipped `PlanSpecHandler`, and `GenerateCodeHandler` enriches its prompt from
`context.plan`. Nothing connected them: `RunContext.plan` was documented as "(set by runner hook)"
with **zero writes anywhere in `src/`** until SF-01 CB-2 added `hydrate_plan_context`.

The pre-existing coverage could not have caught that, and this is the interesting part:
`test_planning_integration.py` proves `PlanSpecHandler` writes a loadable `_plan.yaml` (I8), and
*separately* that a **hand-seeded** `RunContext(plan=...)` reaches the generator (I9/I10).

> **Both halves pass while the bridge between them is missing** — precisely the state the repo was
> in for months. Seeding a field by hand proves the consumer works; it proves nothing about whether
> anything in production ever sets it.

`tests/integration/core/flow/engine/test_seam_pins.py` pins the missing middle. A real `plan+spec`
step runs through the real registry, the real hook fires, and the value visible at the next step is
asserted to equal **the content of the artifact on disk**.

| Test | Claim |
|---|---|
| `test_plan_reaches_the_next_step_without_being_seeded` | the hook populates `context.plan` at all |
| `test_the_value_is_the_artifact_on_disk_not_something_invented` | it came from `plan_path`, not from the capture handler proving itself |
| `test_the_plan_bridge_does_not_populate_the_decomposition_seam` | AD-1: two plan concepts, two fields |
| `test_the_hook_is_what_sets_it` | a `plan_path` pointing at a missing file leaves the field unset and the run degrades rather than crashing |

**Scope stated in the file, not implied:** the generate step is a capture double, so this proves
*the hook delivers*, not *the generator consumes*. That half is I9/I10's and is already covered.
The on-disk equality assertion is what keeps the capture handler from being a self-fulfilling stub
(vacuous-proof pattern 2).

**Probed:** disabling `context.plan = Path(raw_path).read_text(...)` fails exactly the two tests
that assert the bridge works; the two asserting *absence* correctly stay green.

## FR-7 — the DAL summary

D2: no park surface renders `StepResult.output` today (R-4), and changing `engine/display.py` would
touch shipped display used by every pipeline — wider than SF-02's remit. So `build_dal_summary()`
puts the text in the handler's own output and SF-03's CLI journey owns the rendering:

```
Decomposition artifact: onboarding_feature_spec_decomposition.yaml
2 component(s), proposed DAL per component:
  auth     DAL_B
  billing  DAL_D
Component specs: 2 created
```

Naming the artifact file is what lets a human review it before resuming (NFR-7).

## Both carried-forward gaps closed

CB-2's walkthrough recorded two gaps rather than burying them; both now have tests.

- A component listed twice in one plan: created once, then skipped. The first description wins and
  the duplicate never overwrites it.
- A component dict with no `component` key at all — the `not name` half of the guard. The report
  now says `<unnamed>` rather than the literal string `"None"`; the test I first wrote specified the
  unhelpful version and the implementation is the better answer.

## Two self-inflicted problems

A heredoc mangled `"\n".join(...)` into a literal newline inside a string literal, breaking
collection for 11 test files at once. And a bare `MagicMock` was passed as a context where
`load_component_template` needs a real path — the template loads *before* the component loop, so it
runs even when every component is rejected. Both surfaced immediately on running the tests; neither
reached a commit.

## File-size threshold raised for tests

`check_file_sizes.py` derived the test threshold as `SRC_WARN * 1.5` = 675. Per the user
(2026-07-26) the acceptable limit for test files is **800**, now set explicitly rather than scaled,
with the reasoning recorded in the script: a thorough test file legitimately runs long — four
adversarial buckets, a table of hostile inputs, and docstrings explaining what each seam proves all
cost lines, and splitting a file covering ONE contract just to satisfy a threshold makes coverage
harder to audit.

Repo-wide warnings fell 36 → 24. The four genuinely large files (810–841) still warn.

## Test results

| Tier | Count |
|---|---|
| Integration (`test_seam_pins.py`) | 4 |
| Integration (`test_decomposition_artifacts_integration.py`) | 28 |
| Unit (`test_decompose_artifact.py`) | 56 |

## Quality gates

ruff · mypy · `tach check` *All modules validated* · C901 · `check_file_sizes` 0 errors ·
`check_roadmap_sync` · `check_skill_sync` — all clean.

## SF-02 is complete

| CB | Scope | FR | Commit |
|----|-------|----|--------|
| CB-1 | Decomposition artifact persistence | FR-5, FR-7 data | `4a42b87a` |
| CB-2 | Stub component specs | FR-6 | `ce00be20` |
| CB-3 | Plan-bridge seam pin + DAL summary | FR-9(b), FR-7 | this commit |

Remaining for the epic: **SF-03** — the CLI journey (FR-8) and the verifiable e2e proof (FR-10),
plus registry closure. Note the two hard constraints SF-03 inherits, recorded in the design's
Session Handoff: `_resolve_spec_path` must derive `specs/{name}_feature_spec.md` and **import**
`FEATURE_SPEC_SUFFIX` rather than re-hardcode it, and existing coverage must be treated as
unverified until read.
