# Design: Mutation Campaign Corpus and Session Gate

- **Feature ID**: TECH-049
- **Phase**: 7
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_design.md

## Feature Overview

TECH-049 turns one-shot mutation probing into a persistent, scheduled measurement of whether the
test suite still notices its requirements disappearing. It solves the fact that campaigns are
ad-hoc and uncommitted, reports are discarded so drift cannot be detected, the runner returns `0`
even when every mutant is `BROKEN`, and nothing schedules any of it. It interacts with
`scripts/_mutate.py`, `scripts/_mutate_campaign.py`, `scripts/_citations.py` and the
`scripts/baselines/` ratchet pattern, and does **not** touch `src/specweaver/`, any commit gate, or
mutant generation. Key constraints: dev tooling only; a full corpus must stay affordable; nothing
blocks on a surviving mutant without a human.

> **Track.** This is how *we* build SpecWeaver. `A-VAL-03` (Mutation Testing Gates) is a **product
> capability** run against a *user's* codebase. Overlapping subject, different deliverable — nothing
> here is blocked on it, nothing here belongs in it. See *Intake for A-VAL-03*.

## Research Findings

### Codebase Patterns

Everything except persistence, scheduling and evaluation already exists and works.

| Exists | What it gives |
|---|---|
| `scripts/_mutate.py` | Detached-worktree sandbox, uncommitted-work carry-over, isolation proof, anchor application, kill/survive classification |
| `scripts/_mutate_campaign.py` | Batch over one reused sandbox, `git checkout --` between mutants, report ordered by what needs action |
| `scripts/_citations.py` | `Proves: <STORY-ID> FR-n` grammar, already consumed by `check_fr_coverage.py` |
| `scripts/baselines/*.json` + `check_suppressions.py` | The ratchet pattern: a bypass is an entry, counts may fall and never rise, re-freeze is a reviewable diff |
| `scripts/quality.py` | Gate registration (`CHECKS` dict, gate→scope), `--json`, exit codes |

Measured during research, and they set the design's shape:

- One mutant, full suite: **71.73 s**. Same mutant scoped to its test file: **1.24 s** (~58×).
- A fresh sandbox collects **6952/6983** — the whole suite. CLAUDE.md's 4m26 figure is stale.
- **575 requirements** today (347 FR + 228 NFR) across 55 design docs; ~1,400 at full roadmap.
- **35 of 554** test files carry a strict `Proves:` tag (6.3%). Tags cannot gate anything.
- No cron, no systemd timer, no scheduled workflow; `.github/workflows/` holds only an image build,
  and there are no git hooks. **Nothing runs automatically.**

Boundary rules: `scripts/` is dev tooling outside the `tach` module graph, so no `consumes`/`forbids`
rule constrains this. It must not import from `src/specweaver/` — three of 37 scripts do, and none
of them for this purpose.

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Python stdlib `ast` | 3.11+ | `ast.parse`, `ast.dump`, `node.lineno`/`end_lineno` | stdlib |
| pytest | as pinned | `-r` short summary; `should_do_markup` env precedence | `.venv/lib/.../_pytest` |
| git | any | `worktree add --detach`, `checkout --`, `status --porcelain` | already used |

### Blueprint References

`future_capabilities_reference.md` §14 (diff-only mutation) describes a **different execution model**
— inline and pre-commit-shaped, with a 5-minute timeout. It belongs to `A-VAL-03`, not here.
Google's *Practical Mutation Testing at Scale* independently reaches this design's stance: report in
review, never block, because equivalent mutants are 4–39% of all mutants and equivalence is formally
undecidable.

## Functional Requirements

