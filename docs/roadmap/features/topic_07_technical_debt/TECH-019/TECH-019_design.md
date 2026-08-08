# Design: Skill Instruction Integrity — Dangling Doc References and Contradictory Gate Orders

- **Feature ID**: TECH-019
- **Epic**: Topic 07 (Technical Debt)
- **Status**: COMPLETE
- **Origin**: found by the INT-US-21 SF-02 CB-1 pre-commit gate, 2026-07-26
- **Designed**: 2026-08-08

## Problem Statement

Skill instructions are not checked against the repository they instruct on, so they rot silently and
the agent absorbs the rot as truth.

### Defect 1 — twelve dangling references across six live instruction files

`TECH-008` modularized `docs/architecture/architecture_reference.md` into
`docs/architecture/{01..07}_*/` and deleted the file. Six **live** instruction sites still order the
agent to read it. Research for this design found four more dangling references of the same class,
all in `specweaver-pre-commit/references/phase-6-documentation.md`, all under a bullet reading
"**MANDATORY**: You MUST explicitly open, read, and update ALL of the following":

| # | File | Site | Dangling reference | Repair |
|---|---|---|---|---|
| 1 | `.agents/AGENTS.md` | 46 | `docs/architecture/architecture_reference.md` | → `03_system_topology/module_dependency_graph.md` + `hard_dependency_rules.md` |
| 2 | `specweaver-design/references/phase-2-research.md` | 24 | same | → the six numbered docs its own focus-list names |
| 3 | `specweaver-implementation-plan/references/phase-1-preparation.md` | 20 | same | → the five numbered docs its own focus-list names |
| 4 | `specweaver-implementation-plan/references/phase-3-architecture.md` | 22 | `architecture_reference.md` | → `03_system_topology/context_yaml_spec.md` + `hard_dependency_rules.md` |
| 5 | `specweaver-pre-commit/references/phase-1-architecture.md` | 13 (§1.1) | `docs/architecture/architecture_reference.md` | → `README.md` hub + the four docs §1.1–§1.7 actually use |
| 6 | same | 64 (§1.8) | same, **as the place to record new boundary violations** | → `06_lessons_and_future/known_boundary_violations.md` |
| 7 | same | 36 (§1.4) | "Feature Map in the architecture reference" | → `02_bounded_contexts/legacy_feature_map.md` |
| 8 | `specweaver-pre-commit/references/phase-6-documentation.md` | 27 | `docs/architecture/architecture_reference.md` | → `docs/architecture/README.md` + the numbered tree |
| 9 | same | 12 | `docs/testing_guide.md` | → `docs/dev_guides/testing_guide.md` (the real path) |
| 10 | same | 11, 14, 28 | `docs/quickstart.md`, `docs/developer_guide.html` ×2 | **delete the lines** — no such file has ever existed |

Ten of the twelve are mechanically enforceable by the checker. Two are not, and are repaired by hand
in SF-01 without becoming FR-4 obligations: site 4 references `architecture_reference.md` as a bare
basename, and site 7 names the Feature Map in prose with no path at all. Neither shape can be
resolved to a disk location by any rule that keeps NFR-1.

Every design, implementation-plan and pre-commit run since `TECH-008` has been instructed to load
architecture context that cannot be loaded. Two failure modes, both bad: the agent silently skips
the step the phase depends on, or it fills the gap from training data and reports architecture facts
it never read. Site 6 is worse than a dead read — it directs *new* boundary-violation records into a
nonexistent file, so they are written nowhere.

The `docs/architecture/README.md` hub is **not** a drop-in replacement for any of these sites. It is
a module tree and nothing else: it carries no dependency rules, no archetypes, no anti-patterns and
no feature map. Repointing every site at the hub would trade a loud failure (file missing) for a
silent one (file present, content absent). Each site is therefore repaired to the specific numbered
document that holds what that phase asked for:

| Content the instructions ask for | Now lives in |
|---|---|
| module map | `03_system_topology/module_dependency_graph.md` |
| dependency rules (`consumes`/`forbids`) | `03_system_topology/hard_dependency_rules.md` |
| archetypes | `01_foundational_principles/archetypes.md` |
| Known Boundary Violations | `06_lessons_and_future/known_boundary_violations.md` |
| Feature Map | `02_bounded_contexts/legacy_feature_map.md` |
| Anti-Patterns | `06_lessons_and_future/anti_patterns.md` |
| `context.yaml` schema | `03_system_topology/context_yaml_spec.md` |

### Defect 2 — two pre-commit phases give contradictory format orders

