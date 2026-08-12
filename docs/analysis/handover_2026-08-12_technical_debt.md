# Handover — Technical-Debt Session, 2026-08-12

Written at the end of a long session that took `topic_07` from two chronically-red gates to a fully
green tree. Read the **Cautions** section before touching anything; several of them are traps that
already cost this session real time.

**Tree state at handover** — clean, everything committed to `main`:

| | |
|---|---|
| Full suite | `6485 passed, 11 skipped, 0 failed` (~54s with `-n auto`) |
| `scripts/quality.py cb` | **0 failed of 12** |
| `mypy src/` | clean, 334 files |
| `ruff`, `tach` | clean |
| Dependency cycles | **0 across 327 modules** (was 4) |
| Complexity ratchet | **41** frozen (was 97) |
| Class-health ratchet | **19 incohesive + 1 oversized** frozen (was 23) |
| Suppressions ratchet | **229** frozen (was 239) |

---

## 1. What shipped this session

`TECH-014`, `TECH-020`, `TECH-024`, `TECH-026`…`TECH-030`, `TECH-032`, `TECH-033`, `TECH-034` —
all **DELIVERED**. `TECH-025` **COMPLETE**. Each has a `§Delivery` section in its design doc; that
is the authoritative record, not this file.

Three are worth knowing about because later work depends on their shape:

- **`TECH-034`** split the AST parser hierarchy into three paradigm tiers (`ClassBasedParser`,
  `FunctionBasedParser`, `DeclarativeParser`). The governing rule written into `tiers.py` is
  **a tier supplies defaults, never prohibitions** — that is what keeps a future `proto` parser
  (declarative *with* imports) from breaking the design. It also fixed the C++ inheritance gap,
  which the tier caught *by construction*: reparenting `CppCodeStructure` made it un-instantiable
  until `_extract_bases` existed.
- **`TECH-029`** closed 18 of the 25 chronic Linux failures. Its fix is a deliberately best-effort
  backstop — see Caution 2.
- **`TECH-033`** made the retry budget reset correctly across resume. `LoopState.for_run`
  reconstructs `attempts` from `run.step_records`, so a resumed run does not silently inherit a
  spent budget.

## 2. Open tickets, and what each actually needs

### Partial — real work remaining

| Ticket | State | Next concrete step |
|---|---|---|
| **`TECH-023`** Complexity | **41 of 97** frozen. Ratchet green. | `core/flow` holds 12 of the 41 — the only cluster left big enough to pay for a shared abstraction. The rest is a long tail across 22 packages. |
| **`TECH-035`** Class health | Ratchet shipped; **19 incohesive + 1 oversized** frozen. Gate green. | **Settle the dispatcher question first** (below). It decides whether 3 of the 19 are debt at all, and "the metric is wrong here" vs "the class is wrong here" lead to opposite work. |
| **`TECH-031`** Container prepare phase | QA-runner half delivered; **the prepare phase has never installed a toolchain** and that is unfixed. | The chain is latent in production only because `execution_mode` defaults to `"host"`. It was proven broken against live podman — do not re-litigate whether it works. |

**`TECH-023`'s remaining 41, by package** (largest first): `core/flow` 12, `assurance/validation` 5,
`assurance/standards` 3, `sandbox/filesystem` 3, then 22 packages with one or two each. Bands: 11 at
25–39, 9 at 20–24, 21 at 16–19, **nothing at 40+**.

**`TECH-035`'s open design question — decide before touching any of the three.** `FileSystemAtom`,
`GitAtom` and `QARunnerAtom` each split into "the `_intent_*` handlers" and "`run`". That is
arguably the *correct* shape for an intent dispatcher, in which case the answer is a documented,
reviewable exemption — not a forced split. `TECH-035_design.md` §Candidate Approaches states this.

Also in `TECH-035`, already corrected once and worth not re-breaking: **the standards analyzers are
not the parsers' pathology repeated.** They already have their own tier
(`StandardsAnalyzer` → `TreeSitterAnalyzer` → `JS`/`TS`), and `PythonStandardsAnalyzer` sits
outside it on stdlib `ast` **on purpose**. Do not refactor them toward uniformity.

### Stub — never run through `specweaver-design`

`TECH-010`, `TECH-011`, `TECH-013`, `TECH-017`, `TECH-018`. Problem statements only.
Any of these needs the design skill before implementation, not a direct attempt.

*(`TECH-016` left this list on 2026-08-12 — delivered without a `specweaver-design` run, because
measuring its six claimed call sites against the code settled the whole decision space: the
model-shaped helper it proposed fitted two of them. It also closed `TECH-036`, filed the same day.)*

### Designed but not built

`TECH-008` (DESIGN_HARDENED), `TECH-009` (DESIGN_COMPLETE), and `TECH-001`…`TECH-005`, `TECH-007`
(APPROVED).

### Adjacent capability