> **Amended 2026-08-15, after approval.** `FR-1a` was added during SF-01 planning: mutant ids were
> unique only within a campaign, which is not enough for `FR-11a` recurrence counts or `FR-12`
> override entries to name the same mutant across runs. Additive and pre-delivery, so
> `finished-stories-immutable` does not attach; recorded here rather than silently folded in.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Campaign corpus | Loader | The system SHALL load a per-feature `<ID>_mutants.json` declaring `schema` and `feature`, and per campaign a `requirement`, `scope` and one or more `mutants`, rejecting a malformed file **before** any sandbox work | Campaigns are version-controlled beside the design they test, and an unusable corpus fails loudly at parse time |
| FR-1a | Stable mutant identity | Loader | The system SHALL **derive** a project-unique mutant id as `<feature> <requirement> <id>` (e.g. `C-EXEC-06 FR-8 isolation-off`), never accept one hand-typed, and SHALL reject a corpus containing a duplicate | Recurrence counts (FR-11a), override entries (FR-12) and cross-run comparison address the same mutant across runs without drifting |
| FR-2 | Drift detection | Hasher | The system SHALL record a `symbol_sha` over the **normalised AST** (`ast.dump`, line numbers stripped) of the smallest enclosing named node, and report `STALE` when it no longer matches or the symbol is absent | A refactor that moves the code a claim rests on is reported as such, not as a coverage finding |
| FR-3 | Session baseline | Runner | The system SHALL run the full suite **once** per session and record the collected count and the **node id of every failing test**; a failing baseline SHALL NOT stop the run | Results are interpretable, and a tree that was already red cannot masquerade as mutation findings |
| FR-3a | Baseline attribution | Evaluator | The system SHALL mark a mutant `INDETERMINATE` **only when a baseline failure falls inside that campaign's `scope`** | One unrelated red test cannot void the whole session, and a genuinely tainted campaign cannot pass |
| FR-4 | Scoped execution | Runner | The system SHALL run each mutant only against its campaign's declared `scope`, and SHALL fail the mutant when **0 tests are collected** | Cost falls ~58×, and a mis-typed scope can no longer read as a survival |
| FR-5 | Verdict assignment | Evaluator | The system SHALL assign exactly one of `PASS`, `FAIL`, `INDETERMINATE`, `STALE` per the verdict table, requiring an **in-scope killer** for `PASS` | A bystander kill stops counting as proof of the requirement |
| FR-6 | Kill confirmation | Runner | The system SHALL re-run the killers **without** the mutant before recording `PASS` | A flaky test can no longer read as protection |
| FR-7 | Sandbox hygiene | Runner | The system SHALL reset the mutated file and verify the sandbox is clean (`git status --porcelain` empty) between mutants | State written by one mutant's tests cannot leak into the next |
| FR-8 | Accounting | Evaluator | The system SHALL fail a campaign when verdicts returned ≠ mutants declared, and SHALL rate a campaign `FAILED` on any `FAIL`, `PARTIAL` when the only non-passes are `INDETERMINATE` or `STALE`, else `PASSED` | Crashes, interrupts and silent skips surface instead of reading as a clean run, and an unreadable result is not scored as a defect |
| FR-9 | Single report | Reporter | The system SHALL write one `.tmp/mutation_report.json` with a `summary` block first, **self-contained** — no path into the sandbox in any field, captured output included — and exit `0` no-fail / `1` any-fail / `2` could-not-run | A machine can evaluate the run after the sandbox is gone |
| FR-10 | Scheduler | Host | The system SHALL run the whole corpus on a schedule without human invocation | A measurement nobody triggers is a measurement nobody makes |
| FR-11 | Session gate | Gate | The system SHALL block on any unconfirmed finding and release once every finding carries a **confirmation with a disposition** (`real-gap` · `equivalent` · `will-fix` · `stale-refreshed`). It SHALL NOT require a re-run to prove a fix, and SHALL treat a missing or stale report as blocking | Findings get read rather than accumulating, without paying for an on-demand corpus run; the next scheduled run re-measures anyway |
| FR-11a | Repeat findings | Reporter | The system SHALL mark a finding that recurred in consecutive runs with the number of runs it has survived | A `will-fix` that never got fixed is visible instead of being re-confirmed forever |
| FR-12 | Override census | Gate | The system SHALL permit a human override **per (N)FR**, only as a recorded entry naming requirement, person, reason and promise, ratcheted so the count may fall and never rise | A bypass stays visible and narrow; a silent `--force` turns the gate into decoration |
| FR-14 | Usage | Author | The system SHALL document how a campaign is written and how the morning gate is cleared, in the skills that govern development and in `CLAUDE.md` | A gate nobody knows how to clear blocks work until it is switched off |
| FR-13 | Corpus maintenance | Author | The system SHALL provide an explicit, reviewable way to refresh a mutant's `symbol_sha` after its claim has been re-verified and to retire a campaign whose requirement was descoped, and SHALL NOT refresh either automatically | `STALE` has a resolution path, a descoped requirement stops reporting forever, and drift detection cannot be defeated by a silent rewrite |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | Campaign parse + validation precedent | `_mutate_campaign` · `load_campaign(path) -> list[dict]`, `_REQUIRED` tuple | read `scripts/_mutate_campaign.py:63-79` |
| FR-2 | Enclosing-symbol boundaries | stdlib `ast` · `node.lineno` / `node.end_lineno`, `ast.dump(node)` | read `scripts/_mutate.py:77-92` for anchor semantics; stdlib API |
| FR-3 | Sandbox built once, reused | `_mutate` · `_build_sandbox(sandbox)`, `run_one(...)` reuses it | read `scripts/_mutate.py:129-151`, `:181-215` |
| FR-4 | Per-mutant test target; colour-free output | `_mutate` · `run_one(sandbox, *, file, old, new, tests, fast)`, `sandbox_env(sandbox)` | read `scripts/_mutate.py:181-215`, `:176-190` |
| FR-5 | Killer ids and broken-run detection | `_mutate` · `killers(output)`, `is_broken(output)`, `_plain(output)` | read `scripts/_mutate.py:95-115` |
| FR-5 | Which tests cite a requirement | `_citations` · `strict_citations(text) -> dict[str, set[str]]` | read `scripts/_citations.py:38-60` |
| FR-7 | Reset between mutants | `_mutate` · `reset_file(sandbox, file)` (`git checkout --`, one file only) | read `scripts/_mutate.py:218-220` |
| FR-9 | Report ordering precedent | `_mutate_campaign` · `render_report(results, meta)`, `_ORDER`, `_bucket()` | read `scripts/_mutate_campaign.py:82-147` |
| FR-11 | The report to gate on, and the ledger of dispositions | `_mutation_report` · `.tmp/mutation_report.json`; `scripts/baselines/mutation_findings.json` | read `scripts/_mutation_report.py`, `scripts/baselines/suppressions.json` |
| FR-12 | Ratchet mechanics | `check_suppressions` · frozen baseline JSON, `--update-baseline`, fail-on-growth | read `scripts/check_suppressions.py:1-30`, `scripts/baselines/suppressions.json` |

