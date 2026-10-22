# Why the rules exist

The incidents behind the rules in `SKILL.md`. Each rule stays in the skill; this file keeps the story.

## Phase 0 — why the precondition gate is Phase 0 and not advice

INT-US-21's design recorded its prerequisites as "all ✅: US-2 Core, D-INTL-02, D-INTL-03". All
three were materially broken: the shipped `feature_decomposition.yaml` could not execute a single
step because two handlers were never registered; `RunContext.plan` was documented as "(set by
runner hook)" with **zero** writes in `src/`; and a required enum could not be serialized to YAML
at all. Every checkbox was true as written and false in fact, and the whole story became an
archaeology exercise instead of an integration. The gate checks the *evidence*: the declared proof
exists, passes and does not skip; every bundled pipeline step resolves to a real handler; no field
documented as "set by X" is unwritten.

## Phase 0b — why a path a single feature can walk is never restated

Restating one is what credited 41 unit tests to a seam holding six claims while both capabilities
read as untested for three months.

## Phase 4 — why filing a follow-up does not satisfy the closure gate

Six tickets were filed on 2026-08-13 in one day, several as the "outcome" of resolving an earlier
one.

## Phase 4 — why the closure gate is a gate and not a checklist item

`D-INTL-02` §6.2 promised `<name>_decomposition.yaml` plus stub component specs, shipped neither,
and was marked ✅. It also declared `(DRAFT, FEATURE)` valid without registering a handler, so the
pipeline it shipped could not execute one step. Both survived because nothing checked the design's
promises against the code, and the proof only ever drove handlers directly instead of the
artifacts users get. These two commands are that check.
