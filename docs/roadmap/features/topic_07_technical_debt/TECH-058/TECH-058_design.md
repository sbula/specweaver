# Design: The Nightly's Baseline Forgot Its Own `-n auto`

- **Feature ID**: TECH-058
- **Epic**: Topic 07 (Technical Debt)
- **Status**: APPROVED (2026-08-16)
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-058/TECH-058_design.md
- **Origin**: 2026-08-16, verifying an unexplained gap in `TECH-057`'s measurements. A defect in
  `TECH-049`'s delivered session, so a new ticket rather than an edit to it.

> **Proportionality.** Two argv entries. It is a ticket because it is a 3.8x defect in the nightly's
> largest single cost, and because the wrong explanation had already been written down.

## Problem Statement

`run_baseline` built its command without `-n auto`:

```python
cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider", tests]
```

`_mutate.run_one` adds `-n auto` on **the same path** — the unscoped, whole-suite run. `run_baseline`
is *always* a whole-suite run and did not. Nothing compared the two, so an asymmetry plainly visible
in both files sat there unremarked.

Measured in a real sandbox, same worktree, three runs:

| run | seconds |
|---|---|
| as shipped, serial | **291.2** |
| same sandbox, warm `__pycache__`, still serial | **291.7** |
| same sandbox, `-n auto` | **77.3** |

**3.8x.** The baseline was **69%** of a 6m51s session whose actual mutant work was 129.5s, and
`291 + 129.5 = 420s` reconciles that session to within ten seconds.

**The recorded hypothesis was wrong, which is half the reason this is written down.** `TECH-057`
and the guide both said the likely cause was a cold `__pycache__` in a fresh worktree. The warm
second run cost **+0.5s**. Guessing at a cause and filing the guess is how a wrong explanation
outlives the person who wrote it; the measurement is cheap and settles it.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | The baseline runs the suite in parallel, as every other whole-suite run does | The nightly session | lays its baseline before judging any mutant | the suite runs under `-n auto`, so the baseline costs ~77s rather than ~291s, and a red baseline is still reported with its failures intact |
| FR-2 | The unit hands the run a `PATH` that can find the toolchain | The systemd service | starts the nightly under a user manager, which supplies a minimal `PATH` without `.venv/bin` | `tach` — shelled out to by `test_architecture.py` and by the tach pytest plugin at collection — resolves, so the baseline reports failing tests rather than a collection error that reads `green=false, failed=0` |
| FR-3 | The unit raises the file-descriptor limit before the suite needs it | The systemd service | starts a run that fans out one `-n auto` worker per core | `LimitNOFILE` is above the 1024 a user service inherits, so the suite does not exhaust descriptors as ~690 `OSError`s scattered across unrelated unit tests, none of which fail alone or in any pair of tiers |

`FR-2` and `FR-3` were **delivered with this ticket and never written down** — added
`[agreed 2026-08-27]` after `check_dangling_citations.py` found two tests citing them against a
table that declared one requirement. Both are in the shipped unit file with their reasoning in
comments; neither had a row here. The ticket did three things and this table claimed one.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | The verdict must survive the change | A red baseline is context, not a gate — `verdict_of` turns it into `INDETERMINATE`. Losing failures under xdist would silently convert *"the tree was already broken"* into *"this requirement is unprotected"*, the one reading the corpus must never produce |
| NFR-2 | Proven by the command, not a stopwatch | A timing assertion is flaky on a loaded box and gets deleted the week it first goes red. The speed is evidence in this document; the test pins the flag and the agreement between the two runners **[proof: meta — rule about tests, docs or the diff]** |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Match `_mutate.run_one` rather than invent a policy | The repo already decided whole-suite runs are parallel; this is one runner catching up with the other, not a new position | No |
| AD-2 | Fix the baseline before parallelising mutants (`TECH-057`) | The baseline was 69% of the session. Building a sandbox pool first would have parallelised the 31% and left the rest — optimising around the actual cost | No |

## Sub-Feature Breakdown

**Single feature — no decomposition.**

## Execution Order

One commit boundary: the failing tests, then two argv entries.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Single feature | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: DELIVERED 2026-08-16.

**What it changes for `TECH-057`.** The nightly's cost was 291s baseline + 129.5s mutants; it is now
~77s + 129.5s. Parallelising mutants was already the smaller half of the problem and is now the
larger one — which is the right order to have discovered it in, and the reason `TECH-057` says to
re-measure before designing.
