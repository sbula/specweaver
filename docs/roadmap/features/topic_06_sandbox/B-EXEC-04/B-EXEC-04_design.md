# Design: Kernel-Enforced Resource Bounds (cgroups v2)

- **Feature ID**: B-EXEC-04
- **DAL**: B (High-Assurance)
- **Topic**: 06 — Sandbox / EXEC
- **Parent Story**: US-9 (The Zero-Trust Sandbox) → Sub-Story Add-On *Security Defenses*
  (`INT-US-09-SF02`)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Split out of `TECH-029` on 2026-08-12. That ticket found that the sandbox's process cap
  is implemented on Linux as `setrlimit(RLIMIT_NPROC)`, which bounds the invoking **user** rather
  than the sandbox. `TECH-029` repairs the breakage; this capability delivers the constraint the
  system has never actually had on Linux.

## Problem Statement

`C-EXEC-02 FR-11` promises that *"a runaway or fork-bombing script is capped by default"*. On
Windows that is delivered by a Win32 Job Object, which genuinely bounds **the processes in this
job**. On Linux the same field becomes `RLIMIT_NPROC`, which is a **per-real-UID, system-wide** cap
counting *tasks* (threads), not processes.

Measured 2026-08-12 on an idle developer machine:

```
processes for this UID :  64
TASKS (threads) for UID: 234   <- what RLIMIT_NPROC counts
configured cap         : 128   <- already exceeded before the sandbox forks anything
```

So the Linux implementation cannot bound the sandbox, and at the configured value it cannot succeed
at all. `TECH-029` makes it stop failing. It does **not** make the promise true — nothing on the
host-side execution path can, without a mechanism that scopes to a process subtree.

**cgroups v2 `pids.max` is that mechanism.** It bounds a control group, the sandbox's children live
in it, and the invoking user's other work is untouched.

## Relationship to the interim backstop — read this before starting

**Re-measured 2026-08-17. The backstop this section originally described no longer exists, and the
replacement is looser — which raises this capability's value rather than lowering it.**

`TECH-029` shipped `RLIMIT_NPROC = current task count + budget`, bounding the sandbox's *additional*
forks rather than the user's total. That description held until 2026-08-17, when the racy-ness it
flagged in one clause turned out to be the dominant behaviour rather than an edge case.

**What the race actually costs, measured.** Sampling the UID's task count while this repo's own suite
ran at `-n auto`:

```
range within one run : 313 .. 960 tasks   (spread 647)
p50 / p95            : 419 / 484
budget               : 128  ->  ceiling ~453
```

The ceiling sat **below** the load the machine routinely reaches. Sandboxed bash steps died on their
own `fork` with `Resource temporarily unavailable`, exit 254, roughly one full suite run in six — and
the failure was reported against the innocent script, because `BashActionAtom` put only the exit code
in its message. Disabling the cap entirely: **0 failures in 12 runs**, which identified it
conclusively.

The reason is not the measurement window. The ceiling is **fixed for the child's whole lifetime at the
moment it spawns**, so it must clear not the load at spawn but the machine's *future* peak — which no
sample can know. Two sampling-based repairs were implemented and measured before this was accepted: a
process-lifetime high-water mark (still failed — a child spawned before the peak arrives carries the
lower ceiling), then high-water mark plus observed spread (still failed, same reason). **Anyone
planning this capability should not spend time on a third sampling scheme.**

**What ships in the interim instead.** Headroom is now the configured budget **or 1% of the system's
own hard `RLIMIT_NPROC`, whichever is larger**, clamped to that hard limit — measured 3538 against a
325-task baseline where the old ceiling was 453. It is chosen because the system's declared limit is
the only scale on the host that is not a guess. A fork bomb is unbounded and still crosses it in
milliseconds, so `C-EXEC-02` FR-11's outcome holds.

**But the bound is now roughly 8x looser, and it is no longer a per-sandbox quota in any sense.** That
is the state this capability inherits: not "a slightly racy approximation" but "a ceiling deliberately
set high enough that ambient load cannot reach it". Kernel-enforced per-subtree bounding is the only
thing that makes `max_processes` mean what its name says.

**This capability supersedes the backstop.** The design should **remove** it rather than layer on top
— two mechanisms claiming the same guarantee is how the original defect survived unnoticed for as long
as it did.

## Candidate Approaches (not yet designed)

- **Place the child in a delegated cgroup** and write `pids.max`, alongside the existing
  `preexec_fn`. Needs a writable cgroup: under systemd that means a delegated user slice; in CI and
  in containers the picture differs and must be established per environment rather than assumed.
- **Degrade explicitly, never silently.** If no writable cgroup is available the executor must say
  the bound is unenforced — the pattern `NoOpLimiter` already uses. The lesson from `TECH-029` is
  that a limit which quietly does nothing on one platform is worse than no limit, because it is
  believed.
- **Extend the same mechanism to memory** (`memory.max`) rather than `RLIMIT_AS`, if the design
  finds the same subtree-versus-process mismatch there. `RLIMIT_AS` does work, so this is an
  improvement rather than a repair, and may belong in a later increment.
- **Reconcile with `B-EXEC-01`.** The container path already bounds processes by other means. The
  design must say which mechanism applies when a step runs containerized, so the two do not both
  claim the limit.
- **Reconcile with `E-EXEC-01` FR-10 as well** — *"memory/process-count bombs are caught and killed on
  all platforms"*. That is a **second delivered claim** on the same bound, and it is where the Unix
  limiter actually lives, so it is the FR whose meaning changes when a cgroup exists. Counting
  `C-EXEC-02` FR-11, `E-EXEC-01` FR-10 and `B-EXEC-01` NFR-5, **three delivered requirements already
  claim a process bound** — the ambiguity this section warns about is not hypothetical, it is the
  current state.

## Non-Goals (proposed, pending design)

- **Not** cgroups v1. v2 unified hierarchy only; hosts without it degrade explicitly.
- **Not** the memory limit's repair — `RLIMIT_AS` works today.
- **Not** `TECH-029`'s interim fix, which lands first and independently.
- **Not** network egress control, which is `E-EXEC-02` in the same sub-story.

## Next Step

Run through `specweaver-design`. Three things to settle before writing FRs:

1. **Where the cgroup comes from** in each environment the project supports — developer host under
   systemd, CI runner, and inside `B-EXEC-01`'s container. This determines whether the capability is
   usable or usually degraded, and therefore whether it is worth its DAL-B placement.
2. **What `max_processes` means once two mechanisms exist.** `TECH-029` will have made it a
   best-effort backstop; this makes it a real bound where a cgroup is available. One field, two
   guarantees, is exactly the ambiguity that produced the original defect.
3. **How `C-EXEC-02 FR-11` and `E-EXEC-01 FR-10` read afterwards.** Both were amended to state what
   is actually enforced; this capability is what would let either state something stronger. Amend them
   together or the ambiguity simply moves.