**Outcome of the fixpoint.** Every row converged on a surface that exists. Two rewrote an FR:
FR-7 gained the sandbox-clean assert once `reset_file` proved to reset **one file only**; FR-4
gained the collected-count assert once `run_one` proved to have no zero-collection guard.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Corpus runtime | **≤ 4 s per mutant end-to-end**, counting the mutated run *and* FR-6's confirmation re-run. Expressed per mutant on purpose: a campaign holds several mutants, so an absolute wall-clock target silently assumes a mutants-per-requirement ratio nobody has measured. Measured basis: 1.24 s for a scoped mutated run. At ~511 campaign-able requirements and 3 mutants each, ≤ 4 s/mutant puts a full corpus near 100 min — an input to AD-8, not a contradiction of it. |
| NFR-1a | Baseline runtime | The once-per-session full-suite baseline completes in **≤ 10 min**. Measured: a fresh sandbox collects 6952/6983 in a 71.7 s full-suite mutant run. |
| NFR-2 | Colour-free pipeline | `PY_COLORS=0` in the sandbox environment; parsers strip SGR before matching. Already delivered in `72b82df8`. |
| NFR-3 | Report survives teardown | No value in `mutation_report.json` may contain a sandbox path — **including captured pytest output**, which carries absolute sandbox paths in tracebacks and must be rewritten to repo-relative before it is stored. The sandbox is a detached worktree deleted at end of run. |
| NFR-4 | Baseline economy | The full suite runs **once** per session, never per mutant. |
| NFR-5 | Override visibility | Override count may fall, never rise. Re-freeze is an explicit flag producing a reviewable diff. |
| NFR-6 | Gate isolation | No `quality.py` gate (`quick`/`cb`/`sf`/`feature`/`doc`) may invoke the session gate. **[proof: meta — rule about the diff]** |
| NFR-7 | No product coupling | No code added here carries a **module-level** `import specweaver.*`. Stated precisely because `_mutate.py` already contains the string inside its isolation probe — `python -c "import specweaver.core as m"` runs in the sandbox subprocess and is not a coupling. A naive grep would score that a violation. **[proof: arch — import check, not pytest]** |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Python stdlib `ast` | 3.11 | `parse`, `dump`, `lineno`, `end_lineno` | Y | No third-party mutation library is introduced |
| pytest | as pinned | short summary, `PY_COLORS` | Y | Env precedence read in `_pytest/_io/terminalwriter.py` |
| git | 2.x | `worktree`, `checkout`, `status` | Y | Already relied on by the runner |
| Scheduler host | — | — | **N — open** | GitHub Actions vs systemd timer vs cron is undecided (AD-8) |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Mutation detects **drift**, not test-sequencing | Red-first TDD stays primary. Mutation answers "does anything still notice", never "was this red first" | No |
| AD-2 | Mutants are deliberate, one isolated (N)FR each | Random generation is `A-VAL-03`; a hand-authored mutant carries the intent a generated one cannot | No |
| AD-3 | **One corpus file per feature**, beside the design | One per requirement is 575 files now and ~1,400 later. Per-feature is 55 → ~149, and scopes ids that are unique per feature but **not repo-wide** | No |
| AD-4 | `symbol_sha` only, over the normalised AST | Git blob hash and file hash are the same thing, so that was never the axis; at ~11 min per corpus a skip mechanism buys nothing. Raw-text hashing would mark everything stale after one `ruff format` | No |
| AD-5 | Scoping is **semantics**, not optimisation | `PASS` requires an in-scope killer, so out-of-scope kills were never going to count. The 58× saving is a consequence | No |
| AD-6 | Baseline once per session; red baseline yields `INDETERMINATE` | Halting on a red tree throws away every other campaign's information | No |
| AD-7 | **Nothing blocks on a survival automatically** | Equivalent mutants are 4–39% of mutants and equivalence is undecidable — a blanket block carries that as a false-failure floor. Consistent with the campaign tool's existing "a report is an input to a decision" stance | No |
| AD-8 | Scheduler host: **systemd timer** on the dev box | Approved by Steve Bula, 2026-08-15. The runner deliberately carries uncommitted work into the sandbox via `git diff HEAD`, and a hosted runner throws that away — it would measure a different tree than the one being worked on. A ~100 min nightly corpus is free locally and billed on a hosted runner, and there is no CI here to extend | Yes — approved by Steve Bula on 2026-08-15 |
| AD-10 | The gate **confirms** findings; it does not require a re-run | Approved by Steve Bula, 2026-08-15. Requiring proof-of-fix before continuing would mean re-running the corpus on demand, which is the inline model this design rejects. The next scheduled run re-measures anyway, so a finding confirmed and not fixed simply reappears — self-correcting at zero cost | No |
| AD-9 | Override is a ratcheted census entry, not a flag | For an agent under a gate, a silent bypass is the cheapest correct solution. `check_suppressions.py` exists because of exactly that | No |

