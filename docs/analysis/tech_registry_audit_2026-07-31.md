# Session Handoff: TECH Registry Sync Audit (2026-07-30/31)

Working notes for whoever picks this up next — user is restarting their machine mid-session.
Nothing below has been committed yet except where noted. This is a working document, not a
roadmap entry — do not link it from `topic_07_technical_debt.md` as if it were a ticket.

> **STALE (2026-08-01)**: every finding below has since been actioned directly in the live
> registry (`topic_07_technical_debt.md`, `master_story_roadmap.md`) and their design docs.
> TECH-001, TECH-002, TECH-005, TECH-006 are now 🟡 with the real gaps tracked as new SFs
> (TECH-001 SF-04, TECH-005 SF-3, TECH-006 SF-02); TECH-002's design docs were corrected in
> full, not just the roadmap blurb. The 🟢/🟡 verdicts in the table below reflect the OLD,
> now-corrected state — do not read this file as current. See commits `722bed46`, `d615e0af`,
> `acd8e0f6`, `b6e14bf9`, `6b251281`, `cea3548c`.

## How this started

User reported (from a prior session) that an agent had autonomously minted TECH-XXX tickets
out of an unrelated task, and that ticket creation didn't follow the project's normal registration
order (roadmap → capability matrix → topics → feature-folder only once a story starts).

## Part 1 — Root cause found and FIXED (uncommitted)

Traced to commit `9e394973` (2026-07-25), which added both files below in the same commit:

1. `specweaver-pre-commit/references/phase-2-test-gap.md` said "raise a story to make it honest"
   for a vacuous-test finding — an imperative with no gate around it.
2. `specweaver-ticket/SKILL.md` had **zero HITL/STOP instructions anywhere** (unlike every sibling
   skill), so once triggered it ran Phase 1→5 to completion — registry entry, design-doc stub,
   cross-references — before the user was ever asked if a ticket should exist.

