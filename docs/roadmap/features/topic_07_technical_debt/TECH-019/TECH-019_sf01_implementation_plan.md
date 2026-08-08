# Implementation Plan: Skill Instruction Integrity [SF-01: Repair references + reconcile format orders]

- **Feature ID**: TECH-019
- **Sub-Feature**: SF-01 — Repair the references and reconcile the format orders
- **Design Document**: `docs/roadmap/features/topic_07_technical_debt/TECH-019/TECH-019_design.md`
- **Design Section**: §Sub-Features → SF-01
- **Implementation Plan**: `docs/roadmap/features/topic_07_technical_debt/TECH-019/TECH-019_sf01_implementation_plan.md`
- **Status**: APPROVED

## Scope

Covers **FR-1**, **FR-2**, **FR-3**. Documentation only — no source file is touched, no import is
added, no test is changed. FR-4/FR-5/FR-6 belong to SF-02.

**FR-1's proof arrives with SF-02** (HITL-approved 2026-08-08). SF-02 does red/green on fixtures and
carries the live-tree assertion, which is green on arrival precisely because this sub-feature landed
first. No commit is ever red, and the feature-level closure gate is what proves FR-1.

## Mandatory Procedure: Edit Both Skill Trees

`.agents/skills/` and `.claude/skills/` are **separate files**, not hardlinks — measured at plan
time: `nlink == 1` on both sides of a sampled pair, and `check_skill_sync.py` reports 27 files with
0 drift. The design stub's claim that "those trees are hardlinked, so one edit covers both" is
false, and acting on it would repair the instructions for Claude Code while leaving Gemini and
Antigravity reading the rotted copies.

For every edit below:

1. Apply it under `.agents/skills/…`.
2. Apply the identical edit under `.claude/skills/…`.
3. Finish the boundary with `python scripts/check_skill_sync.py` — it must report `0 error(s)`.

`.agents/AGENTS.md` is single-copy (there is no `.claude/AGENTS.md`), so it is edited once.

> Claude Code mirrors the two trees bidirectionally while running, which can make step 2 look like a
> no-op. Do not rely on that — it is harness behaviour, not a repo guarantee, and it is exactly what
> `check_skill_sync.py`'s own header warns about. Step 3 is the verification that matters.

## Edit Table — FR-1 / FR-2