## ROI Analysis

### Investment Cost

| Item | Effort | Risk |
|------|--------|------|
| Corpus format + loader + `symbol_sha` | Medium | Low — `load_campaign` is the template |
| Runner semantics (baseline, scope, hygiene, accounting) | Medium | Medium — touches the isolation path that already produced two silent-scope bugs |
| Report | Low | Low |
| Scheduler | Low | Medium — no host decided; nothing in the repo to copy |
| Gate + override census | Medium | Low — `check_suppressions.py` is the template |

### Returns

| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| Every delivered requirement | Drift is detected: "killed in July, survives today" becomes askable | High — currently unaskable |
| `check_fr_coverage.py` ledger | Attribution gains a strength signal beside it | High |
| Feature work | Findings block by default rather than accumulating unread | Medium |
| `A-VAL-03` | Ships against measured cost and a proven verdict model | High |

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Corpus rots — campaigns written once, never maintained | High | High | `STALE` is a first-class verdict (FR-2), surfaced in the report, not silently skipped |
| Gate becomes noise and is overridden by habit | Medium | High | AD-9 ratchet — the count may fall and never rise, so habitual bypass is visible |
| Scoped run hides a real killer | Low | High | FR-5 requires an in-scope killer for `PASS` by definition; FR-4 fails on zero collection |
| Another silent-scope bug in the sandbox path | Medium | High | FR-4 collected-count assert; the isolation proof already exists and is unchanged |
| Nightly run silently stops running | Medium | Medium | FR-9 report carries `head` and timestamps; gate treats a missing/stale report as `FAIL` |

