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

## Relationship to `TECH-029` — read this before starting

`TECH-029` ships an interim backstop: `RLIMIT_NPROC` set to *current task count + budget*, so it
bounds the sandbox's **additional** forks rather than the user's total. That keeps `FR-11`
approximately true and stops the breakage, but it is racy (another process may start between
measurement and `setrlimit`) and still per-UID.

**This capability supersedes it.** The design should **remove** `TECH-029`'s workaround rather than
layer on top of it — two mechanisms claiming the same guarantee is how the original defect survived
unnoticed for as long as it did.

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
3. **How `C-EXEC-02 FR-11` reads afterwards.** `TECH-029` amends it to state what is actually
   enforced; this capability is what would let it state something stronger.
