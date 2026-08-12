# Design: Retire Grab-Bag Modules (Name-Says-Nothing Refactor)

- **Feature ID**: TECH-015
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-12 — see §Delivery. Three of four modules split; the fourth
  is an explicit scope correction, not an omission.
- **Origin**: User mandate during INT-US-21 SF-01 CB-4 (2026-07-25).

## Problem Statement

A module whose name promises nothing cannot be contradicted, so it accretes. Every author with
something that "sort of belongs near the runner" reaches for `runner_utils`. The mechanism is
observable rather than theoretical: INT-US-21 CB-4 added `try_staleness_bypass` to
`runner_utils.py` for exactly that reason, and relocated it to `engine/staleness.py` in the same
commit boundary once it was called out.

The fix is to split each offender into modules named for their **contract**, so the next addition
has something to violate.

## In Scope (4 modules, measured 2026-07-25)

| Module | Lines | Unrelated concerns |
|---|---|---|
| `core/flow/engine/runner_utils.py` | 413 | **9** |
| `core/flow/handlers/base.py` | 250 | 5 |
| `workspace/project/_helpers.py` | 172 | 3 |
| `interfaces/cli/_core.py` | 88 | 3 |

### 1. `core/flow/engine/runner_utils.py`

Nine concerns: isolation policy (`resolve_should_isolate`, `apply_session_policy`,
`_dal_requires_isolation`, `_derive_allowed_paths`), sandboxed execution (`execute_in_sandbox`,
`setup_sandbox_caches`), session-worktree lifecycle (`execute_run`), fan-out (`run_fan_out`), the
event protocol (`RunnerEventCallback`), vault security (`verify_vault_security`), telemetry
(`flush_telemetry`), time formatting (`_now_iso`).

Proposed targets: `isolation.py`, `session.py`, `fan_out.py`, `events.py`, `security.py`,
`telemetry.py`. **32 references across 8 files.**
`tests/unit/core/flow/engine/test_runner_utils.py` splits the same way — a test file named after a
grab-bag inherits the problem.

### 2. `core/flow/handlers/base.py`

**Do NOT rename this one — move the non-base members out.** `StepHandler` (a Protocol) legitimately
belongs in a `base`; `RunContext`, `_now_iso`, `_error_result` and `_build_base_prompt` do not.

`_now_iso` has **119 call sites**, most importing it from here rather than from `runner_utils`.
Relocating it to the L0 `commons` leaf is architecturally right but has the widest blast radius of
anything in this ticket, so it should be **its own step**.

> Coordinate with **`TECH-006`**, whose Finding 3 (RunContext god object) targets this same file.
> Do not let the two collide.

### 3. `workspace/project/_helpers.py`

Three concerns: constitution discovery/loading (`ConstitutionInfo`, `load_constitution`), directory
traversal (`walk_up_dirs`), markdown table rendering (`build_tech_stack_rows`,
`build_standards_section`).

### 4. `interfaces/cli/_core.py`

Three concerns: repo-op wrapper (`run_repo_op`), active-project guard (`_require_active_project`),
version callback (`_version_callback`).

## Explicitly OUT of Scope

These are legitimate single-ABC homes where `base` **is** the contract; renaming them would be pure
churn:

- `workspace/ast/parsers/base.py` — `BaseTreeSitterParser`
- `infrastructure/llm/adapters/base.py` — `LLMAdapter`
- `sandbox/base.py` — `AtomStatus` / `AtomResult` / `Atom` / `BaseTool`, one cohesive abstract kernel

## Guardrail to Ship With the Fix

A standards rule rejecting **new** module names matching `util(s)` / `helper(s)` / `misc` /
`shared` / `common` outside the L0 `specweaver/commons` leaf. Without it the pathology simply
regrows.

## Execution Constraint

Purely mechanical move + rename per module. **Land one module per commit**, full suite green each
time, and do **not** bundle any of it into a feature commit — the diff must stay trivially
reviewable as "moved, not changed".

