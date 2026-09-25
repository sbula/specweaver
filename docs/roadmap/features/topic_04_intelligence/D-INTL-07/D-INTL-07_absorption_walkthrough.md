# D-INTL-07 — Walkthrough: absorbing `D-INTL-04`

**Ticket**: none — a registry fold, not a build · **Kind**: docs · **DAL-D** · 2026-08-27

This file holds what the registries cannot: **which decisions were put to the user and what they
answered.** The reasoning lives where it governs — the tombstone in `topic_04`, the `ABSORBED`
section of [D-INTL-07_design.md](D-INTL-07_design.md), and `STATE.md`. A copy here would be the second
copy `PRINCIPLES.md` §5 forbids.

## Delivered

`D-INTL-04` folded into `D-INTL-07` as its second (bootstrap) rubric; `US-8` re-pointed and renamed.

Trigger: *"how does the existence of the grill-me skills change `D-INTL-04`?"* Not through the
skill: `grill-me` is **workbench** — a Claude Code skill in `.claude/skills/`, five lines, delegating
to a plugin; SpecWeaver cannot import, ship or depend on it, so `D-INTL-04` could never have used it.
It made the shape visible: `D-INTL-04` and `D-INTL-07` were both *adaptive interview → artefact*,
differing only in rubric content and output renderer. Neither is a capability. Two IDs described one
machine.

## Decisions taken with the user

| # | Question | Answer |
|---|---|---|
| 1 | Is the interview a capability or a substrate? | **Fold `D-INTL-04` into `D-INTL-07` as a second rubric** `[agreed 2026-08-27]` |
| 2 | `US-8`'s only capability is being retired — re-point or retire the story? | **Re-point to `D-INTL-07`** `[agreed 2026-08-27]` |
| 3 | Pre-commit Phase 2 — any tests for a docs-only registry change? | **None needed** `[agreed 2026-08-27]` |
| 4 | `US-8` is titled *The Greenfield Bootstrap **Wizard*** — the retired mechanic | **Rename** → *The Greenfield Bootstrap Interview* `[agreed 2026-08-27]` |
| 5 | Phase 7.5 finding: deleting the misfiled line orphaned an add-on group | **Delete the empty group** `[agreed 2026-08-27]` |

No gate was skipped or auto-approved.

**Decision 5 in numbers.** Removing `D-INTL-04`'s misfiled line from `US-18` left the add-on group
**`🔴 Secure Sandboxed Operations`** empty. Across the file: **72 add-on groups, exactly one empty** —
a hole this boundary made, not the file's convention. The group's **only member had been a design
questionnaire**, so the category never had a real capability behind it. Deleted; 71 groups, none
empty.

## Where each fact went

| Fact | Now lives |
|---|---|
| the goal — no guessing persistence, auth, archetype on a blank canvas | `D-INTL-07` design, ABSORBED |
| the output — a **localized** `context.yaml`, bound to the directory the command ran in | `D-INTL-07` design, ABSORBED + the rubric table |
| the *Monolith* mitigation | `D-INTL-07` design, ABSORBED |
| `Legacy: 3.52` → the architecture note | the tombstone line, as a path |
| **the un-passable-question requirement** | `D-INTL-07` design, What it does — moved out of the registry entry when `entry_depth` fired, not deleted |
| the fixed `Typer` wizard | **nowhere.** Superseded 2026-07-21, and that is the point |

## Records left alone, deliberately

- `INT-US-02` (APPROVED) and `INT-US-21` (COMPLETE) still name `D-INTL-04`: past scoping prose, true
  when written; the tombstone resolves the trail.
- `C-INTL-05` (APPROVED) was the exception: its line was a **forward dependency** — *"needs a
  `questionnaire_state` slot"* — that somebody would act on. A dependency naming a dead id is a
  statement that has become false, the one case trap 9 permits editing a delivered design.
  Corrected in place, saying why.
- `TECH-060`'s delivery record keeps the old story name. It is history.

## Proof

| Check | Result |
|---|---|
| full suite | 9,058 passed, 11 skipped |
| `quality.py cb` | 14 passed, 1 skipped, 0 failed |
| `quality.py doc` | 14 passed, 0 failed |
| `tests.py cb D-INTL-07 --kind refactor` | `ok, 0 path(s)` — *"this boundary changed no code"* |
| `tach` · coupling · `test_architecture.py` | clean · 355 modules in limits · 28 passed |

## Findings still open

- **Nothing mechanically stops `D-INTL-04` being reused.** The tombstone says *ID is dead* and the
  ticket skill's collision check greps every mention, so it will be found — but that is prose, not a
  check. Same protection `C-EXEC-05` has had since it was retired.
- **`D-INTL-07` is still `🔴` and still blocked on `C-FLOW-11`.** The fold changed what it owns, not
  when it can be built. Its design remains a STUB and has never been through `specweaver-design`.
- **`US-08`'s completed base-story prose still says "the graph the wizard produces".** Left
  untouched: that sentence is about `sw init`'s existing behaviour and belongs to a `✅` base story
  finished 2026-08-18, not to the retired questionnaire mechanic.
