# The 29 Linux test failures — root-cause analysis

- **Date**: 2026-08-12
- **Box**: Linux, Python 3.14.4, after the move from the Windows laptop
- **Baselines (verified identical against a stashed clean HEAD)**: unit 5567/6 · integration 576/14 ·
  e2e 182/9
- **Status (updated 2026-08-12)**: 25 of 29 diagnosed. **Clusters B and C are FIXED** (4 failures
  closed, 3 tests added). Cluster A is minted as **`TECH-029`** and not yet implemented. Clusters D
  and E remain.

| Tier | Before | Now | Remaining |
|---|---|---|---|
| unit | 5567 / **6** | 5586 / **3** | Cluster D (3) |
| integration | 576 / **14** | 578 / **13** | Cluster A (10), E (3) |
| e2e | 182 / **9** | 182 / **9** | Cluster A (8), E (1) |
| **total failing** | **29** | **25** | 18 of them are Cluster A, waiting on `TECH-029` |

> **None of these are a delta to accept.** One is a production defect in the sandbox's resource
> limiter, three are unit tests reaching for a live API key, one is a test whose premise is false on
> any platform. Every fix below must leave the test proving what its name claims.

---

## Cluster A — `RLIMIT_NPROC` is per-user, not per-sandbox — **18 failures** ⚠️ PRODUCTION DEFECT

**Affected**: integration `test_session_reconcile` (6), `test_session_isolation` (3),
`test_session_policy_fullchain` (1); e2e `test_step_worktree_isolation_e2e` (3),
`test_session_worktree_isolation_e2e` (3), `test_implement_loop_worktree_isolation_e2e` (2),
`test_cqrs_e2e` (1).

### Root cause

`sandbox/execution/core/atom.py:24` sets the default limits for every bash step:

```python
_DEFAULT_RESOURCE_LIMITS = ResourceLimits(
    max_memory_bytes=2_147_483_648,  # 2 GiB, FR-11
    max_processes=128,
)
```

`platform_limiter.py` maps `max_processes` to `setrlimit(RLIMIT_NPROC, (128, 128))` inside a
`preexec_fn`, and `executor.py:156` applies `preexec_fn` **only when `sys.platform != "win32"`**.

**`RLIMIT_NPROC` counts every process owned by the real UID, system-wide — not the processes in this
sandbox.** So the cap does not bound what it was written to bound, and it fails whenever the user
happens to be running other things. On Windows the same field becomes a Job Object limit, which
*does* mean "processes in this job" — the intended semantic. The two platforms implement different
constraints under one name, and only the Linux one is wrong.

### Reproduced directly

```
$ bash gen.sh                                   rc=0
$ bash gen.sh  under AS=2GiB + NPROC=128        rc=254
  gen.sh: fork: retry: Resource temporarily unavailable
```

`mkdir -p src` is the first fork in the script, and `254` is bash's exit after exhausting its fork
retries. `RLIMIT_AS` alone is harmless — probed separately and `echo ok` succeeds, because a shell
builtin never forks. Only the fork limit bites.

### Proven by removal

| | integration | e2e | wall clock |
|---|---|---|---|
| `max_processes=128` (today) | 14 failed | 9 failed | 67s / 39s |
| `max_processes=None` | **4 failed** | **1 failed** | **12s / 14s** |

The runtime collapse is part of the evidence: bash was burning seconds in fork-retry loops before
giving up.

### Why it never showed on Windows

`preexec_fn` is guarded by `sys.platform != "win32"`, so **this code path had never executed** on the
development machine. The move to Linux is what ran it for the first time.

### Fix — production, not test

The tests are correct and must not be touched: they assert that a worktree-isolated run completes
and reconciles, which is exactly what `C-EXEC-06` promises.

| Option | Assessment |
|---|---|
| **A. Stop setting `RLIMIT_NPROC`; document that a per-subtree process cap needs cgroups** | Honest. `max_processes` keeps its Job-Object meaning on Windows and becomes explicitly unenforced on Linux, logged like `NoOpLimiter` already does. Loses a limit that was never working anyway |
| **B. Raise the number** | Does not fix the semantic. Still per-user, still breaks on a busy machine, still fails to bound the sandbox. Rejected |
| **C. Implement via cgroups v2 `pids.max`** | The only way to actually deliver the intended constraint on Linux. Correct, and much larger — needs a writable cgroup and a delegation story |

**Recommend A now, C as its own story.** Shipping A means `FR-11`'s memory limit keeps working while
the process limit stops making a promise it cannot keep on this platform.

> This is `B-EXEC-01`/`C-EXEC-02` territory and changes shipped sandbox behaviour, so it should not
> ride along inside `TECH-025` SF-05.

---

