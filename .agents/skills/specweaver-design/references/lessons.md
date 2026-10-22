# Why the rules exist

The incidents behind the rules in `SKILL.md`. Each rule stays in the skill; this file keeps the story.

## Integration is implicit

`TECH-041` is one instance of a seam FR proven by mocks: `C-VAL-03` is `✅` and its DAL override is
proven link by link, never as a chain.

Integration used to be the one carve-out from "a defect in closed code becomes a `TECH` ticket",
and the carve-out is what grew a second registry: measured 2026-08-19, 31 of 36 open contract rows
were tracking work that another ticket already owned.

## Record a stopped HITL gate in the handover

`E-VAL-03` sat at its Phase 1 gate across sessions and was only picked up correctly because the
handover named the analysis document and said *do not restart the research* — without that line
the next session re-derives it.
