# C-EXEC-07 — DAL-Escalated Isolation for Pipeline Runs

**Status**: STUB — not yet run through the `specweaver-design` skill. Run it before any
implementation. · **DAL**: C · **Epic**: Topic 06 (Sandbox) · **Feature ID**: C-EXEC-07

| | |
|---|---|
| Extends | `INT-US-03` `AD-8` escalation (`dal_auto_escalate` in `apply_session_policy`) to the `sw run` / `sw resume` roots |
| Escalates to | `C-EXEC-06` session isolation, at or above `auto_isolate_min_dal` |
| Integrated by | `INT-US-09-SF06` |
| Supersedes | `AD-8`'s per-caller opt-out, via a **new recorded decision**. `INT-US-03`'s finished documents stay untouched — finished-stories-immutable |

Origin: minted 2026-07-24 from `INT-US-24` SF-03 intake — *"would a PO be happy we don't use DAL
here?"*. File created 2026-08-13 under `TECH-044`: the capability had no design document, so its
topic entry was the only record; everything here is moved verbatim from that entry.

## What it does

Evaluates the existing DAL escalation rule on `sw run` / `sw resume` too, not only on `sw implement`.
Same rule, same target (`C-EXEC-06` session isolation at or above `auto_isolate_min_dal`) — it
extends *where* the rule is evaluated, not what it decides.

## Why

Today only the `sw implement` composition root resolves the escalation. Journeys that execute
generated code under `sw run` — `scenario_integration`, `new_feature` — run with the weakest default.
That is backwards: **LLM-derived scenario tests running over LLM-generated code** are the most
untrusted execution surface, and the only one with no escalation.

DAL-C, as for `C-EXEC-06`: it widens what the single reconcile gate authorizes.

## Why this is not a one-line flip

`_derive_allowed_paths` is implement-shaped — `[src/{stem}.py, tests/test_{stem}.py]`. Under session
isolation the scenario chain's artifacts (`contracts/`, `scenarios/definitions/`,
`scenarios/generated/`) fall outside it and would be **silently dropped by the reconcile
authorization gate**. The capability owns:

- **pipeline-aware allow-list derivation** — the hard part;
- **dual-fan-out-in-one-worktree semantics**;
- a proof that includes a real `scenario_integration` run.
