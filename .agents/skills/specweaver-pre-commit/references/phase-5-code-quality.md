---
description: "Phase 5: Code quality checks — one consolidated static-analysis gate, plus registry sync."
---

# Phase 5: Code Quality Checks

5.1. Run the **consolidated static-quality gate** for the commit point you are actually at:

     ```
     python scripts/quality.py cb        # a commit boundary (CB-N) — the usual case
     python scripts/quality.py sf        # the sub-feature (SF-N) is complete
     python scripts/quality.py feature   # the feature / story is closing
     ```

     This replaces the separate `ruff` / `mypy` / `C901` / file-size / `tach` invocations that
     used to be five steps here. One command runs every static check **in parallel** and prints a
     summary table followed by full detail for failures only.

     Checks covered: `ruff` (lint, including `PLR0913` / `FBT` / `PGH`), **`ruff format --check`**,
     `mypy`, `complexipy` (cognitive complexity — this REPLACED the C901 cyclomatic gate), `tach`,
     file sizes, the suppression ratchet, class health (god-object + LCOM4), import cycles,
     coupling metrics, coding conventions, and the two test-source guards.

     If the `format` check fails, the fix is one command — `python -m ruff format src tests
     scripts` — and it is safe to run unprompted. It is a gate because `pyproject.toml` disables
     `E501` on the grounds that "line length handled by formatter", so with no formatter running,
     line length was enforced by nothing at all.

     **Gates are cumulative and the scope is derived from the gate.** `feature` ⊇ `sf` ⊇ `cb` ⊇
     `quick`: a higher commit point runs MORE checks over MORE code. Core checks cover ALL source
     from `cb` upward regardless of what was touched. Do **NOT** pass `--scope` to make a gate
     cheaper — the scope is the contract, not a preference.

     Every failure MUST be fixed — no exceptions, regardless of whether the failure is
     pre-existing or newly introduced.

     > [!IMPORTANT]
     > **NEVER silence a finding to make the gate pass.** Not with `# noqa`, not with
     > `# type: ignore`, not with a `per-file-ignores` entry in `pyproject.toml`, not with
     > `# mypy: ignore-errors`. `scripts/check_suppressions.py` counts all four forms against a
     > frozen baseline and will block the commit anyway — it exists precisely because adding the
     > suppression is the cheapest way to satisfy a gate, and it is the one check every other
     > check depends on. Fix the code. If a rule is genuinely wrong for a package, change the
     > rule's configuration (one reviewable place) and say so in the commit message.

     While working, `python scripts/quality.py quick` is the sub-second subset — safe to run as
     often as you like, and NOT sufficient for a commit.

     `python scripts/quality.py matrix` prints which checks run at which gate and over what
     scope. `--only <check>` reruns a single check while iterating; `--json` emits machine-
     readable results.

5.2. Run the **documentation registry gate**:

     ```
     python scripts/quality.py doc
     ```

     This runs the roadmap-registry sync and the skill-tree sync together. It is a **separate
     track from 5.1 on purpose** — it checks registries, not code, and a stale roadmap checkbox
     must not fail a code gate. Both steps are required; neither substitutes for the other.

     **Roadmap sync.** STALE errors (an unchecked dep box whose capability/story is done in the
     registry) MUST be fixed by syncing the box. OVERCLAIM warnings (a checked box not done in
     the matrix) MUST be surfaced to the user — never silently "fixed" in either direction, since
     resolving them touches finished-registry content (HITL + guard hook apply).

     **Skill sync.** `.claude/skills/` and `.agents/skills/` hold two copies of the same files so
     that Claude Code and other agents (Gemini/Antigravity) both find them. Any error MUST be
     fixed by copying the correct version over the other; decide which side is correct by
     reading, not by timestamp.

     Not included here, because both need a `<STORY-ID>` argument and belong to specific
     lifecycle moments rather than to every commit: `check_story_preconditions.py` (run by
     `specweaver-dev` and `specweaver-implementation-plan` at story start) and
     `check_fr_coverage.py` (run by `specweaver-feature` at closure).

> [!IMPORTANT]
> **NO HITL GATE HERE:** If all checks in Phase 5 pass successfully, update `task.md` and PROCEED IMMEDIATELY to Phase 6. Do NOT stop to ask the user for permission to continue.
