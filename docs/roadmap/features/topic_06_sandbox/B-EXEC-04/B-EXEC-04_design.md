# B-EXEC-04 — Kernel-Enforced Resource Bounds (cgroups v2)

**Status**: STUB — not yet run through the `specweaver-design` skill · **DAL**: B (High-Assurance) ·
**Topic**: 06 — Sandbox / EXEC · **Feature ID**: B-EXEC-04

| | |
|---|---|
| Parent story | US-9 (The Zero-Trust Sandbox) → Sub-Story Add-On *Security Defenses* (`INT-US-09-SF02`) |
| Origin | Split out of `TECH-029` on 2026-08-12 |
| Supersedes | `TECH-029`'s interim `RLIMIT_NPROC` backstop (remove it, do not layer) |
| Must reconcile | `C-EXEC-02 FR-11` · `E-EXEC-01 FR-10` · `B-EXEC-01` NFR-5 |
| Not touched | network egress (`E-EXEC-02`) |

## Problem

`C-EXEC-02 FR-11` promises that *"a runaway or fork-bombing script is capped by default"*. On Windows a
Win32 Job Object bounds **the processes in this job**. On Linux the same field becomes `setrlimit(RLIMIT_NPROC)`:
a **per-real-UID, system-wide** cap counting *tasks* (threads), not processes. It bounds the invoking
**user**, not the sandbox.

Measured 2026-08-12 on an idle developer machine:

```
processes for this UID :  64
TASKS (threads) for UID: 234   <- what RLIMIT_NPROC counts
configured cap         : 128   <- already exceeded before the sandbox forks anything
```

So the Linux cap cannot bound the sandbox, and at the configured value it cannot succeed at all.
`TECH-029` repairs the breakage; it does **not** make the promise true — nothing on the host-side
execution path can without a mechanism scoped to a process subtree.

**cgroups v2 `pids.max` is that mechanism.** It bounds a control group, the sandbox's children live in
it, and the invoking user's other work is untouched.

## The interim backstop — read before starting

Re-measured 2026-08-17. The bound this capability inherits is loose on purpose, which raises its value.

**What ships now.** Headroom is the configured budget **or 1% of the system's own hard
`RLIMIT_NPROC`, whichever is larger**, clamped to that hard limit — measured 3538 against a 325-task
baseline. The system's declared limit is the only scale on the host that is not a guess. A fork bomb is
unbounded and still crosses it in milliseconds, so `C-EXEC-02` FR-11's outcome holds. But the bound is
roughly 8x looser and no longer a per-sandbox quota in any sense: a ceiling set high enough that
ambient load cannot reach it.

**Replaced: `RLIMIT_NPROC = current task count + budget`** (`TECH-029`'s first form), because the
ceiling is **fixed for the child's whole lifetime at the moment it spawns** — it must clear the
machine's *future* peak, which no sample can know. Sampling the UID's task count while this repo's
suite ran at `-n auto`:

```
range within one run : 313 .. 960 tasks   (spread 647)
p50 / p95            : 419 / 484
budget               : 128  ->  ceiling ~453
```

The ceiling (453) sat **below** routine load. Sandboxed bash steps died on their own `fork` with
`Resource temporarily unavailable`, exit 254, roughly one suite run in six, reported against the
innocent script (`BashActionAtom` put only the exit code in its message). With the cap disabled:
**0 failures in 12 runs**.

Two sampling repairs were measured and failed for the same reason: a process-lifetime high-water mark
(a child spawned before the peak carries the lower ceiling), then high-water mark plus observed spread.
**Do not spend time on a third sampling scheme.**

Kernel-enforced per-subtree bounding is the only thing that makes `max_processes` mean what its name
says. **This capability supersedes the backstop and should remove it** — two mechanisms claiming the
same guarantee is how the original defect survived unnoticed.

## Candidate approaches (not yet designed)

- **Place the child in a delegated cgroup** and write `pids.max`, alongside the existing `preexec_fn`.
  Needs a writable cgroup: under systemd a delegated user slice; in CI and in containers the picture
  differs and must be established per environment, not assumed.
- **Degrade explicitly, never silently.** With no writable cgroup the executor must say the bound is
  unenforced — the `NoOpLimiter` pattern. A limit that quietly does nothing on one platform is worse
  than no limit, because it is believed (`TECH-029`).
- **Extend to memory** (`memory.max`) instead of `RLIMIT_AS`, if the same subtree-versus-process
  mismatch shows there. `RLIMIT_AS` works, so this is an improvement, not a repair — maybe a later
  increment.
- **Reconcile with `B-EXEC-01`.** The container path already bounds processes by other means. The
  design must say which mechanism applies when a step runs containerized, so both do not claim the
  limit.
- **Reconcile with `E-EXEC-01` FR-10** — *"memory/process-count bombs are caught and killed on all
  platforms"*. A **second delivered claim** on the same bound, and where the Unix limiter lives, so its
  meaning changes when a cgroup exists. Counting `C-EXEC-02` FR-11, `E-EXEC-01` FR-10 and `B-EXEC-01`
  NFR-5, **three delivered requirements already claim a process bound** — the ambiguity is the current
  state.

## Non-Goals (proposed, pending design)

- **Not** cgroups v1. v2 unified hierarchy only; hosts without it degrade explicitly.
- **Not** the memory limit's repair — `RLIMIT_AS` works today.
- **Not** `TECH-029`'s interim fix, which lands first and independently.
- **Not** network egress control, which is `E-EXEC-02` in the same sub-story.

## Open questions for design

Settle these in `specweaver-design` before writing FRs:

1. **Where the cgroup comes from** in each supported environment — developer host under systemd, CI
   runner, inside `B-EXEC-01`'s container. Decides whether the capability is usable or usually
   degraded, and so whether it earns its DAL-B placement.
2. **What `max_processes` means once two mechanisms exist.** `TECH-029` made it a best-effort
   backstop; this makes it a real bound where a cgroup exists. One field, two guarantees, is the
   ambiguity that produced the original defect.
3. **How `C-EXEC-02 FR-11` and `E-EXEC-01 FR-10` read afterwards.** Both were amended to state what is
   enforced; this capability lets either state something stronger. Amend them together or the
   ambiguity moves.