### Refactoring Opportunities

| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `_mutate_campaign.py` | Returns `0` unconditionally; markdown-only output | Gains verdicts, accounting and a machine report | Medium |
| `check_fr_coverage.py` | Proves attribution, never strength | A corpus verdict sits beside each citation | Low — read-only pairing |
| `scripts/baselines/` | Ratchet pattern used by 5 checks | One more consumer, no change to the pattern | Low |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Guide-1 | Writing a mutation campaign — choosing a mutant that breaks one (N)FR, declaring scope, reading verdicts | ✅ `docs/dev_guides/writing_mutation_campaigns.md` (SF-01; verdict half lands with SF-03) |

## Sub-Feature Breakdown

### SF-01: Campaign Corpus and Drift Hashing
- **Scope**: The on-disk format, its loader and validation, derived mutant identity, `symbol_sha` computation, and the explicit refresh/retire path.
- **FRs**: [FR-1, FR-1a, FR-2, FR-13]
- **Inputs**: `<ID>_mutants.json` files beside feature designs; source files named by mutants.
- **Outputs**: Validated campaign objects with drift state; `STALE` determination.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf01_implementation_plan.md

### SF-02: Session Baseline and Scoped Execution
- **Scope**: Run the suite once per session; run each mutant against its declared scope in a clean sandbox.
- **FRs**: [FR-3, FR-4, FR-7]
- **Inputs**: Validated campaigns from SF-01; a detached-worktree sandbox.
- **Outputs**: Per-mutant raw run results with collected counts; baseline health record.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf02_implementation_plan.md

### SF-03: Verdicts, Confirmation and Accounting
- **Scope**: Attribute baseline failures to scope; turn raw results into verdicts; confirm kills; enforce the declared-vs-returned rule.
- **FRs**: [FR-3a, FR-5, FR-6, FR-8]
- **Inputs**: Raw run results and baseline failure node ids from SF-02; citations from `_citations.py`.
- **Outputs**: Per-mutant verdicts and per-campaign verdicts.
- **Depends on**: SF-02
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf03_implementation_plan.md

### SF-04: Machine Report
- **Scope**: One self-contained JSON report, summary first, with exit codes.
- **FRs**: [FR-9]
- **Inputs**: Verdicts from SF-03; session metadata.
- **Outputs**: `.tmp/mutation_report.json`; process exit code.
- **Depends on**: SF-03
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf04_implementation_plan.md

### SF-05: Scheduler
- **Scope**: Run the corpus unattended nightly via a systemd timer on the dev box (AD-8).
- **FRs**: [FR-10]
- **Inputs**: The repository working tree, uncommitted work included.
- **Outputs**: A report produced without human invocation.
- **Depends on**: SF-04
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf05_implementation_plan.md

### SF-06: Session Gate and Override Census
- **Scope**: Block on unconfirmed findings, release on confirmation with a disposition, track recurrence, and carry a ratcheted human override.
- **FRs**: [FR-11, FR-11a, FR-12]
- **Inputs**: `.tmp/mutation_report.json`; prior run results; the override baseline.
- **Outputs**: A session verdict; per-finding dispositions; recurrence counts; a ratcheted override census.
- **Depends on**: SF-04
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf06_implementation_plan.md

