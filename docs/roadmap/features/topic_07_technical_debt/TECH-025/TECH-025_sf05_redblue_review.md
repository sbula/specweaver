# Red/Blue Team Review — TECH-025 SF-05 (TECH-002 FR Ledger)

- **Target**: `TECH-025_sf05_task.md` + `TECH-025_sf05_implementation_plan.md`
- **Date**: 2026-08-11
- **Cycles**: 2
- **Findings**: 8 (1 CRITICAL, 3 HIGH, 3 MEDIUM, 1 LOW)
- **Status**: CRITICAL and HIGH fixes fold into the task list before any code is written

> Bare `FR-N` is **TECH-025's**. Others are written qualified — `TECH-002 FR-4`.

---

## Cycle 1

### 🔴 RED-1.1: The plan creates a live false credit in the file it is adding citations to

**Category**: Boundaries & Dependencies · **Severity**: **CRITICAL**
**Target**: Plan §3, `tests/unit/test_architecture.py`

**Finding**: The plan places TECH-002's two absence invariants in `tests/unit/test_architecture.py`.
That file **already contains the string `TECH-001`**. `check_fr_coverage.cited_frs_in_tests`
attributes **whole-file**:

```python
if text is None or story not in text:      # names the story?
    continue
for fr in sorted(collect_frs(text)):       # then credit EVERY FR-N token in the file
```

So the moment the file also names `TECH-002`, TECH-002 is credited with every `FR-N` token present —
today `FR-4, FR-5, FR-6, FR-7, FR-8, FR-9`.

**Evidence** — simulated by appending *only* `Proves: TECH-002 FR-5.` and `FR-6.`:

```
  6 FR(s) cited by tests naming TECH-002
  FR-4    NO PLAN  1 test file(s)     <- FALSE. Borrowed from TECH-001's
  FR-5    NO PLAN  1 test file(s)         test_cli_commands_live_in_their_own_domains
  FR-6    NO PLAN  1 test file(s)
```

TECH-002 FR-4 is *"each domain facade inherits `BaseTool` and registers its factory"*. The test that
would credit it asserts CLI commands live in their own domains. It proves nothing about FR-4.

**Attack Vector**: TECH-002's ledger closes partly on a borrowed citation. This is the third
appearance of the defect class SF-01 was created to fix and SF-04 CB-3 caught in `TECH-022` — now
inside the sub-feature whose entire purpose is honest traceability.

### 🔵 BLUE-1.1 — **VALID, FIX REQUIRED**

SF-01's own plan already ruled on this, and the rule was not carried into SF-05:

> This new file must contain **no real story ID other than `TECH-025`**. It names `TECH-025` (for the
> `Proves:` tag) and would otherwise credit any story it mentioned with every `FR-N` token in it —
> reintroducing the defect one file over.

**Fix**: the two TECH-002 invariants move to a **new test file naming only `TECH-002`**, containing
**exactly two** `FR-<digit>` tokens — the ones in its own `Proves:` tags. The generalised scanner
stays in `test_architecture.py` and is **imported**; importing does not copy `TECH-001` into the new
file's text, so the scanner is shared without the credit being shared. Verified:

```
from tests.unit.test_architecture import config_orchestration_offenders, SRC_ROOT   -> OK
```

(`tests/` and `tests/unit/` both have `__init__.py`; `pythonpath = ["src", "."]`.)

