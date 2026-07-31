# Design: TECH-Ticket Roadmap-Registration Guardrail (specweaver-ticket Phase 4 + check_roadmap_sync.py)

- **Feature ID**: TECH-025
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Code-verified audit of the TECH registry, 2026-07-31
  (`docs/analysis/tech_registry_audit_2026-07-31.md`, Open Decision #4), which traced
  directly to commit `657f9948`'s own message

## Problem Statement

`TECH-022` (the ticket this session retired) closed its documented repair scope but explicitly
left one piece uncarried, per commit `657f9948`'s own message:

> "NOT complete, and deliberately not carried by this commit: the guardrail TECH-022 also
> specified — asserting both-registry presence with matching markers in
> `check_roadmap_sync.py`, and requiring the roadmap entry in `specweaver-ticket` Phase 4.
> Neither exists. Until they do, D1 can recur exactly as before: eight of the nine missing
> entries were minted during INT-US-21 and Phase 4 never asked for the roadmap side. That work
> needs its own ticket, since 'Split-Brain — Seven Statuses' no longer names what is left of it."

Confirmed still true by inspection on 2026-07-31:

- `scripts/check_roadmap_sync.py` checks a **different** registry pair — capability IDs
  (`[A-E]-(?:UI|SENS|FLOW|INTL|VAL|EXEC)-\d+`) against `capability_matrix.md`, and `US-N Core`
  checkboxes against green `### US-N` headers. It has **no regex, no logic, and no mention of
  `TECH-\d+` anywhere in the file.**
- `.claude/skills/specweaver-ticket/SKILL.md` Phase 4 ("Register It") step 4 says
  "**Capability IDs only:** update both `capability_matrix.md` and the topic doc" — TECH IDs are
  never told to register a `master_story_roadmap.md` header entry at all. The only reason this
  session's TECH-022 through TECH-024 minting registered roadmap headers is that the operator
  (this session, following the audit doc's Part 2 finding that "topic_07 vs. headers" is a real
  sync axis) chose to, not because the skill required it.

This is exactly the class of defect that produced the original `TECH-022`/`657f9948` split-brain:
a topic-doc entry with no roadmap header (or vice versa) silently drifts, and nothing catches it
until a manual audit.

## Candidate Approaches (not yet designed)

- Extend `check_roadmap_sync.py` (or add a sibling check) to assert: every `TECH-\d+` referenced
  by a topic_07 entry has a matching `### <emoji> TECH-\d+:` header in `master_story_roadmap.md`
  with the same status emoji, and vice versa — mirroring the existing capability-ID check's
  stale/overclaim error-and-warning structure.
- Add a Phase 4 step to `specweaver-ticket/SKILL.md` for the TECH family specifically, requiring
  a `master_story_roadmap.md` header entry (title + status + at least one MVS checkbox line) in
  the same pass that files the topic-doc entry — not deferred to a later "someone will notice."
- Wire the new check into `scripts/quality.py doc` alongside the existing `roadmap_sync` check so
  it runs at the same pre-commit gate.

## Non-Goals (proposed, pending design)

- Not a rewrite of the existing capability-ID sync check — extend or sit alongside it, don't
  replace working logic.
- Not a retroactive audit of TECH-012 through TECH-021 for this specific gap — that's `TECH-018`'s
  and the audit doc's Part 3 "not yet code-audited" scope, a separate concern.

## Next Step

Run through `specweaver-design` to decide: extend `check_roadmap_sync.py` vs. a new script, and
the exact Phase 4 wording for `specweaver-ticket/SKILL.md`.
