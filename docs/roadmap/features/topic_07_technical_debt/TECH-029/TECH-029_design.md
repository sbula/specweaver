# Design: Sandbox Process Cap Uses `RLIMIT_NPROC`, Which Bounds the User and Not the Sandbox

- **Feature ID**: TECH-029
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED (2026-08-12)
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

### The limit is not merely over-broad — it can never succeed on Linux (measured 2026-08-12)

`RLIMIT_NPROC` counts **tasks**, i.e. threads, not processes. Measured on this idle machine:

```
processes for this UID :  64
TASKS (threads) for UID: 234   <- what RLIMIT_NPROC actually counts
system default (ulimit -u): 321342
```

The UID sits at **234 tasks at idle — 83% above the 128 cap before the sandbox forks anything.**
So the limit is already exceeded at the moment it is applied, and every bash step fails regardless
of load. This is not "breaks on a busy machine"; it is "never works".

Confirmed against ordinary work — 40 *sequential* `/bin/true` calls, a workload no sandbox budget
would object to:

```
no limit      rc=0    0.02s   done
NPROC=128     rc=254  15.00s  fork: retry: Resource temporarily unavailable
NPROC=4096    rc=0    0.03s   done
```

The 15 seconds are bash retrying the fork before giving up, which is where the suite's wall-clock
went.

### The conflict this creates with a delivered story

`C-EXEC-02 FR-11` specifies these defaults and its acceptance criterion reads:

> *A runaway or fork-bombing script is capped by default; pipeline authors may tune within a
> bounded range but **MAY NOT disable limits entirely**.*

`E-EXEC-01 FR-10` owns the mechanism: *"Unix/macOS: `resource.setrlimit()` via `preexec_fn`.
Windows: Win32 Job Objects."*

**So option A — stop setting `RLIMIT_NPROC` — contradicts a delivered FR in its letter**, even
though the limit it removes has never once worked on this platform. That conflict is the decision
this ticket exists to make, and it must be made explicitly rather than by quietly deleting a line.

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

---

## Delivery (2026-08-12)

> [!NOTE]
> **Process, recorded rather than implied.** This ticket did not run `specweaver-design` to
> completion. Its Phase 3 gate surfaced a gap — the leaning recommendation contradicted a delivered
> FR — the options were discussed with the user, and the decisions below were taken directly. The
> measured evidence above *is* the research; what was skipped is the FR/NFR table and a
> sub-feature breakdown, which a single-change fix would not have used.

### Decisions taken (user, 2026-08-12)

| # | Decision |
|---|---|
| 1 | **Option D**, not A. A would have contradicted `C-EXEC-02 FR-11`'s *"MAY NOT disable limits entirely"* |
| 2 | **Budget stays 128.** The semantics change; the configured number does not |
| 3 | **Amend `C-EXEC-02 FR-11`** to state what is actually enforced |
| 4 | **`B-EXEC-04`** minted for cgroups v2 — a capability at DAL-B under US-9, not a TECH ticket, because it delivers something never built rather than repairing something broken |

### What changed

- `platform_limiter.py`: new `current_task_count()` reading `/proc`, and the cap computed as
  **baseline + budget** in the **parent** — not in `preexec_fn`, which runs after fork where only
  async-signal-safe work is sound and walking `/proc` is neither safe nor cheap.
- No task count available (macOS, restricted `/proc`) → the process cap is **not set** and a warning
  says so. Memory and file-size bounds still apply. Guessing a number would be a limit that does not
  limit.
- `C-EXEC-02 FR-11` amended under a waiver named in the commit.

### Measured outcome

```
                       before        after
tests/integration      578 / 13      588 /  3      68s -> 12.6s
tests/e2e              182 /  9      190 /  1      39s -> 13.8s
tests/unit            5620 /  1     5622 /  1
```

The wall-clock collapse is the fork-retry loops disappearing.

**Acceptance, probed directly rather than inferred from the suite:**

```
ordinary work (40 sequential forks)   rc=0    0.04s   <- was rc=254 after 15s
fork storm    (400 concurrent procs)  rc=254  5.02s   <- still capped, FR-11 holds
```

### One test changed, and why that is not weakening it

`test_process_limit_unix` asserted the literal `"50"` appeared in the child's `RLIMIT_NPROC`. That
assertion is what let the defect survive: the raw budget is not a reachable ceiling, so pinning it
pinned the bug. It now asserts the cap **exceeds the baseline by the budget** — relative, which is
the actual contract. The other 17 tests fixed here were not touched.

### What remains with `B-EXEC-04`

This is a best-effort backstop. The cap still applies to the whole UID and the baseline can drift
between measurement and exec. Only a per-subtree mechanism makes `FR-11` true without qualification.

## Carried down from the topic entry (2026-08-13, `TECH-044`)

Moved here verbatim when the entry was shortened to four lines — recorded rather than dropped.

- Measured: `max_processes=None` takes integration 14→4 failures and e2e 9→1, wall clock 67s→12s and 39s→14s.