**`B-EXEC-04`** — Kernel-Enforced Resource Bounds (cgroups v2 `pids.max`). Not a `TECH` ticket.
See Caution 2: it must **remove** `TECH-029`'s backstop, not layer on it.

---

## 3. Cautions — read these before starting

**1. `TECH` lines in the roadmap use `✅` or `[ ]`. Never `[x]`.**
`[x]` is for user stories. This was gotten wrong in this session and the correction was emphatic.
The rule is now documented as **R-MARKER** in the roadmap placement contract and enforced by
`scripts/check_roadmap_placement.py` with its own tests. The trap is that the contract shows only
the open form beside a "check off the boxes" instruction that refers to user stories.

**2. `TECH-029`'s process cap is a backstop to be deleted, not a foundation to build on.**
`max_processes` is applied as *current task count + budget* because `RLIMIT_NPROC` is per-real-UID
and counts threads — an idle host sits at 234 tasks against a configured 128, which is why **every
bash step failed** before it was measured. It remains approximate: the limit still applies to the
whole UID, and the baseline can drift between measurement and exec. When `B-EXEC-04` lands, the
correct move is to **remove** this and let cgroups v2 bound the subtree. `C-EXEC-02`'s FR-11 has
been amended to say exactly this.

**3. Probe every guardrail by planting a violation. Reading the code is not verification.**
This session found three checks that were inert or silently skipped: `R-OWNER` shipped inert,
`-p no:randomly` was a no-op for a plugin that is **not installed** (so any flake attributed to it
was misdiagnosed — it was a real regression), and `check_class_health` reported
`nothing in scope` for an entire session while 20 classes were failing. **A check that silently
does not run is indistinguishable from one that passes.** When probing, also check that your probe
is real — the first `class_health` "getting worse" probe added a field the checker does not count
and read as a gap in the guard.

**4. `check_class_health`'s commit-gate scope is `changed`, so it skips silently.**
It only inspects files the commit touched. That is what let it stay red-but-invisible. The ratchet
now bounds it, but the scoping behaviour is unchanged — do not read a green run as "the tree is
clean" without `python scripts/check_class_health.py src`.

**5. Toolchain PATH is not exported in a fresh shell.** Java, Kotlin and Rust are installed but
their locations are not on `PATH` by default. Before running anything that shells out to them:

```bash
export PATH="$PWD/.venv/bin:$HOME/.cargo/bin:$HOME/.sdkman/candidates/java/current/bin:$HOME/.sdkman/candidates/kotlin/current/bin:$PATH"
```

`.venv/bin` is load-bearing on its own: `tests/unit/test_architecture.py` shells out to a **bare
`tach`**, which `.venv/bin/python -m pytest` cannot otherwise see.

**6. `tests.py cb <STORY> --kind tooling` selects the unit tier only.** Integration and e2e
failures went unmeasured for a day because of this. Pass `--all` when a change could reach beyond
unit. `python scripts/tests.py matrix` shows every profile.

**7. Moving a function to another file reads as a *new* complexity violation.** The ratchet is
keyed on `file::function`. A pure relocation will look like a regression; check each one against
its old score before re-freezing, and say so in the commit message. Three of these came up during
the `BaseTreeSitterParser` split and all three were genuine no-ops (16→16, 16→16, 19→19).

**8. Extracting a helper can trade a complexity violation for a suppression.** `_dlx_logger` was
extracted returning `object`, which then needed `# type: ignore[attr-defined]` to call `.error`.
The suppressions ratchet caught the `+1` at the commit gate. The fix is the honest return type
(`logging.Logger`), never a re-freeze.

**9. One pre-existing test-isolation defect, currently untracked.**
`tests/integration/interfaces/cli/test_drift_rot_handler.py::test_rot_check_exits_42_on_drift`
**fails when run alone and passes in the full suite.** Verified pre-existing — identical with and
without this session's drift refactor. It is a test-isolation problem, not a production defect, and
it has no ticket. If it bites you, file one rather than assuming you broke it.

**10. `CLAUDE.md`'s Linux-failure block was stale and has been corrected.** It listed 25 chronic
failures and told the reader not to fix them. All 25 are fixed and the suite is green. If you see
a failure, it is yours.

---

## 4. Working conventions that paid off, and are worth continuing

- **Reduce by cluster, not by score.** Six batches took complexity 97 → 41, and the recurring
  finding was that *a cluster of violations is usually one duplicated mechanism, not N complicated
  functions*. Nine of the last two batches' violations were cleared by naming the shared thing once
  (`_context_walk.resolve_up_tree`, `_documentation.coverage_band`). No function was split for the
  sake of the number.
- **Ratchet before reduce.** Every one of the four ratchets (`suppressions`, `complexity`,
  `class_health`, R6/R7) turned a permanently-red, therefore-ignored gate into one that blocks the
  *next* regression. `check_complexity` caught three real regressions within an hour of shipping,
  including one of mine.
- **One cluster, one commit, full suite green, baseline re-frozen with the diff reviewed.**
  `--update-baseline` is deliberately explicit so somebody reads the diff.