**Fix applied to all four files** (`.agents/skills/...` and `.claude/skills/...` copies of both —
confirmed these two trees are kept byte-identical, edit both or they'll drift):
- Phase 2 line reworded: gap goes into the coverage matrix as a *proposed* story only; explicit
  "do NOT invoke `specweaver-ticket` from inside this phase" instruction added.
- `specweaver-ticket/SKILL.md` gained a mandatory STOP-before-Phase-3 checkpoint requiring
  explicit user confirmation before any registry entry or feature-folder is created, with a
  second dated incident entry (2026-07-30) logged the same way the original 2026-07-25 collision
  incident is logged.

**Status: edited, NOT committed.** `git status` currently shows these 4 files modified:
```
.agents/skills/specweaver-pre-commit/references/phase-2-test-gap.md
.agents/skills/specweaver-ticket/SKILL.md
.claude/skills/specweaver-pre-commit/references/phase-2-test-gap.md
.claude/skills/specweaver-ticket/SKILL.md
```
Commit these before anything else touches them, per this repo's "commit directly to main" convention.

## Part 2 — Registry cross-sync audit

**topic_07_technical_debt.md vs. master_story_roadmap.md's `### TECH-NNN` story headers: IN SYNC.**
21 tickets (TECH-001..021), all 21 status markers match exactly. This was fixed one commit before
HEAD by `657f9948` ("retire TECH-022 and reconcile the seven TECH statuses", 2026-07-29).
`capability_matrix.md` correctly has zero TECH references (different ID family, not a gap).

**But a SECOND, separate desync exists and was missed by that reconciliation.** Inside
`master_story_roadmap.md` itself, the "🎯 Active Routing Queue → 🔧 Debt Sequencing" section
(around lines 17-72, specifically the "Pre-existing, never ranked" note at lines 71-72) makes its
own inline status claims that contradict this same file's `### TECH-NNN` headers just below:

| Ticket | Debt Sequencing note (~line 71) | This file's own header | topic_07 doc |
|---|---|---|---|
| TECH-001 | 🔜 | 🟢 Completed | 🟢 |
| TECH-002 | 🟡 In Progress | 🟢 Completed | 🟢 |
| TECH-005 | 🟡 In Progress | 🟢 Completed | 🟢 |
| TECH-009 | 🔜 | 🟢 Completed | 🟢 |
| TECH-010 | 🔜 | 🔴 Pending | 🔴 |
| TECH-011 | 🔜 | 🔴 Pending | 🔴 |

That note says "Refreshed 2026-07-28" — one day *before* the `657f9948` reconciliation, which never
touched this section. It predates and was never in scope for the TECH-022 audit either (that audit
only ever compared topic-doc vs. headers). **Not yet fixed** — still open, pending user go-ahead
(see Open Decisions below; also caught mid-diagnosis that TECH-009's and TECH-010/011's *actual*
correctness was independently confirmed by the code audit in Part 3, so we now know which side of
each of these six is right).

## Part 3 — Code-verified ground truth, TECH-001 through TECH-011

User's framing: "code is the ultimate destination of truth." Dispatched one focused sub-agent per
ticket to check the claim in each design doc against actual `src/`. Full results:

| Ticket | Doc claims | Code-verified reality | Verdict |
|---|---|---|---|
| TECH-001 | 🟢 DDD unification, incl. "preventing circular dependencies" | Bounded-context layout is real (no flat `config/`/`cli/`/`loom/`). **But `tach.toml` explicitly declares two mutual/circular deps**: `core.config ↔ infrastructure.llm` and `core.config ↔ core.flow`. | **Overstated** — circular-dependency claim is false as written. |
| TECH-002 | 🟢 "utilizing `__init_subclass__`" | No `__init_subclass__` anywhere in `src/`. Explicit `ToolRegistry` (`sandbox/registry.py`) exists instead — design doc itself records metaclass auto-registration was deliberately rejected. | Capability shipped; **blurb describes the wrong mechanism** (cosmetic). |
| TECH-003 | 🟢 AST parsers/adapters split | `workspace/ast/parsers/` + `workspace/ast/adapters/` cleanly separated, `tach.toml` enforces it. | **Confirmed.** |
| TECH-004 | 🟢, topic doc still frames as open "GraphBuildAtom vs. deprecate CLI" | No `GraphBuildAtom` — because design doc's own `AD-2` explicitly chose "keep CLI as Composition Root, no centralized Atom." Code matches that decision. | Code matches the real decision; **only the topic-doc summary text is stale**, reads as unresolved when it isn't. |
| TECH-005 | 🟢 in topic doc + header, **🟡 in Debt Sequencing note** | SQLAlchemy tables (`workspace_*`, `flow_artifact_events`, `llm_*`) correctly prefixed. Raw-sqlite3 tables (`nodes`, `edges`, `pipeline_runs`, `audit_log`, `sw_reservations`) **completely unprefixed**. | **The 🟡 note is right, 🟢 is wrong** — ticket claims "all existing database tables"; it isn't all of them. |
| TECH-006 | 🟢, three findings | Findings 1 (misplaced loaders) + 2 (spider-web imports) confirmed fixed. Finding 3 (`RunContext` god object) **still present and worse**: 31 fields now vs. 23 documented, 68-line `model_post_init`. | **Overstated** — 2 of 3 done, the god object grew instead of shrinking. |
| TECH-007 | 🟢 PromptBuilder escaping | Escaping module exists (`infrastructure/llm/escaping.py`), wired into render, tests cover real injection payloads (CDATA breakout, attribute-quote breakout). | **Confirmed.** |
| TECH-008 | 🟢 architecture doc modularization | `architecture_reference.md` deleted, numbered directory structure exists, Composition-Root-vs-Factory ADR exists. | **Confirmed.** |
| TECH-009 | 🟢 in topic doc + header, **🔜 in Debt Sequencing note** | `SubprocessExecutor` correctly used in git/filesystem; documented `noqa: TID251` exemptions exactly as described (`cli_drift.py`, `discovery.py`); no undocumented raw subprocess in scope. | **🟢 is correct; the 🔜 note is the stale one.** |
| TECH-010 | 🔴 not done | `mcp/core/executor.py` still raw `subprocess.Popen`, no persistent-executor abstraction anywhere, no commits touching it since filed. | **Confirmed still pending — 🔴 accurate.** |
| TECH-011 | 🔴 not done | `PipelineStep.params` still opaque `dict[str, Any]`; `validate_flow()` never inspects it; no per-action schemas or load-time test. | **Confirmed still pending — 🔴 accurate.** |

**TECH-012 through TECH-021 have NOT yet been code-audited this session** — only cross-registry
sync was checked for those (and that part is clean, see Part 2). If continuing this work, that's
the natural next batch, same method: one sub-agent per ticket, read the design doc's claim, verify
against `src/`.

## Open decisions — nothing below has been actioned, all pending user go-ahead

Per the Part 1 fix (STOP-before-mint gate), do **not** mint any of these autonomously:

1. **Fix the stale "Debt Sequencing" note** in `master_story_roadmap.md` (~lines 71-72) — either
   update it to match the current header statuses, or delete the stale per-ticket list since it
   duplicates data tracked authoritatively elsewhere.
2. **File NEW tickets** (never edits to 001/005/006 — finished-stories-immutable) for the three
   genuine code gaps found:
   - TECH-001's circular dependencies (`core.config ↔ infrastructure.llm`, `core.config ↔ core.flow`)
   - TECH-005's unprefixed raw-sqlite3 tables (nodes/edges/pipeline_runs/audit_log/sw_reservations)
   - TECH-006's Finding 3 (RunContext god object, now 31 fields / 68-line `model_post_init`)
3. **Fix stale summary text** for TECH-004 and TECH-009 in `topic_07_technical_debt.md` (both
   describe unresolved-sounding states for decisions/work that's actually already settled/done).
4. **File the Phase-4 roadmap-registration guardrail ticket** that commit `657f9948`'s own message
   said was still needed ("requiring the roadmap entry in `specweaver-ticket` Phase 4" — neither
   that requirement nor a real both-registry-marker check exists; `scripts/check_roadmap_sync.py`
   exists but checks a *different* pair of registries — capability IDs, not TECH). Confirmed via
   grep: no ticket covers this yet.
5. **Continue the code audit** to TECH-012..021 if thoroughness is wanted before treating the
   registry as trustworthy end-to-end.

## Quick resume checklist

- [ ] Commit the 4 skill-file fixes (Part 1) — safe, already reasoned through, just needs `git commit`.
- [ ] Get user's decision on items 1-5 above.
- [ ] If continuing the audit, reuse the same one-sub-agent-per-ticket pattern from Part 3.
