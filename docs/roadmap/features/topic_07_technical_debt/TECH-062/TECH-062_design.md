# Design: Parallel Fan-Out Has No Collision Guards

- **Feature ID**: TECH-062
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-19
- **Origin**: found 2026-08-17 by `INT-US-18-MIG`/`INT-US-19-MIG` while citing `C-FLOW-03`'s FRs

## Problem Statement

`C-FLOW-03` (Multi-Spec Pipeline Fan-Out) is `✅`. Two of its six declared FRs describe mechanisms
that **do not exist in the source**:

| `C-FLOW-03` requirement | Claim | Reality |
|---|---|---|
| `C-FLOW-03 FR-3` | *Dynamic Port Offset Injection* — "Injects a unique `SW_PORT_OFFSET` hash into the environment of a sandbox worktree" so "testing instances and mock servers do not collide on network ports or SQLite database locks" | `SW_PORT_OFFSET` appears **nowhere** in `src/**/*.py`. No port-offset mechanism of any name exists |
| `C-FLOW-03 FR-4` | *Serialized Worktree Context Prep* — "Pauses background GC (`gc.auto 0`) and sequentially creates `.worktree` directories and unique branches per component" to avoid "fatal Git locking collisions natively experienced when spawning parallel Git worktree tasks" | No `gc.auto` configuration anywhere. Worktree creation is not serialised |

**The hazards are real, not theoretical.** `run_fan_out` is genuinely concurrent — `asyncio.gather`
over one sub-runner per component (`core/flow/engine/fan_out.py:60-62`) — and each sub-run can take
the per-step isolation path that calls `git worktree add`. So parallel git-lock contention and port
collisions between concurrent test instances are exactly the conditions FR-3 and FR-4 were written
for, and nothing guards them.

**Why no gate caught it.** Both FRs were uncited, and an uncited FR is invisible to
`check_fr_sweep.py` only in aggregate — the specific claim is never compared against code. This is
the shape `TECH-038` recorded for `INT-US-21-SUB` (a registry entry advertising behaviour that was
never built, surviving delivery *and* an epic closure) and `TECH-046` for `C-INTL-01` (designed
multi-level, shipped single-pass, no descope recorded).

Found only because `ADR-004`'s migration required citing every FR with a killed mutant. There is no
mutant to kill for code that does not exist.

## Decision

Follow `TECH-046`'s precedent exactly: **delete the two FR rows from `C-FLOW-03`'s design so the
descope is visible**, and carry the real work here rather than leaving a `✅` that advertises it.

`C-FLOW-03` keeps FR-1, FR-2, FR-5 and FR-6, all four cited and mutant-verified.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Concurrent fan-out over real worktrees is exercised | the integration tier | creates 16 worktrees concurrently against a real repository, then asks git what exists | the concurrency claim is under test at last, and a change that breaks it fails rather than going unnoticed as the deleted FRs did |

## What the measurement said

The filing's own instruction was *"measure before choosing"* and *"a reproduction is the first task"*.
Both hazards were measured, and neither is present:

**FR-4's git contention does not reproduce.** 32 concurrent `worktree_add` calls against a real
repository on **git 2.53.0** produced 32 worktrees and zero failures. Git takes its own lock around
the worktree administrative area, so the serialisation FR-4 described would be a second lock over one
that already works — and `gc.auto 0` would address a contention source that is not the one.

**FR-3's port collisions cannot occur.** Nothing in `core/flow/` allocates, injects or reads a port.
The FR described a guard for a mechanism this codebase does not have.

So none of the three candidate approaches was implemented, and that is the finding rather than a gap.
Building the lock anyway would have shipped a mechanism with no failure to point at — which is how
FR-3 and FR-4 came to exist in the first place.

## What was delivered

**The descope is visible.** FR-3 and FR-4 were deleted from `C-FLOW-03`'s design on 2026-08-17, which
that design records; the capability keeps FR-1, FR-2, FR-5 and FR-6, all cited and mutant-verified.

**The missing test now exists.** No test in this repo ran a concurrent fan-out over real worktrees,
which is precisely why a claim about concurrency survived delivery uncontested. It does now, and it
asserts what git knows rather than what the calls returned: a mutant that reports SUCCESS and creates
nothing fails two of its three tests.

## What is knowingly not covered

**A git version that does contend.** The measurement is of git 2.53.0, and the guard would fail
loudly on a version that behaves differently — which is the right outcome, and better than a lock
protecting against a hazard nobody has seen.

## Verifiable Proof

| FR | Test |
|---|---|
| FR-1 | `tests/integration/core/flow/engine/test_concurrent_worktree_creation.py` — 16-way concurrency, the directories on disk, and `git worktree list`. Making `worktree_add` report success without creating anything fails 2 of 3 |

## Candidate Approaches (as filed)

1. **Reuse the reservation table.** FR-2's `RESERVE` gate already exists (`engine/reservation.py`,
   `flow_reservations`) and already parks colliding runs. Extending it from modules to *ports* is the
   smallest change and keeps one mechanism.
2. **Serialise worktree creation behind a lock.** An `asyncio.Lock` around the `worktree_add` atom
   call in the sub-run path — cheap, and it addresses FR-4 without touching git config.
3. **`git config gc.auto 0` per worktree**, as FR-4 originally described. Addresses background GC
   specifically, which may not be the actual contention source; needs measurement first.

**Measure before choosing.** No test in this repo currently runs a real concurrent fan-out over real
worktrees, so the failure mode is documented rather than observed. A reproduction is the first task.

## Non-Goals

- `C-EXEC-04` (Concurrent Git Merge Orchestration), unbuilt, which owns merge-time coordination.
  This ticket is about *setup* collisions, not merge.
- `A-EXEC-04` (Advanced Row-Level Task Locking), unbuilt, which owns pessimistic locking in the task
  ledger.
- Broadening `C-FLOW-03`'s scope. Its four surviving FRs are proven; this is the descoped remainder.

## Next Step

Run `specweaver-design`, starting from a reproduction: a fan-out over two components that each create
a worktree, asserting git-lock contention or its absence. Without that, approach 3 is a guess.
