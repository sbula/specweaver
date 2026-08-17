# Design: Custom Rule Paths

- **Feature ID**: D-VAL-02
- **Epic**: Topic 05 (Validation)
- **Status**: ✅ Delivered — this document is a **record**, not a plan.
- **Legacy**: 3.4
- **Created**: 2026-08-17 under `INT-US-25-SF01-MIG`. The capability shipped with an implementation
  plan and **no design document**, so no requirement of it existed in the ledger's form and neither
  sweep had anything to count.

## What shipped

The validation battery stops being a fixed list. A project declares its own pipelines in YAML, inherits
from packaged ones with `extends` / `override` / `remove` / `add`, drops its own `D`-prefixed rule
classes into a directory, and overrides all of it locally — without changing SpecWeaver.

`ValidationPipeline` / `ValidationStep` models, `inheritance.resolve_pipeline`, `pipeline_loader` with
its three-tier lookup (project-local → packaged → framework plugin), `loader` for custom rule classes,
`sw list-rules`, a `--pipeline` override, and `apply_settings_to_pipeline()` bridging stored settings
onto a resolved pipeline.

**Complete:** 10 components, 2181 tests at delivery.

## Functional Requirements

Written 2026-08-17 under `specweaver-dev` §3.2c, on contact from `INT-US-25-SF01-MIG`. Written from
**why the capability exists** — a project's assurance rules are the project's business, and adopting
SpecWeaver should not mean adopting its opinions — not from an inventory of its modules. Each is behind
a killed mutant.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A pipeline can be defined by difference | Project | Declares `extends` with `override`, `remove` and `add` against a packaged pipeline | A project states what it wants *changed*, instead of restating a whole battery to alter one step |
| FR-2 | A cyclic `extends` chain is refused | System | Resolves a pipeline whose inheritance loops | The chain is reported by name, rather than recursing until the interpreter stops it |
| FR-3 | A project's own rules run | Project | Drops `D`-prefixed rule classes into a rules directory | Rules SpecWeaver has never seen are discovered, validated and registered |
| FR-4 | Stored settings reach the resolved pipeline | System | Applies `ValidationSettings` onto a pipeline | A rule disabled or re-thresholded in settings is disabled or re-thresholded in the run — the two configuration systems agree |
| FR-5 | The project's copy wins | Project | Places `<name>.yaml` in `.specweaver/pipelines/` | The local definition takes precedence over the packaged and framework ones, so an override is a file rather than a fork |

**FR-1's mutant fails 71 test files** — the widest measured anywhere in this migration. Disabling the
`remove` directive alone breaks the packaged pipelines that use inheritance to build themselves, and
almost every validation path runs through one. **FR-4's fails 20**, **FR-5's 13**, **FR-3's 4**, and
**FR-2's 3**.

That spread is the useful part of the exercise. FR-2's guard is the narrowest thing here and the only
one protecting against a stack overflow in a user-supplied file; FR-1 is the load-bearing beam. Neither
fact was visible from the topic entry, which lists ten components as equals.

## Non-Functional Requirements

None declared. No threshold for this capability is recorded anywhere in the repository, and inventing one
now would add a row nothing checks. Stated rather than left blank, per §3.2c.