- `phase-1-architecture.md` §1.9: *"FORMAT EXCEPTION: You MUST NOT write this combined analysis into
  a file or system Artifact! You MUST print … DIRECTLY into your conversational chat response."*
- `phase-2-test-gap.md` §2.8: *"You MUST write the test gap analysis into a system Artifact … You
  MUST NOT print the Coverage Matrix or Test Stories directly into your conversational chat
  response."*

Both govern the same output at the same moment — the combined analysis presented at the end of
Phase 2 — and both are marked MUST. Whichever the agent picks, it violates an instruction marked
MUST, so compliance is a coin flip and the transcript record of *why* is lost.

**Which is stale, decided on blame evidence.** The stub asserted "§1.9 relocated the gate and §2.8
was never updated". The git record reverses this: `phase-1-architecture.md` has exactly **one**
commit (`24de5e19`, 2026-07-11) and has not been touched since, while `phase-2-test-gap.md` has been
edited **four** times after that date (latest `59813b9c`, 2026-07-31), each editor leaving the
Artifact mandate standing. §1.9 is the frozen instruction; §2.8 is the maintained one. §2.8 also
states a reason §1.9 does not: the user needs the Artifact to leave line-by-line comments.

**Resolution (HITL-approved 2026-08-08):** §2.8 wins. §1.9's FORMAT EXCEPTION block is deleted and
replaced by a pointer naming §2.8 as the single format authority. The loser is removed, not left
alongside.

## Functional Requirements

| ID | Requirement |
|---|---|
| **FR-1** | Every repo-rooted path referenced in a live instruction file resolves to a file on disk. |
| **FR-2** | Boundary violations that cannot be fixed in scope are recorded in `06_lessons_and_future/known_boundary_violations.md`, the live ledger. |
| **FR-3** | Exactly one instruction governs the format of the pre-commit combined analysis; the contradicting one is deleted. |
| **FR-4** | `scripts/check_skill_references.py` fails when a live instruction file references a repo-rooted path that does not resolve, and names the file, line and reference. |
| **FR-5** | The checker does not flag things that are not assertions about a path on disk: bracket/angle/glob templates (`[ID]`, `<skill-name>`, `topic_*.md`), uppercase stand-in tokens (`US-NN_integration.md`), bare basenames, and allowlisted worked examples. |
| **FR-6** | The checker runs as part of the standard quality gate, so a doc refactor that breaks a reference is caught at the commit that breaks it. |

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| **NFR-1** | The checker's false-positive rate on the current tree is **zero, measured**. A checker that cries wolf is switched off within a day, and a naive "every backticked path must resolve" rule flags 34 distinct references of which 4 are real — an 88% false-positive rate. |
| **NFR-2** | Failure output names the file, the line number and the unresolved reference, so the fix needs no second search. |
| **NFR-3** | Runs in under a second over the instruction tree; it is in the per-commit gate. |
| **NFR-4** | Both skill trees (`.agents/` and `.claude/`) are scanned or provably identical. `check_skill_sync.py` measured them as **separate files, not hardlinks** (2026-07-25); the stub's claim that "one edit covers both" is wrong, so repairs must land in both and be verified by that checker. |

## The Checker's Rule (FR-4/FR-5/NFR-1)

A path-shaped token — inline-backticked, fenced, or bare in prose — is **enforced** only when all
five hold:

1. it contains `/`; and
2. its first segment is a real top-level entry of the repo (`docs`, `src`, `tests`, `scripts`,
   `specs`, `.agents`, `.claude`); and
