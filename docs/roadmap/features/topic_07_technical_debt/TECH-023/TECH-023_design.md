# Design: Repo-Wide Cyclomatic Complexity Violations (complexipy)

- **Feature ID**: TECH-023
- **Epic**: Topic 07 (Technical Debt)
- **Status**: PARTIAL 2026-08-12 — the mechanism is delivered and the gate is green; **41 of 97
  violations remain frozen** (was 93 when the ratchet shipped). See §Delivery. This stays open as
  the reduction work.
- **Origin**: Found while running `python scripts/quality.py cb` for TECH-001 SF-04
  (2026-08-02) — confirmed via `git stash` to be chronic and unrelated to that commit
  (identical failure list with or without SF-04's changes applied).

## Problem Statement

`complexipy` (cyclomatic complexity, threshold 15) currently fails for **98 functions across 68
files** — reproducible via:
```
complexipy src --failed --max-complexity-allowed 15
```
This spans nearly every domain in the codebase (graph, standards analyzers, validation rules,
core.config, core.flow handlers, LLM adapters, sandbox executors, AST parsers, workflows
interfaces) — it is not localized to any one recent feature or refactor.

Two of the 98 are already the explicit, in-progress scope of other TECH tickets and are **out of
scope here**, tracked there instead:
- `PipelineRunner::_execute_loop` (52) — `TECH-020`'s exact target (`core/flow/engine/runner.py`).
- `RunContext::model_post_init` (17) — `TECH-006` SF-02's exact target
  (`core/flow/handlers/base.py`).

Worst offenders among the remaining 96 (severity ordering, not exhaustive — see the reproduction
command above for the full list):
- `OrchestrateComponentsHandler::execute` (79) — `core/flow/handlers/decompose.py`
- `drift_check_rot` (51) — `assurance/validation/interfaces/cli_drift.py`
- `find_by_glob` (49) — `sandbox/filesystem/core/search.py`
- `DependencyHasher::_hash_directory` (36) — `assurance/graph/hasher.py`
- `load_evaluator_schemas` (36) — `workflows/evaluators/loader.py`
- `tree_command` (34) — `graph/interfaces/cli.py`

Per this project's pre-commit skill: "no inherited problems are acceptable" — but 98 functions
across 68 unrelated files is not a mechanical fix incidental to any one commit; it needs its own
scoped effort(s), not to be absorbed into whichever commit happens to touch the gate next.

## Candidate Approaches (not yet designed)

- Triage by severity and domain into batches (e.g. one PR per bounded context), rather than one
  mega-refactor — matches this registry's own "own commits, never bundled" convention used
  elsewhere (TECH-015, TECH-016, TECH-020).
- For each function: extract sub-steps into named collaborators (the same pattern TECH-020
  proposes for `_execute_loop`), not just complexity-suppression comments.
- Decide whether any legitimately-irreducible functions (e.g. a large dispatch table) warrant a
  documented, reviewed exception rather than forced splitting — and if so, through what
  mechanism (this registry has no per-function complexity-baseline/allowlist today, unlike
  `check_suppressions.py`'s ratchet for `noqa`/`type: ignore`).

## Non-Goals (proposed, pending design)

- Not a rewrite of any single module's behavior — structural extraction only, zero behavior
  change, matching this registry's standard NFR for refactor-classified tickets.
- Does not include `TECH-020`'s or `TECH-006` SF-02's already-owned functions (see above).

## Next Step

Run through `specweaver-design` to decide the triage/batching strategy and produce implementation
plan(s).


## Re-verified 2026-08-08

Count is now **97 functions**, not 98. The one that went is `RunContext::model_post_init`, which
this ticket had explicitly excluded as TECH-006 SF-02's target; that work landed and split it into
three named methods. The exclusion can be dropped from the entry — nothing else about the list
changed, which is further evidence the debt is chronic rather than drifting.

Reproduce with the project venv, not a bare `python` (the system interpreter has no `pytest-xdist`
and differs in other ways):

```
.venv/Scripts/complexipy src --max-complexity-allowed 15    # Windows
python scripts/quality.py cb                                # what the commit gate actually runs
```

### Before starting, decide the split

97 functions across ~68 files is far too large for one sub-feature and spans nearly every domain.
It needs decomposing before any code is written — most likely by domain (assurance/standards,
workspace/ast, sandbox/filesystem, interfaces) rather than by severity, so each sub-feature stays
inside one bounded context and one reviewer's head.

### Sequencing hazards

* `PipelineRunner::_execute_loop` belongs to **TECH-020** and is excluded here. TECH-020 is still
  🔴. If TECH-020 runs first the count drops again; if this ticket runs first, do not touch that
  function.
* Extracting helpers to reduce complexity **changes imports**, which is exactly what **TECH-024**
  measures. Running both at once in one working tree will make it hard to tell which change moved
  which number. Do TECH-024 first (it is far smaller) or keep them in separate sessions.
* `docs/dev_guides/` may describe functions this ticket splits. Check before finishing.

## Delivery, 2026-08-12

### The mechanism first, because the gate was the real problem

`complexipy` had failed the commit gate continuously since 2026-08-02. A gate that is always red
is one nobody reads — and nothing stopped a 98th violation appearing, which is the part that
actually matters.

`scripts/check_complexity.py` runs the same tool at the same threshold and compares against a
frozen per-function baseline. **A new violation blocks the commit that introduces it, and so does
an increase on a function already frozen.** Neither was true before. Same shape as
`check_suppressions`, R6 and R7: frozen baseline, regression check, explicit `--update-baseline`
whose diff is reviewed.

It answers this ticket's open question — *"through what mechanism"* — and answers it as a
**ratchet, not an allowlist**. There are no permanent exemptions: every entry is debt with a number
attached, and the number can only fall. Improvements are reported but never auto-applied, so the
baseline cannot silently drift above reality.

Verified by planting both regression kinds rather than by reading the code: a new 24-complexity
function, and an increase on an already-frozen one (17 → 21). Both exit 1; a clean tree exits 0.

**`quality.py cb` now reports 0 failed of 12 for the first time.** `TECH-024` took the `cycles`
gate green; this took the last one.

### The `>=40` group, cleared

| Function | Was | Now |
|---|---|---|
| `OrchestrateComponentsHandler::execute` | **79** | resolved — no function in `decompose.py` is over 15 |
| `drift_check_rot` | 51 | resolved |
| `find_by_glob` | 49 | resolved |
| `_extract_signatures` | 40 | resolved |

**None needed a behaviour change**, and every `# noqa: C901` in the touched files was deleted
rather than relocated.

Two things worth carrying into the remaining 93:

- **Extraction alone is often not enough.** `find_by_glob` went 49 → 21 by extracting its per-entry
  work, and only cleared the threshold once the nested walk became a generator. The `break`-then-
  `if truncated: break` dance *was* the complexity.
- **A large share of the cost is failure reporting, not logic.** `OrchestrateComponentsHandler`
  had seven early `return StepResult(FAILED, ...)` sites, each a branch. Collapsing them behind a
  private refusal exception — converted back to the identical `StepResult` — did most of the work.

### Six reduction batches, 2026-08-12 — 93 → 41

Reduced by **package cluster** rather than by score, on the finding that the violations were not 93
independent functions. Each batch was its own commit, full suite green, baseline re-frozen with the
diff reviewed.

| Batch | Cluster | Cleared | What was actually shared |
|---|---|---|---|
| 1–2 | `workspace/ast/parsers` | 20 | Query/walk/edit mechanics repeated across ten parsers — this is what grew into `TECH-034` |
| 3 | `core/flow/engine` + handlers | ~14 | The step-execution loop (`TECH-020`), plus prompting/results/context helpers |
| 4 | `workspace/project`, `sandbox/language` | ~11 | Constitution loading, directory walking, SARIF report parsing (two runners, one parser) |
| 5 | `core/config` | 5 | One up-tree walk under three resolvers (`_context_walk.resolve_up_tree`) |
| 6 | `assurance/standards` analyzers | 4 | One documentation-coverage banding under two analyzers (`_documentation.py`) |

**The recurring finding: a cluster of violations is usually one duplicated mechanism, not N
complicated functions.** Nine of the last two batches' functions were cleared by naming the shared
thing once — no function was split for the sake of the number.

Two hazards this work hit, worth knowing before continuing:

- **Moving a function to a new file reads as a new violation to the ratchet.** The
  `BaseTreeSitterParser` split produced three. Each had to be checked against its old score
  (16→16, 16→16, 19→19) before re-freezing. The ratchet is right to ask; "review the diff" is what
  it is for.
- **Extracting a helper can trade a complexity violation for a suppression.** `_dlx_logger` was
  extracted returning `object`, which needed a `type: ignore[attr-defined]` to call `.error` on it.
  The suppressions ratchet caught the +1 at the commit gate. The fix was the honest return type,
  not a re-freeze.

### What remains

**41 frozen violations: 11 in the 25–39 band, 9 at 20–24, 21 at 16–19. Nothing at 40+.** The
largest concentration is **`core/flow` (12)** — handover persistence, resume, and four handler
`execute` methods. After that: `assurance/validation` (5), `assurance/standards` (3, all outside
the analyzers), `sandbox/filesystem` (3).

The remainder is a genuine long tail — 22 packages hold one or two each — so the cluster strategy
above is largely spent. Expect the rest to be individual work.

## Next Step

Keep reducing. The gate no longer depends on it — that is the point of the ratchet. Start with
`core/flow`, the one cluster still large enough to pay for a shared abstraction.