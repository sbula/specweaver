# Design: An Empty `FolderGrant` Path Grants the Whole Project on POSIX and Nothing on Windows

- **Feature ID**: TECH-030
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED (2026-08-12)
- **Origin**: Found 2026-08-12 working through the Linux test failures
  (`docs/analysis/linux_test_failures_2026-08-12.md`, Cluster D). Two of that cluster were test
  defects and are fixed; this one is not. `test_grant_at_root_covers_everything` is **left failing
  on purpose** — it is asserting a real security property that no longer holds on this platform.

## Problem Statement

`FolderGrant("", AccessMode.READ, recursive=True)` means two different things depending on the
operating system.

`FileSystemTool._path_matches_grant` compares path segments:

```python
target_parts = target.replace("\\", "/").split("/")
grant_parts  = grant_path.split("/")          # "" -> ['']
```

and `_resolve_access` builds an absolute `check_path` when the requested path is relative. So the
comparison that decides access is made against an **absolute** path:

| Platform | Absolute path splits to | vs `grant_parts == ['']` |
|---|---|---|
| POSIX | `['', 'tmp', 'proj', …]` | first element is `''` → **matches** |
| Windows | `['C:', 'proj', …]` | first element is `'C:'` → no match |

An empty grant path therefore matches *every* absolute POSIX path under the project root, and no
Windows path at all.

### Measured, on this box

One grant only — `FolderGrant("", READ, recursive=True)`:

```
read src/domain/billing/calc.py   -> success
read secrets/prod.env             -> success      <- granted nowhere
read .git/config                  -> success      <- granted nowhere
```

Against the normal case, `FolderGrant("src/domain/billing", …)`:

```
read src/domain/billing/calc.py   -> success
read secrets/prod.env             -> error        <- correct
```

**Scope is the project root, not the filesystem.** `read_file("/etc/passwd")` is refused by a
separate containment check, so this is not an escape from the project. It is an unintended
whole-project read — including `.git/` and anything a repository keeps beside its source.

### Why it never showed before

`test_grant_at_root_covers_everything` asserts `status == "error"` with the comment *"Empty-string
grant path is treated as invalid — doesn't match"*. That is true on Windows and false on Linux, so
the test passed for four years on the platform where the branch is unreachable.

This is the same shape as `TECH-029`: one configuration, two platform behaviours, and the divergence
invisible until the code ran somewhere new. It is worth asking during design whether these two are
instances of a pattern worth auditing rather than two isolated bugs.

## The decision this ticket exists to make

**Not** "make the test pass". Either answer requires a production change, and editing the test to
match current Linux behaviour would silently bless whole-project read.

| Reading | Consequence | Argument for |
|---|---|---|
| **A — an empty grant path is invalid** | Reject it at construction, so the mistake is loud instead of permissive. Matches what the test asserts and what Windows already does | A grant that names nothing looks like a bug or an unset config; failing closed is the safe default for a security primitive |
| **B — an empty grant path means "project root"** | Legitimate and explicit: with `recursive=True` it covers the project by design. Windows becomes the broken platform and is fixed to match | Symmetric with `FolderGrant(".")`, and there are real roles (a reviewer with whole-project read) that may want it |

**Leaning A.** The system already expresses "read the project" by granting the directories that make
it up, and every current caller passes a real path — so B would add a spelling for something already
sayable, in the one component where an accidental empty string must not widen access. But the
callers must be counted before deciding: if any legitimately relies on the POSIX behaviour today,
A breaks it and that has to be seen first.

Whichever is chosen, **the two platforms must agree**, and the fix belongs in
`_path_matches_grant`/`_resolve_access` rather than in the caller.

## Candidate Approaches (not yet designed)

- **Validate in `FolderGrant.__post_init__`** if A wins — one place, applies to every consumer, and
  turns a silent widening into a construction-time error.
- **Normalise the comparison so it is not string-segment-based.** The leading `''` is an artifact of
  splitting an absolute POSIX path. Comparing resolved `Path` objects with `is_relative_to` removes
  the whole class of separator and root-segment bugs rather than patching this instance.