### SF-07: Adoption
- **Scope**: Make the gate usable — skills, the morning routine, and the command in `CLAUDE.md`.
- **FRs**: [FR-14]
- **Inputs**: The gate delivered by SF-06.
- **Outputs**: Updated skills and guides; a documented daily routine.
- **Depends on**: SF-06
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf07_implementation_plan.md

## Execution Order

1. SF-01 (no deps — start immediately)
2. SF-02
3. SF-03
4. SF-04
5. SF-05 and SF-06 in parallel (both depend only on SF-04)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Campaign Corpus and Drift Hashing | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Session Baseline and Scoped Execution | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Verdicts, Confirmation and Accounting | SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | Machine Report | SF-03 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-05 | Scheduler | SF-04 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-06 | Session Gate and Override Census | SF-04 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-07 | Adoption | SF-06 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Verdict Table

"Baseline" here means **the baseline result restricted to this campaign's `scope`** (FR-3a) — a
failing test elsewhere in the suite does not taint a campaign that does not run it.

| Baseline ∩ scope | After mutation | Verdict |
|---|---|---|
| green | red, killer **in scope** | `PASS` |
| green | red, no in-scope killer | `FAIL` — bystander; requirement unproven |
| green | green | `FAIL` — requirement not protected |
| **red** | anything | `INDETERMINATE` — unreadable |
| — | anchor will not apply | `STALE` — the code moved |
| — | 0 tests collected | `FAIL` |

Campaign verdict (FR-8): `FAILED` on any `FAIL`; `PARTIAL` when the only non-passes are
`INDETERMINATE` or `STALE`; otherwise `PASSED`. Verdicts returned must equal mutants declared.

### Scope versus citations

`scope` in the campaign is **authoritative** — only 35 of 554 test files carry a `Proves:` tag, so
citations cannot gate anything. Where both exist and disagree, the run records a `scope_drift`
note against the campaign and continues. It is a finding for a human, never a verdict: either the
tag is stale or the scope is, and only a reader can say which.

### Exit code versus gate

They answer different questions and must not be conflated. **FR-9's exit code reports the health of
the run** — did it complete, did anything fail. **FR-11's gate is a separate decision** that consumes
the report, applies the override census, and rules on whether feature work continues. The scheduler
reads the exit code; the human reads the gate.

## Non-Goals

- **Mutant generation from an AST** — `A-VAL-03`. Every entry stays hand-authored, so the format must
  remain writable by a person.
- **Any commit-gate integration** (NFR-6).
- **Blocking on a surviving mutant automatically** (AD-7).
- **Answering the red-first question.** The original TECH-049 framing asked whether a test was red
  before the code it covers. Mutation measures drift, not sequencing — that gap and `TECH-025` NFR-3
  remain **unowned**, and this design does not close them.
- Retrofitting campaigns onto delivered stories. The corpus grows as campaigns are written.

## Intake for `A-VAL-03`

Carry forward rather than re-derive: the cost figures (71.73 s full-suite vs 1.24 s scoped per
mutant), the 4–39% equivalent-mutant floor and its consequence (AD-7), scoping-as-semantics (AD-5),
baseline-once-per-session (AD-6), the accounting rule (FR-8), and the verdict table.

## Session Handoff

**Current status**: Design **APPROVED** 2026-08-15 (Steve Bula), with AD-8 resolved to a systemd
timer and AD-10 setting the gate to confirm-not-rerun. The blocking runner defect was already
delivered in `72b82df8` — it reported every mutant `SURVIVED` under a colour-forcing shell.
**Open decisions**: none.
**Next step**: SF-01 to SF-06 are delivered — the mechanism is complete and runs end to end. Only
SF-07 (Adoption) remains: until the skills describe how to write a campaign and clear the morning
gate, the gate works and nobody knows how to use it.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and
resume from there using the appropriate skill.
