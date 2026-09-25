# Anti-Patterns (Learned)

Each row cost a session. The table is the rule; the cases below it are the evidence.

## Module boundaries

| Anti-Pattern | Why It's Wrong |
|--------------|----------------|
| Putting tool-consuming code in `commons/` | Violates `forbids: tools/*` |
| Creating parallel security classes (e.g. `WorkspaceBoundary`) | Duplicates `FolderGrant` + `FileExecutor._validate_path()` |
| Centralizing tool definitions in a separate module | Each tool should own its own `ToolDefinition` list |
| God-object dispatcher reimplementing I/O | Delegate to actual tool methods instead |
| Naming modules by what the agent *does* ("research") | Name by what the code *is* |
| Domain modules importing from `sandbox/*` | 12 of 16 modules explicitly forbid this — use `flow/` as the bridge |
| Hiding dependencies via inline imports inside methods | Bypasses `tach` and hides how tightly modules are coupled |
| A declared rule that nothing reads | A rule with no reader is documentation about itself. Enforce it with a test that ships with it, or record it in [Known Boundary Violations](known_boundary_violations.md) where a human sweep will find it. [Case](#a-declared-rule-that-nothing-reads) |

## Seams and tests

| Anti-Pattern | Why It's Wrong |
|--------------|----------------|
| Two modules naming one thing differently across a seam | Each half is self-consistent and neither sees the other, so every test of either half passes while the pair cannot work. Give the thing **one** name as a shared constant both sides import, and write the agreement test: hand one half's output to the other half's reader, naming no key of your own. [Case](#two-modules-naming-one-thing-differently-across-a-seam) |
| Two tests citing one FR while pinning opposite halves of it | **A citation count answers *is this FR mentioned*, never *is this FR met*.** Where an FR says *A and B*, one test must drive A **into** B; asserting each separately is the `TECH-056` composition defect wearing a ledger's clothes. [Case](#two-tests-citing-one-fr-while-pinning-opposite-halves-of-it) |
| A gate that checks for **words about** a rule instead of the rule | It measures the presence of vocabulary, not the truth of a claim. A guaranteed-present record is worse than a missing one: missing makes the next agent stop and ask; present-but-rotten makes it proceed and build. [Case](#a-gate-that-checks-for-words-about-a-rule-instead-of-the-rule) |
| Marking a test `@pytest.mark.integration` / `e2e` while leaving it under `tests/unit/` | Tier is selected by **directory**, not by marker — `tests.py` passes `tests/integration` and `tests/e2e` as paths. The marked test runs in the unit tier and is never selected by the tier it claims. Move the file; the marker alone is a label, not a location |
| `# fr-coverage: fixture-data` on a file that also carries a real `Proves:` tag | The marker is a **file-level** exemption, so it silently nullifies the citation — the ledger reports the FR as unproven while the test that proves it sits there passing. Give fixtures requirement ids the design does not declare (`FR-98`), then the file needs no marker |
| A test that reads the wall clock it does not control | **An uncontrolled clock is an uncontrolled input, and a relative age is not the same claim as a schedule.** Pin `now` (patch the module's own `time` name, not the global) and state the wall time the test means. [Case](#a-test-that-reads-the-wall-clock-it-does-not-control) |

## Storage

| Anti-Pattern | Why It's Wrong |
|--------------|----------------|
| Unchunked bulk graph ingestion into SQLite | Triggers `database is locked` deadlocks (RT-4); always batch `executemany` into 5,000-row chunks |

## Cases

### Two modules naming one thing differently across a seam

- `TECH-068` hit this twice in one ticket. The engine wrote the edge kind under `kind` and the store
  read `type`, so 108 persisted edges all took the store's `"CALLS"` fallback. The fix then left
  `load_from_db` still writing `type`, so a graph read back could never be written again. Remedy:
  `EDGE_KIND_ATTR`.
- **It recurred in `scripts/` on 2026-08-27**, after the remedy above was written. `68a089d4` renamed
  a session record's first block `summary` -> `session` in the producer and the renderer and missed
  `_mutation_gate`'s single reader. The gate's red-baseline rule matched no document any producer
  wrote and could never fire for as long as it existed. Both halves had tests; the gate's fed it the
  retired shape. Now `_session_record.SESSION_BLOCK`.

### Two tests citing one FR while pinning opposite halves of it

`TECH-049` `FR-3` reads *"record the collected count **and the node id of every failing test**"*.

- `test_mutation_session.py::TestBaseline` — docstring *"records what failed, by node id"* —
  asserted `run_baseline` captures them.
- `test_session_record.py` asserted the written record is **exactly** `{ran, green, failed}`, which
  pins their removal.

Both passed, `check_fr_coverage` reported FR-3 cited by two files, and the story was `COMPLETE` with
half the requirement unbuilt. The nightly then went red on three consecutive nights and named
nothing, because `_session_record.py` took `len()` of the list and dropped it. Two tests can each be
right about their own end while the requirement between them is not built.

### A gate that checks for words about a rule instead of the rule

`TECH-069` read every design for a `Decisions taken with the user` section naming all thirteen §2
triggers. It passed:

- one bullet listing them all as `not touched`;
- flipping `fired — <answer>` to `not touched` — *while deleting the answer*;
- `T-SPEND: not touched` beside a live currency figure, because it never read the rest of the design.

Where the recorded fact is *testimony* — what a human agreed, once, in a conversation — no later run
can recompute it, so the drift is undetectable by construction. `PRINCIPLES.md` §5 already forbade
the second copy. Retired 2026-08-23; a settled decision is now written `` `[agreed <date>]` `` beside
the fact it governs, where whoever edits the fact must look at it.

### A declared rule that nothing reads

`allowed_imports` in `graph/**/context.yaml` is not in the `context.yaml` schema and no script or
test opened it. So `TECH-068`'s `AD-3` — a user-approved architectural switch — could be marked
delivered while none of its three obligations happened.

### A test that reads the wall clock it does not control

`test_a_fresh_report_does_not_block_on_staleness` wrote a report **sixty seconds old** and asserted
the gate would not call it stale. The gate does not measure age: it asks whether the report
predates the **last scheduled run**, and `NIGHTLY_HOUR = 3`. Between 03:00:00 and 03:01:00 a
sixty-second-old file is from yesterday's business, so the gate blocks and is right to. The nightly
runs at 03:00.

It failed on 2026-08-26, took the baseline red, and voided all 145 verdicts — including the five
`TECH-056` mutants that share the file, which reported `UNMEASURED [scope-already-red]` rather than
an answer. It read as flaky for four nights and was not: it is deterministic inside the sixty-second
window the suite runs in.
