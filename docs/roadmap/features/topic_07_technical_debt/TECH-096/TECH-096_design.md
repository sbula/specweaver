# Design: The Never-Run List Is Only Text

- **Feature ID**: TECH-096
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `tooling`
- **Origin**: 2026-11-08, during `TECH-088`; a command on the never-run list was run in a session.
  The list lives only in `CLAUDE.md` and the agent's memory, and nothing stops a command on it.

## Problem Statement

The never-run list: `git stash`, `rm -rf`, reading or printing an API key, `sw` against the real
`~/.specweaver`, `gh`, `git push`, network fetches through Bash, and committing
`scripts/baselines/mutation_findings.json`. It is text, so an agent can break it by mistake.
`.claude/settings.json` even allows `Bash(git stash *)` (line 14). The one `PreToolUse` hook,
`.claude/hooks/guard_finished_stories.py`, guards `Edit|Write` only.

## Candidate Approaches (not yet designed)

Agreed with the user 2026-11-08:
- A `PreToolUse` hook on `Bash` (Python, in `.claude/hooks/`) blocks each listed command with
  exit 2 and a reason `[agreed 2026-11-08]`.
- It reads the command with a shell parser (for example `bashlex`), never with string splits, so it
  sees every part of `;`, `&&`, `||`, `|`, new lines and `$( )` `[agreed 2026-11-08]`.
- It also reads inside `bash -c`, `sh -c` and `eval` `[agreed 2026-11-08]`.
- A command it cannot parse is blocked `[agreed 2026-11-08]`.
- `Bash(git stash *)` leaves the allow list. `.claude/settings.json` refuses agent writes, so the
  user applies every settings change `[agreed 2026-11-08]`.
- Tests: one per listed command, and one per chained or nested form.

## Non-Goals (proposed, pending design)

- No sandbox for the agent; the hook is a guard for mistakes, not a security boundary.
- No change to the `Edit|Write` hook.

## Next Step

`specweaver-feature TECH-096`. Queue: first after `TECH-088` (the user, 2026-11-08).
