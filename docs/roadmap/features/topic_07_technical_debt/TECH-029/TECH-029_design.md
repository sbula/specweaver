# Design: Sandbox Process Cap Uses `RLIMIT_NPROC`, Which Bounds the User and Not the Sandbox

- **Feature ID**: TECH-029
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found 2026-08-12 diagnosing 29 test failures after the move from Windows to Linux.
  Full analysis: `docs/analysis/linux_test_failures_2026-08-12.md`. This defect alone accounts for
  **18 of the 29**.

## Problem Statement

`sandbox/execution/core/atom.py:24` applies a process cap to every bash step:

```python
_DEFAULT_RESOURCE_LIMITS = ResourceLimits(
    max_memory_bytes=2_147_483_648,  # 2 GiB, FR-11
    max_processes=128,
)
```

`platform_limiter.py`'s Unix limiter maps `max_processes` to
`setrlimit(RLIMIT_NPROC, (128, 128))` inside a `preexec_fn`, and `executor.py:156` applies that
`preexec_fn` only when `sys.platform != "win32"`.

**`RLIMIT_NPROC` is a per-real-UID, system-wide limit.** It caps every process the invoking user
owns — their editor, their shell, the pytest workers, everything — not the processes this sandbox
spawns. So the field does not bound what it exists to bound, and it fails whenever the user happens
to be running other things.

The Windows path maps the same field to a Job Object, where "max processes" genuinely means
*processes in this job*. **The two platforms implement different constraints under one name, and
only the Linux one is wrong.**

### Reproduced

```
bash gen.sh                                  rc=0
bash gen.sh   under AS=2GiB + NPROC=128      rc=254
              gen.sh: fork: retry: Resource temporarily unavailable
```

`mkdir -p src` is the script's first fork; `254` is bash's exit after exhausting fork retries.
`RLIMIT_AS` alone is harmless — probed separately, `echo ok` succeeds, because a shell builtin never
forks. Only the fork limit bites, which is why a naive probe misses it.

### Measured blast radius

| `max_processes` | integration | e2e | wall clock |
|---|---|---|---|
| `128` (today) | 14 failed | 9 failed | 67s / 39s |
| `None` | **4 failed** | **1 failed** | **12s / 14s** |

The runtime collapse is part of the evidence: bash was spending seconds in fork-retry loops before
giving up.

### Why it never surfaced before

`preexec_fn` is guarded by `sys.platform != "win32"`, so **this code path had never executed** on the
Windows development machine. The Linux move ran it for the first time. Any limit that only exists on
one platform is untested on the other by construction — which is the general lesson here, and worth
carrying beyond this ticket.

### Not a test defect

The 18 failing tests assert that a worktree-isolated run completes and reconciles — exactly what
`C-EXEC-06` promises. They are correct and must not be weakened. The defect is in `src/`.

## Candidate Approaches (not yet designed)

- **A — Stop setting `RLIMIT_NPROC` on Linux; log the limit as unenforced.** `max_processes` keeps
  its Job-Object meaning on Windows and becomes explicitly unenforced on Linux, matching how
  `NoOpLimiter` already reports unsupported platforms. Honest, small, and loses a limit that was
  never working. `RLIMIT_AS` (FR-11's memory bound) is unaffected and stays.
- **B — Raise the number.** Rejected. Does not fix the semantic: still per-user, still breaks on a
  busy machine, still fails to bound the sandbox. It would convert a reproducible failure into an
  intermittent one, which is worse.
- **C — Implement via cgroups v2 `pids.max`.** The only mechanism that delivers the intended
  constraint on Linux. Correct, and much larger: needs a writable cgroup, a delegation story, and a
  degradation path for hosts where neither is available.

**Leaning A now, C as its own story.** A is a small change that stops the system making a promise it
cannot keep on this platform; C is the feature that would let it keep the promise.

## Non-Goals (proposed, pending design)

- **Not** the memory limit. `RLIMIT_AS` at 2 GiB is `FR-11`, works on Linux, and is out of scope.
- **Not** the other 11 Linux failures. Clusters B–E in the analysis document have unrelated causes:
  three unit tests needing a live `GEMINI_API_KEY`, one asserting `RLIMIT_FSIZE` against a pipe,
  three encoding Windows path semantics, and four still open.
- **Not** a container-isolation redesign. `B-EXEC-01`'s container path already bounds processes by
  other means; this ticket is about the host-side `SubprocessExecutor`.
- **Not** a general audit of every platform-conditional branch — though the design should say
  whether one is warranted, since the root lesson is that `sys.platform` guards hide untested code.

## Ownership note

This changes shipped sandbox behaviour and sits in `C-EXEC-02` / `B-EXEC-01` territory. It was
**deliberately not folded into `TECH-025` SF-05**, which is a documentation-and-traceability
sub-feature that happened to be running when this was found. Mixing a live `src/` behaviour change
into a citation commit is exactly the attribution problem `TECH-025` exists to remove.

## Next Step

Run through `specweaver-design`. The change under option A is small; the design work is in three
places:

1. **What `max_processes` means once Linux stops enforcing it.** A field that silently does nothing
   on one platform is its own defect class. Options: rename it to say it is Windows-only, keep it
   and log loudly per call, or leave it unset by default until C lands.
2. **Whether any other limit has the same shape.** `RLIMIT_FSIZE` is set from
   `max_file_size_bytes`, and the analysis found its own test asserting it against a pipe, where it
   cannot apply — so its real behaviour on Linux is also unverified.
3. **Whether the 18 tests need anything beyond the fix.** They should pass unchanged. If any needs
   editing, that is a signal the fix changed more than intended.