## Delivery, 2026-08-12

### The thesis was confirmed on the ticket's own example, while it waited

`runner_utils.py` grew **413 → 469 lines** between this ticket being filed and being worked. One of
those accretions was added by the agent working `TECH-014`, who put a helper there precisely
because `runner.py` had no headroom. The ticket predicted the mechanism and then the mechanism ran
on the ticket.

### The guardrail landed first, not last

**R7** in `check_conventions.py`: a module name states a contract, not a location — no `util(s)`,
`helper(s)`, `misc`, `shared` or `common(s)` segment outside the L0 `specweaver/commons` leaf.

A census against a frozen baseline like R6, because rejecting outright would have blocked every
commit until the whole refactor landed. Matched as whole `_`-delimited segments so `runner_utils`
is caught and `commonmark` is not; `commons` is exempt **by path**, so a stray `commons.py`
elsewhere is still rejected. Verified by planting an offender and watching it fire, not by reading
the regex. Ratchet went **9 → 6** across this work.

### What was split

| Was | Became |
|---|---|
| `engine/runner_utils.py` (469 lines, 9 concerns) | `isolation`, `session`, `sandboxed_execution`, `fan_out`, `events`, `telemetry`, `security`, + `commons/timestamps` |
| `workspace/project/_helpers.py` (172, 3) | `constitution_loading`, `directory_walk`, `standards_rendering` |
| `handlers/base.py` (334, 5) | `run_context` (240) + `prompting` + `results`; **`base.py` is now 69 lines holding the Protocol** |

`session.py` and `sandboxed_execution.py` are the pair the old file made easy to confuse: one
worktree per *run* versus one per *step*, mutually exclusive at runtime, sharing a file that named
neither.

`RunContext`'s move rewrote **115 importers**. That was put to the user as a decision rather than
swept in, since the ticket already flags a 20-importer symbol as needing its own step.

### `_now_iso` was worse than recorded

The ticket knew of two definitions. There were **six**, all the identical
`datetime.now(UTC).isoformat()`. Two are now gone — the flow engine's copy moved to the L0 commons
leaf where the ticket says it belongs, and `handlers/base` delegates there instead of redefining
it, which removed a duplicate **without touching a single importer**. Four remain
(`engine/store`, `core/config/database`, `workspace/store`, `graph/lineage/store`), each with its
own local callers; consolidating those is not this ticket's business.

### `interfaces/cli/_core.py` — scope correction, not an omission

**Decided with the user: leave it.** The ticket lists it as the fourth module, but `_core` names a
real contract — the CLI's composition root, holding `app`, `console`, `get_db` and `logger`. Its
docstring documents a deliberate design: everything imports it **as a module** so
`monkeypatch.setattr("...cli._core.get_db", ...)` resolves, and roughly eight test files depend on
that. R7 does not flag the name either. Splitting it would risk a documented test contract to move
three small functions, which is churn rather than structure — the same reasoning the ticket already
applies to the `base.py` files it puts out of scope.

### Execution

One module per commit, as required, and no feature work bundled in. **6448 tests pass untouched**
at every boundary, with `mypy` and `tach` clean. The only test changes are module-name censuses —
`test_logging_rollout`'s logger list, an e2e's patch target, and `test_check_class_health`'s two
hardcoded paths — all of which must move when modules do.

The sweep broke four things that the gates caught rather than a reviewer: a regex mangled a
parenthesised `# noqa` into invalid syntax; a moved function lost its `_now_iso` import; imports on
their own line became annotation-only and tripped `TC001`; and a `TYPE_CHECKING` import was
duplicated into both halves of a split, which the suppressions ratchet flagged.

## Next Step

Done. Four `_now_iso` duplicates remain repo-wide, recorded above rather than ticketed — they are
independent one-liners with local callers, not a grab-bag.
