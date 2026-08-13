# Design: DAL-Escalated Isolation for Pipeline Runs

- **Feature ID**: C-EXEC-07
- **Epic**: Topic 06 (Sandbox)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Minted 2026-07-24 from `INT-US-24` SF-03 intake — *"would a PO be happy we don't use
  DAL here?"*
- **Created**: 2026-08-13 under `TECH-044`. The capability had no design document, so its topic
  entry was the only record and there was nowhere to redistribute its detail to. Everything below
  is moved verbatim from that entry, not newly authored.

## Problem Statement

The shipped `INT-US-03` `AD-8` escalation (`dal_auto_escalate` in `apply_session_policy`) is wired
on the `sw implement` composition root only. The `sw run` / `sw resume` roots resolve neither, so
any journey that executes generated code — `scenario_integration`, `new_feature` — runs with the
weakest default.

That is an asymmetry in the wrong direction: **the tool's most untrusted execution surface is
LLM-derived scenario tests running over LLM-generated code**, and it is the one with no escalation.

The escalation target is `C-EXEC-06` session isolation, entered at or above the configured
`auto_isolate_min_dal` threshold — so this extends *where* that existing rule is evaluated, not
what it decides.

## Why this is capability work, not a one-line flip

`_derive_allowed_paths` is implement-shaped — `[src/{stem}.py, tests/test_{stem}.py]`. Under session
isolation the scenario chain's artifacts (`contracts/`, `scenarios/definitions/`,
`scenarios/generated/`) fall outside that list and would be **silently dropped by the reconcile
authorization gate**. So the capability owns three things:

- **pipeline-aware allow-list derivation** — the hard part;
- **dual-fan-out-in-one-worktree semantics**;
- a proof that includes a real `scenario_integration` run.

## DAL

DAL-C, for the same reason as `C-EXEC-06`: it widens what the single reconcile gate authorizes.

## Decision record

Supersedes `AD-8`'s per-caller opt-out via a **new recorded decision**. `INT-US-03`'s finished
documents remain untouched — finished-stories-immutable.

## Integration

Integrated by `INT-US-09-SF06`.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
