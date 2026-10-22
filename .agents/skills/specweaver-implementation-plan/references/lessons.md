# Why the rules exist

The incidents behind the rules in `SKILL.md`. Each rule stays in the skill; this file keeps the story.

## Pre-condition 1 — prerequisites green in code

INT-US-21's design recorded its prerequisites as "all ✅: US-2 Core, D-INTL-02, D-INTL-03" — and
**all three were materially broken**: handlers never registered so the shipped pipeline could not
run a single step; `RunContext.plan` documented as "(set by runner hook)" with zero writes in
`src/`; a required enum that cannot be serialized to YAML at all. Every checkbox was true as
written and false in fact.

## Pre-condition 5 — never let a plan settle a number the design left open

That is how a `$25` spend cap that bills real money shipped in one session with no input.

## Test tier — never defer all integration work to one final boundary

That is how SF-02 CB-1 came to ship 16 unit tests and zero others.

## Test tier — a "write the missing test" boundary is done when the test kills a mutant

This is not ceremony. `TECH-017` wrote a containment test that passed immediately and proved
nothing — the function it covered returned `{}` for every caller, so the assertion could not fail.
The mutant was what said so, and chasing it found a key mismatch that had kept skeleton context
out of every generation and review prompt since the feature shipped.

## Integration is implicit

`TECH-041` is one instance of a seam FR proven by mocks: `C-VAL-03` is `✅` and its DAL override is
proven link by link, never as a chain.

Integration used to be the one carve-out from "a defect in closed code becomes a `TECH` ticket",
and the carve-out is what grew a second registry: measured 2026-08-19, 31 of 36 open contract rows
were tracking work that another ticket already owned.