3. it contains no placeholder metacharacter (`[`, `<`, `*`, `{`); and
4. no path segment is an uppercase stand-in token (`NN`, `XX`, `ID`, `N`, `SFxx`); and
5. it is not in `EXAMPLE_ALLOWLIST`, which carries a stated reason per entry (same pattern as
   `check_story_preconditions.py`'s `DEAD_PROMISE_ALLOWLIST`).

Anything else is ignored by construction. Rule 2 excludes shorthand like `flow/models.py`, rule 3
excludes templates like `docs/roadmap/features/[Topic]/[ID]/[ID]_design.md`, and requiring a `/`
excludes bare basenames such as `check_fr_coverage.py`, which name a real file without asserting
where it lives.

Rules 4 and 5 exist because they were **measured into existence**, not anticipated. Rules 1–3 alone
produced two false positives on the live tree: `docs/roadmap/topics/topic_08_integration/US-NN_integration.md`
(a template whose placeholder is `NN`, not a metacharacter) and `tests/unit/test_foo.py` ×4 (a
stand-in filename in `specweaver-dev`'s TDD walkthrough). With all five rules the scan returns
**exactly the 10 enforceable sites of Defect 1, 4 distinct references, and nothing else** — 73
path-shaped tokens are ignored as non-assertions. NFR-1 is therefore a measurement, not a hope.

Scanning must cover fenced blocks and prose, not only inline backticks: the §1.1 site
(`phase-1-architecture.md:13`) sits inside a ``` fence and a backtick-only scan misses it.

The trade is deliberate and worth stating: shorthand and basename references are **not** enforced,
so a broken `flow/models.py` still slips through. Enforcing them needs a resolution convention that
does not exist yet, and inventing one here would cost the zero-false-positive property that makes
the checker survivable. FR-1 is scoped to repo-rooted paths for that reason.

## Non-Goals

- Not a rewrite or reorganization of the skills. References and one contradiction only.
- Not a sweep of historical documents. Implementation plans and delivered design docs that mention
  `architecture_reference.md` are **records of what was true then** and must not be edited
  (finished-stories-immutable). The checker scans live instruction trees only, never
  `docs/roadmap/features/`.
- Not the duplicate `6.3` section numbering in `phase-6-documentation.md` (two sections share the
  number). Real, but a different defect class; file separately if it matters.
- Not enforcement of shorthand or basename references — see the trade above.

## Sub-Features

### SF-01 — Repair the references and reconcile the format orders

Docs only. Repairs all 12 dangling references per the Defect 1 table, deletes §1.9's FORMAT
EXCEPTION in favour of §2.8, and mirrors every edit into both skill trees. Lands first so that the
checker is green on the commit that introduces it — a guardrail that arrives red teaches the team to
ignore it.

### SF-02 — Ship the guardrail

`scripts/check_skill_references.py` implementing the rule above, its unit tests, and wiring into
`scripts/quality.py` so it runs in the standard gate. Depends on SF-01.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Repair references + reconcile format orders | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | `check_skill_references.py` guardrail | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Verifiable Proof

- `tests/unit/scripts/test_check_skill_references.py` — the checker's rule, including the
  false-positive classes of FR-5 and a live-tree assertion that FR-1 holds for the whole
  instruction tree.

## Session Handoff

**Current status**: Design approved 2026-08-08. Phase 0 precondition gate green.

**Blocker cleared during Phase 0**: `check_story_preconditions.py`'s dead-promise scan counted only
`.field =` and `Class(field=...)` as writes, making it structurally blind to
`model_copy(update={...})` — the *only* legal write on a frozen Pydantic model, and the idiom this
codebase requires for the models the engine copies per step. It reported `PlanContext.plan` and
`.decomposition` as dead promises although `hydration.py` has written both since INT-US-21 SF-02.
That false failure blocked **every** story behind a gate with no override. Fixed test-first; the
`(set by runner hook)` comments in `handlers/base.py` were corrected to name `hydrate_plan_context`,
which is what actually writes them.

**SF-01 delivered** (commit `ffaa4a8b`, 2026-08-08). 15 edits across both skill trees; the
dangling-reference scan went 10 sites → 0, `check_skill_sync.py` reports 0 drift, and the full
suite passed 6228. Three extra repairs were made in `phase-6-documentation.md` beyond the plan's
edit table — its frontmatter and §6.3 heading still advertised `quickstart` and the developer
guide after those bullets were deleted, which is the same defect class.

**SF-02 delivered** (commit `fdc4eac2`, 2026-08-08). `scripts/check_skill_references.py` + 17 tests
+ a `doc`-gate row. Verified by injecting a dangling reference and observing exit 1 with
file/line/reference before reverting — a guardrail never seen failing is not known to work.

**Feature COMPLETE.** Closure gate green: `check_fr_coverage.py TECH-019` reports all 6 FRs planned
and cited; `tests.py feature TECH-019 --kind tooling` exits 0; full suite 6242 passed.

FR-2, FR-3 and FR-6 initially failed the FR ledger — delivered but unproven, because SF-01 was
documentation and SF-02's tests only covered the checker. Rather than descope them, three
regression guards were added: the boundary-violation ledger is the one §1.8 names, exactly one
instruction states the combined-analysis format, and the checker is registered in the `doc` gate.
That also closes the gap SF-01 knowingly accepted — its repairs now have automated protection.

**Known and deliberately not fixed**: `quality.py cb` fails `complexipy` and `cycles`. `src/` was
byte-identical to HEAD throughout this work, so both are inherited — they are `TECH-023` and
`TECH-024`, which this roadmap ranks #7 and #6 against TECH-019's #1, and which must not share a
working tree.

**Next step**: nothing for TECH-019. Per the debt order, `TECH-025` is #2.

**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume
from there using the appropriate workflow.
