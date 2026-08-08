# Design: Repo-Wide Dependency Cycles (check_coupling)

- **Feature ID**: TECH-024
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found while running `python scripts/quality.py cb` for TECH-001 SF-04
  (2026-08-02) — confirmed via `git stash` to be chronic and unrelated to that commit
  (identical failure list with or without SF-04's changes applied).

## Problem Statement

`check_coupling.py --cycles-only` currently reports **4 live import cycles**, reproducible via:
```
python scripts/check_coupling.py --cycles-only src
```

1. **Cycle of 3** — `specweaver.assurance.validation.registry` ⇄
   `specweaver.assurance.validation.rules.code.register` ⇄
   `specweaver.assurance.validation.rules.spec.register`
2. **Cycle of 6** — `specweaver.core.flow.engine.runner` ⇄ `engine.runner_utils` ⇄
   `engine.staleness` ⇄ `handlers.decompose` ⇄ `handlers.dual_pipeline` ⇄ `handlers.registry`.
   Overlaps the file `TECH-020` and `TECH-015` already target (`core/flow/engine/runner.py` /
   `runner_utils.py`) — coordinate with both rather than duplicating their scope; this ticket
   tracks the **cycle** (an import-direction defect), which is a different problem class from
   `TECH-020`'s file-size/complexity target and `TECH-015`'s grab-bag-module split, even though
   all three touch overlapping files.
3. **Cycle of 2** — `specweaver.infrastructure.llm.adapters._rate_limit` ⇄
   `specweaver.infrastructure.llm.factory`.
4. **Cycle of 5** — `specweaver.interfaces.api.app` ⇄ `interfaces.api.ui.htmx` ⇄
   `interfaces.api.v1.pipelines` ⇄ `interfaces.api.v1.router` ⇄ `interfaces.api.v1.ws`.

Per `check_coupling.py`'s own message: "an import cycle means these modules cannot be understood,
tested or extracted independently. Break it by moving the shared contract down, not by deferring
an import inside a function." None of these 4 cycles were introduced by TECH-001 SF-04 or any
other work in this session — confirmed via `git stash` (identical `check_coupling` output with
SF-04's changes present or absent).

## Candidate Approaches (not yet designed)

- For each cycle, identify which direction is "wrong" (analogous to TECH-001 SF-04's own
  circular-dependency work) and extract the shared contract into a lower, leaf-level module both
  sides can depend on without depending on each other.
- Cycle 2 (the `core.flow.engine`/`handlers` one) should be sequenced *with* `TECH-020`/`TECH-015`
  rather than independently, since a structural split of `runner.py`/`runner_utils.py` will very
  likely also be the fix for this cycle — doing them separately risks two overlapping refactors
  of the same files.
- Add `check_coupling.py --cycles-only` (or equivalent) as a standing zero-tolerance gate once
  all 4 are cleared, so a 5th cannot silently regrow — it already runs at `cb`, this is about
  making a *clean* baseline meaningful rather than a chronically-red one.

## Non-Goals (proposed, pending design)

- Not a rewrite of any cycle member's business logic — import-direction restructuring only.
- Cycle 2's file-size/complexity work stays `TECH-020`'s and `TECH-015`'s; this ticket owns only
  the import-cycle defect itself.

## Next Step

Run through `specweaver-design` once `TECH-020`/`TECH-015`'s sequencing is clearer, so Cycle 2's
fix isn't designed twice.


## Re-verified 2026-08-08

All **4 cycles still present and unchanged**. Worth knowing because TECH-006 SF-02 rewrote call
sites in five of the six modules in the largest cycle (`runner`, `runner_utils`, `staleness`,
`decompose`, `dual_pipeline`) without moving the number — the cycle is structural, not incidental
to how those files were being used.

```
python scripts/check_coupling.py --cycles-only
```

### Three of the four are self-contained; one is not

* `assurance.validation.registry` / `rules.code.register` / `rules.spec.register` (3) — isolated.
* `infrastructure.llm.adapters._rate_limit` / `factory` (2) — isolated, and the smallest. Good
  first target.
* `interfaces.api.app` / `ui.htmx` / `v1.pipelines` / `v1.router` / `v1.ws` (5) — isolated to the
  API layer.
* `core.flow.engine.runner` / `runner_utils` / `staleness` / `handlers.decompose` /
  `handlers.dual_pipeline` / `handlers.registry` (6) — **overlaps TECH-015 and TECH-020**, both
  still 🔴. This ticket owns only the import-direction defect, not the restructuring those two
  tickets plan for the same files. Take the other three cycles first; this one wants coordinating.

### The one thing not to do

The gate's own message says it: break a cycle by moving the shared contract down, **not** by
deferring an import inside a function. A function-local import silences the checker while leaving
the modules just as entangled, and it is the fix that will look tempting for the 6-module cycle.