Filename must carry no registry ID (SF-02's R5) — proposed `tests/unit/test_layer_import_isolation.py`.

---

### 🔴 RED-1.2: The plan's verification block cannot detect RED-1.1

**Category**: Testability · **Severity**: **HIGH**
**Target**: Plan §Verification

**Finding**: The verification runs `TECH-001` (must stay 0), `TECH-005` (stays 1), `TECH-022`
(stays 1). None moves under RED-1.1: TECH-001 already cites FR-5/FR-6 from this very file, so its
count is unchanged, and TECH-005/TECH-022 are untouched. The only ledger that moves is TECH-002 —
and it moving to 0 is the *declared goal*, so a false credit and a real one look identical.

**Attack Vector**: The plan's own guard rails pass while the defect ships. The commit message would
truthfully report every check green.

### 🔵 BLUE-1.2 — **VALID, FIX REQUIRED**

**Fix**: add a positive assertion to the task list — after CB-2, each of TECH-002's six FRs must be
cited by the **specific file that genuinely proves it**, not merely by *some* file. Concretely:
`FR-4` must resolve to `test_sandbox_registry.py` and **must not** resolve to `test_architecture.py`.
A count-based check cannot express this; the file list must be read.

---

### 🔴 RED-1.3: Plan R4's central claim is false

**Category**: Testability · **Severity**: **HIGH**
**Target**: Plan R4

**Finding**: R4 justifies the file choice with *"a new absence proof placed there inherits the guard
that its live inputs actually exist."* It does not. `test_the_invariants_below_are_reading_the_real_tree`
asserts **named paths**:

```python
assert (SRC_ROOT / "sandbox").is_dir()
assert list((SRC_ROOT / "core" / "config").glob("*.py"))
for entry in ("factory.py", "router.py"): ...
```

Nothing there covers `assurance/validation/` or `interfaces/`. Both new invariants are absence proofs,
and absence is exactly what a missing tree returns — vacuous-proof **pattern 8**.

### 🔵 BLUE-1.3 — **VALID, FIX REQUIRED**

**Fix**: the new file writes its **own** real-tree guard for its two roots, asserting each exists and
contains `.py` modules **recursively**. Written first, and demonstrated by pointing the scanner at a
deliberately wrong root and watching it report clean. R4's rationale for using `test_architecture.py`
collapses with this finding, which independently supports BLUE-1.1's move.

---

### 🔴 RED-1.4: FR-5 and FR-6 are treated as symmetric; they are not

**Category**: Architecture · **Severity**: **MEDIUM**
**Target**: Plan §3

**Finding**: Probed live — `tach` **already enforces** TECH-002 FR-5's absence half. Planting
`from specweaver.sandbox.registry import ToolRegistry` into
`assurance/validation/rules/code/c03_tests_pass.py` makes `tach check` fail, because
`specweaver.assurance.validation` declares `depends_on = ["specweaver.workspace.analyzers",
"specweaver.core.config"]`. Meanwhile **`specweaver.interfaces` is not a declared tach module at
all**, so FR-6 is enforced by nothing.

**Attack Vector**: A later reader sees two identical-looking tests, discovers one duplicates tach,
and deletes both as redundant — silently retiring the only guard FR-6 has.

### 🔵 BLUE-1.4 — **VALID, FIX REQUIRED**

**Fix**: the docstrings state the asymmetry explicitly. FR-5's says tach is the primary enforcement
and this is the *citable* second one — necessary because `test_tach_architectural_boundaries` carries
no FR tag and shells out to a bare `tach` that is invisible unless `.venv/bin` is on `PATH` (observed
this session). FR-6's says nothing else enforces it.

**Recorded, not fixed here**: adding `specweaver.interfaces` to `tach.toml` is the durable fix for
FR-6. It is a change to a shipped boundary file and is out of this sub-feature's traceability scope.

---

### 🔴 RED-1.5: "Unparseable module raises" turns any syntax error into a confusing failure

**Category**: Robustness · **Severity**: **MEDIUM** · **Target**: Plan Test Plan T7

**Finding**: A syntax error anywhere under `validation/` or `interfaces/` surfaces as an architecture
test failing, not as a parse error where it happened.

### 🔵 BLUE-1.5 — **VALID — ACCEPTED RISK**

Raising is correct: silently skipping an unparseable module is how an absence proof goes vacuous, and
the repo's own `test-quality.md` names that pattern. The mitigation is a message naming the offending
path, not a behaviour change. Any syntax error in `src/` already fails many other tests.

---

### 🔴 RED-1.6: Filename must carry no registry ID

**Category**: Maintainability · **Severity**: **LOW** · **Target**: new file

### 🔵 BLUE-1.6 — **VALID, FIX REQUIRED**
`test_layer_import_isolation.py` — names the behaviour, not the ticket. Enforced by
`check_conventions.py` R5, which SF-02 widened to cover exactly this.

---

## Cycle 2 — challenging Cycle 1's defences

### 🔴 RED-2.1: BLUE-1.1's new file re-creates the trap one level up

**Category**: Boundaries · **Severity**: **HIGH**
**Target**: proposed `test_layer_import_isolation.py`

**Finding**: TECH-025's own SF-05 owns **FR-2** ("close TECH-002's ledger"), which will eventually
need a test citation. The obvious place is the new file. But that file names `TECH-002` and carries
`FR-5`/`FR-6` tokens — so adding `Proves: TECH-025 FR-2.` makes it name TECH-025 too, and TECH-025
would then be credited **FR-5 and FR-6** from tokens that belong to TECH-002. TECH-025's FR-5 is
SF-07's ledger-regression guard and FR-6 is SF-02's test-naming rule; neither is proven by an import
scan. Identical shape to RED-1.1, one story up.

### 🔵 BLUE-2.1 — **VALID — DEFERRED, AND RECORDED**

The new file must **not** carry a `TECH-025` tag. It names `TECH-002` only.

TECH-025's own ledger currently cites **FR-9 alone**, so this is pre-existing and not SF-05's to
solve: SF-04 delivered FR-1/FR-4 without citing them either. The ticket closes its own ledger at
closure, and this finding says that closure **cannot** simply tag the sub-feature test files — every
one of them names a subject story and carries that story's FR tokens. Recorded as a constraint on
**SF-07**, which owns FR-5 and the manifest.

---

### 🔴 RED-2.2: The new file must be checked for accidental `FR-N` tokens, not assumed clean

**Category**: Testability · **Severity**: **MEDIUM** · **Target**: new file

**Finding**: SF-01 hit exactly this — the natural way to write these tests scatters `FR-N` strings
through fixtures and comments. A comment reading *"unlike FR-4's conformance test"* would silently
credit TECH-002 FR-4 again, re-creating RED-1.1 in the file built to avoid it.

### 🔵 BLUE-2.2 — **VALID, FIX REQUIRED**

**Fix**: assert it mechanically, following SF-01's T9 precedent — the new file reads its own source
and asserts it contains **exactly two** literal `FR-<digit>` tokens. Self-guarding, and it survives a
future contributor adding an innocent-looking comment.

---

## Corrections folded into the task list

| # | Change |
|---|---|
| 1 | Both TECH-002 invariants move to a new `tests/unit/test_layer_import_isolation.py` naming only TECH-002 (BLUE-1.1) |
| 2 | That file writes its own real-tree guard for `validation/` and `interfaces/` (BLUE-1.3) |
| 3 | The generalised scanner stays in `test_architecture.py` and is imported (BLUE-1.1) |
| 4 | CB-2 verification reads the **file list** per FR, not just the count — FR-4 must resolve to `test_sandbox_registry.py` and not to `test_architecture.py` (BLUE-1.2) |
| 5 | Docstrings state the tach asymmetry so neither test is deleted as duplicate (BLUE-1.4) |
| 6 | No `TECH-025` tag in the new file; the constraint is recorded against SF-07 (BLUE-2.1) |
| 7 | The new file asserts it contains exactly two `FR-<digit>` tokens (BLUE-2.2) |

## Accepted risks

- **RED-1.5** — an unparseable module raises rather than being skipped. Correct behaviour; mitigated
  by naming the offending path in the message.

## Stop condition

Cycle 2 produced 1 HIGH and 1 MEDIUM — below the ≥2 HIGH / ≥5 MEDIUM thresholds. Review complete.