## Cluster B — three unit tests need a live `GEMINI_API_KEY` — **3 failures** ✅ FIXED

**Affected**: `test_api_review.py::test_review_returns_result`,
`::test_review_denied_returns_result`, `test_implement.py::test_implement_returns_200`.

### Root cause

The endpoint builds an LLM adapter; `adapter.available()` returns `False` with no key, so
`create_llm_adapter` raises `LLMAdapterError` and FastAPI returns 500.

```
WARNING specweaver.infrastructure.llm.factory:factory.py:72
        create_llm_adapter: adapter not available for gemini
```

`GEMINI_API_KEY` is unset here and is presumably set in the Windows developer's environment or
`.env`. `.env.example:5` lists it, so nothing is missing from the repo — the tests simply depend on
ambient configuration.

### Proven

```
$ GEMINI_API_KEY=dummy-for-probe pytest test_api_review.py test_implement.py
  9 passed
```

### Fix — test defect

`tests/CLAUDE.md` is explicit: *"unit/ — Fast, isolated. **Mock all I/O.**"* A unit test that passes
only when a real provider key is exported is not isolated, and it would reach a live API the moment
a key with quota were present.

Mock the adapter (or `create_llm_adapter`) so the endpoint's own behaviour is what is asserted.
**Do not** set a dummy key in `conftest.py` — that makes the suite green while leaving the tests
dependent on ambient state, and hides the next one that starts reaching outward.

---

## Cluster C — `test_file_size_limit` asserts something that cannot happen — **1 failure** ✅ FIXED

**Affected**: `test_executor_integration.py::TestSubprocessExecutorIntegration::test_file_size_limit`

### Root cause

```python
script = "import sys\nprint('A' * (2 * 1024 * 1024))"   # writes to STDOUT
result = executor.execute([py, "-c", script])
assert result.exit_code != 0                             # "Should be killed by OS (SIGXFSZ)"
```

`RLIMIT_FSIZE` bounds writes to **regular files**. Standard output here is a `subprocess.PIPE`, and
writing to a pipe never raises `SIGXFSZ` at any size. The process exits 0 and the 2 MB arrives in
`stdout` — visible in the failure output.

The docstring says it *"verifies file size limits are enforced on Unix (FR-10)"*. It does not
verify that, and never could as written.

### Fix — test defect, and the fix makes it meaningful for the first time

Have the script write to an actual file inside `tmp_path`, then assert the non-zero exit. That
turns a test which cannot fail-for-the-right-reason into a genuine `FR-10` proof. Worth checking
whether `RLIMIT_FSIZE` is reached at all on Windows, or whether this only ever passed vacuously.

---

## Cluster D — three unrelated causes, not one — **2 fixed, 1 minted as `TECH-030`**

**Affected**: `test_filesystem_tool.py::TestGrantBypassAttempts::test_backslash_normalization`,
`::TestPathTraversalEdgeCases::test_grant_at_root_covers_everything`,
`test_filesystem_atom.py::TestSymlinkIntent::test_symlink_valid`.

### Root cause (class-level; each needs its own reading)

Backslash is a path separator on Windows and an ordinary, legal filename character on Linux. Tests
asserting that `a\b` normalises to a nested path encode Windows semantics. Two fail expecting
success, one expects an error and gets success — so the grant logic behaves differently, not merely
the assertions.

### Fix — needs a decision, not a mechanical edit

The real question is what the **product** should do: is a backslash in a path on Linux a traversal
attempt to reject, or a legal filename to accept? That is a security-boundary decision in
`FolderGrant` territory, and the answer determines whether the code or the test changes. **Not yet
resolved.**

---

## Cluster E — still open — **4 failures**

| Test | What is known | What is not |
|---|---|---|
| `test_loom_stack.py::TestTypeScriptRunnerRealTooling::test_ts_node_debugger_execution` | exit 1. `node`, `npm`, `npx` present; **`ts-node` is not installed** — `npx ts-node` fetches it on demand | Whether the runner shells out to a bare `ts-node` (then it should skip when absent, as the git/bash tests do via `shutil.which`) or resolve through `npx` |
| `test_testrunner_tools_e2e.py::test_e2e_typescript_qarunner_tooling` | Same tooling gap, almost certainly the same cause | Same |
| `test_container_executor_integration.py::TestContainerExecutorRealEngine::test_writable_scratch_mount_allows_writes` | exit 2. `podman info` succeeds, so the engine is usable rootless | Why the scratch mount write fails — likely rootless UID mapping or SELinux labelling, both Linux-only |
| `test_worktree_atoms.py::test_worktree_sandbox_lifecycle_integration` | `AtomStatus.FAILED`; survives the Cluster A fix, so it is a distinct cause | The atom's failure message has not been captured yet |