Content mapping (from the design's research): module map →
`03_system_topology/module_dependency_graph.md`; dependency rules →
`03_system_topology/hard_dependency_rules.md`; archetypes →
`01_foundational_principles/archetypes.md`; Known Boundary Violations →
`06_lessons_and_future/known_boundary_violations.md`; Anti-Patterns →
`06_lessons_and_future/anti_patterns.md`; `context.yaml` schema →
`03_system_topology/context_yaml_spec.md`; Feature Map →
`02_bounded_contexts/legacy_feature_map.md` (historical — see E7).

All paths below are under `docs/architecture/`.

| # | File : line | Current | Required change |
|---|---|---|---|
| E1 | `.agents/AGENTS.md` : 46 | "Read `docs/architecture/architecture_reference.md` for the module map and dependency rules." | Replace the single path with the two that hold those things: `module_dependency_graph.md` (module map) and `hard_dependency_rules.md` (dependency rules). Keep the numbered-list shape. |
| E2 | `specweaver-design/references/phase-2-research.md` : 23–26 (A.2) | "Read the architecture reference in full: `docs/architecture/architecture_reference.md`" + a Focus-on list naming module map, dependency rules, archetypes, Known Boundary Violations, Feature Map, Anti-Patterns | Replace the single read target with the six documents that the focus-list already enumerates, one per line, so each focus item names its own file. Drop the now-redundant "Focus on:" line. |
| E3 | `specweaver-implementation-plan/references/phase-1-preparation.md` : 19–22 (1.2) | Same shape, focus-list without Feature Map | Same treatment, five documents. |
| E4 | `specweaver-implementation-plan/references/phase-3-architecture.md` : 22 | "check the `context.yaml` and `architecture_reference.md` definitions for the target module" | → "check the module's `context.yaml` against `03_system_topology/context_yaml_spec.md` and `03_system_topology/hard_dependency_rules.md`". The three bullets under it already quote `forbids:` rules, so the dependency-rules doc is the correct target. |
| E5 | `specweaver-pre-commit/references/phase-1-architecture.md` : 11–14 (§1.1) | Fenced block containing the bare path | Replace the fenced path with the four documents §1.1–§1.7 actually consume: `module_dependency_graph.md`, `hard_dependency_rules.md`, `archetypes.md`, `anti_patterns.md`. **Keep it a fenced block** only if every path stays on its own line; a bullet list is preferred. |
| E6 | same : 61–67 (§1.8) — **FR-2** | "document the violation in the architecture reference (`docs/architecture/architecture_reference.md`) under 'Known Boundary Violations'" | → "record the violation in `docs/architecture/06_lessons_and_future/known_boundary_violations.md`". Drop "under 'Known Boundary Violations'" — the file *is* the ledger, so the section qualifier no longer applies. This is the site that was writing new records into nowhere. |
| E7 | same : 36 (§1.4) | "Check the Feature Map in the architecture reference for precedent." | → point at `02_bounded_contexts/legacy_feature_map.md` **and say what it is**: a Phase 1–3 historical record whose paths (`project/`, `cli/`, `validation/`, `sandbox/filesystem/`) predate the current `src/specweaver/` layout. Useful for placement *reasoning* and precedent, not for locating files. (HITL-approved 2026-08-08.) |
| E8 | `specweaver-pre-commit/references/phase-6-documentation.md` : 11 | `- docs/quickstart.md — new workflows or commands` | **Delete the bullet.** No such file has ever existed. |
| E9 | same : 12 | `- docs/testing_guide.md — new test patterns or quality gates` | → `docs/dev_guides/testing_guide.md`, the real path. |
| E10 | same : 14 | `- docs/developer_guide.html - add diagrams…` | **Delete the bullet.** Never existed; `docs/dev_guides/` already carries this obligation via §6.4. |
| E11 | same : 27 | `- docs/architecture/architecture_reference.md` | → enumerate the four documents §6.3's own trigger list maps onto, one per line: `03_system_topology/module_dependency_graph.md` (module placement), `03_system_topology/hard_dependency_rules.md` (dependency direction, layer boundaries), `06_lessons_and_future/anti_patterns.md` (the next line orders "Add new anti-patterns discovered during this feature"), `06_lessons_and_future/known_boundary_violations.md`. **Do not** substitute `README.md` here — it resolves on disk and would satisfy SF-02's checker while telling the agent nothing (R3). |
| E12 | same : 28 | `- docs/developer_guide.html` | **Delete the bullet.** Same reason as E10. |

After E8/E10/E12, re-read the surrounding `6.3` bullet list and confirm the introductory sentence
("ALL of the following documents **if they exist**") still reads correctly with three fewer items.

## Edit Table — FR-3 (the format contradiction)

| # | File : line | Required change |
|---|---|---|
| F1 | `phase-1-architecture.md` : 73–74 (§1.9) | **Delete** the `> [!CAUTION] FORMAT EXCEPTION` block in full. Replace with a one-line pointer: the combined analysis is presented at the Phase 2 gate, in the format §2.8 specifies. §1.9's surrounding text (deferred gate, proceed to Phase 2, present a COMBINED analysis) is correct and stays. |
| F2 | `phase-2-test-gap.md` : 125–128 (§2.8) | Keep the Artifact mandate — it is the surviving authority — but make the **mechanism tool-neutral** (HITL-approved 2026-08-08). Remove `using write_to_file with IsArtifact: true`, a Windsurf/Cascade verb that does not exist in Claude Code or Antigravity. State the intent instead: write the combined analysis to a reviewable document the user can comment on line-by-line, and do not print the Coverage Matrix or Test Stories into chat. |
| F3 | `phase-2-test-gap.md` : 130–132 | The MANDATORY HITL YIELD block says "present … as an Artifact" and "ZERO further tool calls after generating the Artifact". Reword to match F2's neutral phrasing. The **yield semantics are load-bearing and must not be weakened** — only the noun changes. |

> F2/F3 are why §2.8 must be re-read as a whole before editing: the mandate appears in three places
> in thirty lines, and repairing one leaves the other two contradicting it — the same defect this
> ticket exists to remove, reintroduced at a smaller scale.

## Commit Boundary

**CB-1 (single).** All of E1–E12 and F1–F3. The design specifies one commit for the repairs, and
splitting them would leave main in a state where some instructions point at the numbered tree and
others still name the deleted file — a reader could not tell which was intended.

Suggested message:

```
docs(skills): repair 12 dangling instruction references and reconcile the gate format
```

## Verification (no automated proof at this boundary — by design)

Run in order; all four must hold before the boundary is offered:

1. `python scripts/check_skill_sync.py` → `0 error(s)`. Catches a repair applied to one tree only.
2. Apply the design's five-rule scan (§The Checker's Rule) over `.agents/` → **0
   enforced-and-dangling sites**, down from the 10 measured at design time. This is the exact
   number SF-02's live-tree test will assert; if it is not 0 here, SF-02 lands red. Re-derive the
   scan rather than reusing a session scratch file — those do not survive the session.
3. Search for surviving `architecture_reference` mentions in the instruction trees. **Do not use
   `grep -r` against `.claude/`** — verified at plan time: `grep -rn "architecture_reference"
   .claude/` returns zero hits while `.claude/skills/specweaver-pre-commit/references/phase-1-architecture.md`
   contains two, because Git Bash does not traverse the directory junction. A one-sided repair
   would read as clean. Enumerate files explicitly (`rglob`/`Get-ChildItem`) or check the
   `.agents/` side and rely on step 1 for the mirror.
   Hits under `docs/roadmap/features/` are **expected and must not be touched** — historical
   records, finished-stories-immutable.
4. Read §1.9 and §2.8 back-to-back and confirm exactly one format order survives, in one place.

Step 3 is the check that catches E4, the bare-basename site the SF-02 rule cannot see — which is
why it cannot be dropped in favour of step 2.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | An edit lands in one skill tree only, so non-Claude agents keep reading rot. | Step 1 of Verification. This is the single most likely failure — the harness's live mirroring makes one-sided edits look complete. |
| R2 | Over-repair: a bulk find/replace of `architecture_reference.md` hits `docs/roadmap/features/**`, editing delivered designs and implementation plans. | Explicit non-goal. Edits are applied per-site from the table above; never a tree-wide replace. Step 3 asserts the boundary. |
| R3 | Repairs point at `README.md` for everything, which resolves on disk and so passes SF-02's checker while telling the agent nothing. | The edit table names a specific numbered document per site. A green checker with hollow targets is the failure mode this ticket is *about*. |
| R4 | §2.8 reworded in one of its three locations, leaving two contradicting it. | F2/F3 are a single unit; re-read §2.8 whole before and after. |
| R5 | E7 points a live instruction at a legacy document without saying so, and the next agent treats stale paths as current. | E7 mandates the "historical record" framing, not a bare repoint. |