- **Ship the guardrail with the fix.** `test_grant_at_root_covers_everything` becomes the regression
  test once the decision is made; it should also gain a sibling asserting the *other* platform's
  reading, so the two can never drift apart again.
- **Audit the sibling assumptions.** `_path_matches_grant` also does `target.replace("\\", "/")`,
  which treats a backslash as a separator — deliberate on Windows, and on POSIX it silently rewrites
  a legal filename character. The user's ruling (2026-08-12) is that a backslash is a legal filename
  on Linux, so that line has the same platform-divergence shape as the defect above.

## Non-Goals (proposed, pending design)

- **Not** the absolute-path containment check, which correctly refuses `/etc/passwd` and is
  unaffected.
- **Not** `TECH-029`'s `RLIMIT_NPROC` defect, though the two share a root pattern.
- **Not** the two Cluster D tests already fixed (backslash-as-filename, and the symlink test that
  never created its link's parent directory).
- **Not** a general rewrite of the grant model. If the design concludes that `is_relative_to` should
  replace segment comparison, that is the fix for this defect and not licence to redesign roles.

## Next Step

Run through `specweaver-design`. Before writing any FR:

1. **Count the callers.** Grep every `FolderGrant(` construction in `src/` and in the sandbox
   factory. If none passes an empty path, A is nearly free; if any does, its intent decides the
   question.
2. **Confirm the Windows behaviour is what the test claims**, rather than inferring it from the
   split. It has never been asserted on Windows either — the test passes there for a reason nobody
   has verified.
3. **Decide A or B**, then make both platforms implement it, with a test per platform reading.

---

## Delivery (2026-08-12)

**Decision: option A — an empty grant path is invalid** (user). Rejected at construction, in
`FolderGrant.__post_init__`.

### The caller count decided the shape, as §Next Step said it would

- **`src/`: zero** of eight `FolderGrant(` constructions pass an empty path. Rejecting breaks no
  production code.
- **`tests/`: twelve** call sites did — all in `code_structure` suites using `""` as a
  "grant everything" convenience. **They passed because of the bug.**

That mattered, because `"."` does *not* work as a whole-project grant, so the obvious replacement
was not available. Two legitimate expressions already existed and were used instead:

- `FileSystemTool` — the project root's **absolute path**, verified working.
- `CodeStructureTool` — **`"/"`**, which `_resolve_mode` already maps the root case to explicitly.

So no new capability was needed; the tests were leaning on the defect where a supported spelling
existed.

### Both definitions guarded

`FolderGrant` is declared **twice** — `sandbox/security.py` and
`sandbox/filesystem/interfaces/models.py` — and both are imported by real callers, so guarding one
would have left the hole open through the other. A test pins each. **The duplication itself is a
defect** and is left recorded rather than fixed under a security change.

### Verified end to end

```
empty grant                       -> ValueError, naming the fix in the message
explicit project-root grant       -> success        (whole-project access still expressible)
scoped grant reading secrets/     -> error          (scoping still works)
```

### The test that had to change, and why it is not weakening

`test_grant_at_root_covers_everything` asserted `status == "error"` — the *Windows* reading, on the
platform where that branch is unreachable. That is why it passed for years while the hole was open.
It now asserts the construction raises, which is where the guard lives.

### Final state

```
tests/unit         5630 passed, 0 failed
tests/integration   591 passed, 0 failed
tests/e2e           191 passed, 0 failed
```

The Linux migration's 29 failures are closed.

## Carried down from the topic entry (2026-08-13, `TECH-044`)

Moved here verbatim when the entry was shortened to four lines — recorded rather than dropped.

- `_path_matches_grant` compares path **segments**, and `_resolve_access` builds an absolute path
  first: on POSIX `/tmp/proj/x` splits to `['', 'tmp', …]` whose first element matches an empty
  grant's `['']`, while on Windows `C:/proj/x` splits to `['C:', …]` and never matches.