**A note on the two TypeScript ones**: if the runner genuinely requires `ts-node`, the correct
outcome is a **skip**, not a pass — `test_session_reconcile.py` already models this with
`pytest.mark.skipif(_GIT is None or _BASH is None)`. Installing `ts-node` to make them green would
hide a missing dependency declaration rather than fix one.

---

## Proposed order

1. **Cluster A** — the only production defect, and 18 of the 29. Needs its own ticket; it changes
   shipped sandbox behaviour and belongs to `B-EXEC-01`/`C-EXEC-02`, not to `TECH-025`.
2. **Cluster B and C** — self-contained test fixes, each making the test prove more than it does now.
3. **Cluster E** — finish the diagnosis; the two TypeScript ones probably resolve together.
4. **Cluster D** — needs a product decision on backslash handling before any edit.

---

## What was actually done (2026-08-12)

### Cluster A → minted as `TECH-029`

Not implemented here. It changes shipped sandbox behaviour in `C-EXEC-02`/`B-EXEC-01` territory, and
folding a live `src/` change into `TECH-025`'s citation work is the attribution problem that ticket
exists to remove.

### Cluster B — fixed, and the error path is now asserted on purpose

`tests/unit/interfaces/api/v1/conftest.py` (new) supplies a `stub_llm_adapter` fixture patching
`create_llm_adapter` **at its definition site** — both routes import the symbol *inside* the request
handler, so a patch in either route's namespace would never be seen.

Deliberately **not** an autouse fixture and **not** a dummy key in the environment: either makes the
suite green while leaving it dependent on state no assertion mentions, and hides the next test that
starts reaching outward. Verified with `env -u GEMINI_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY`
— 10 passed.

**Added `TestReviewEndpointWithoutAnLlm::test_missing_provider_key_returns_llm_error`.** The 500 was
always correct behaviour — `review.py` maps `LLMAdapterError` to a structured `LLM_ERROR` response —
but nothing asserted it. It was "covered" only by three other tests failing for the wrong reason.
Now it is pinned deliberately, so the route's documented failure mode has a real proof.

### Cluster C — fixed, and now proves FR-10 for the first time

The write targets a real file instead of a pipe. Two assertions, not one: the process must fail
**and** the file must stop at the limit — "the process failed" alone would also be satisfied by a
typo in the script.

Added `test_a_write_under_the_file_size_limit_succeeds` as a control. Without it the main test would
still pass if the executor were broken such that every child exited non-zero — satisfied for
entirely the wrong reason.

Probed, because the old test proved nothing and the replacement should not repeat that:

```
limit 1MB   exit=1   file=1048576 bytes    <- truncated exactly at the limit
NO limit    exit=0   file=2097152 bytes    <- full write
```

The old test had `skipif(sys.platform == "win32")`, so it was skipped on Windows and broken on
Linux: **it had never run to a meaningful conclusion on any platform.**

---

## Cluster D resolved (2026-08-12) — and it was not one cause

Grouping these three as "Windows path semantics" was wrong. Only one was about backslashes.

- **`test_backslash_normalization`** — genuinely platform semantics. Read
  `src\domain\billing\calc.py` and asserted success, which only holds where backslash is a
  separator. Per the user's ruling (backslash is a legal filename on Linux) it is now two tests: one
  proving a file literally named `back\slash.py` inside a grant is readable on POSIX, and one
  keeping the bypass property the class exists for — platform-agnostic, since on Windows those
  backslashes are a real `..` traversal and on POSIX an exotic filename, and both must be refused.
- **`test_symlink_valid`** — not a path-semantics issue at all. The test never created
  `.worktrees/agent/`, so `os.symlink` failed on the link's parent with ENOENT. With
  `skipif(os.name == "nt")` it was skipped on Windows and broken on Linux: **never run anywhere**,
  exactly like `test_file_size_limit`. Now creates the parent, asserts the link *resolves to the
  target* rather than merely being a symlink, and the missing-parent case is pinned as its own test.
- **`test_grant_at_root_covers_everything`** — **not a test defect. Left failing on purpose** and
  minted as `TECH-030`. `FolderGrant("")` grants read of the whole project on POSIX — including
  `secrets/` and `.git/` — and matches nothing on Windows, because an absolute POSIX path splits to
  a leading `''` and a Windows one to `'C:'`. Scope is the project root, not the filesystem:
  `/etc/passwd` is refused by a separate containment check. Which behaviour is correct is a product
  decision; editing the test would silently bless whole-project read.

**Corrected while investigating**: this analysis first reported the empty grant as reading the
entire filesystem. It does not — the live probe refuses `/etc/passwd`. The real scope is the
project root, which is narrower but still an unintended widening.
