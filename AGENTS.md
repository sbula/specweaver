# SpecWeaver — Agent Entrypoint

> Tool-neutral entrypoint. This file is a **pointer, not a copy** — everything below lives
> somewhere else on purpose, so there is nothing here to drift.

## Read these first

| What | Where |
|---|---|
| **Engineering standards** (architecture principles, mandatory context loading, testing philosophy, shell rules, HITL protocol) | **`.agents/AGENTS.md`** |
| **Lifecycle skills** — numbered, gated procedures for design / plan / dev / pre-commit / review / ticket-minting | **`.agents/skills/<name>/SKILL.md`** |
| **Project map, tech stack, test commands, commit convention** | **`CLAUDE.md`** (repo root — despite the name, the content is tool-agnostic) |
| **Architecture reference** | `docs/architecture/README.md` |
| **Developer guides** | `docs/dev_guides/` |
| **Roadmap & registries** | `docs/roadmap/` |

## Non-negotiables

These are the rules most often broken by agents new to this repo. The full set is in
`.agents/AGENTS.md`.

1. **No guessing.** If anything is unclear, STOP and ask. Never assume.
2. **TDD always.** Red → Green → Refactor. Every change starts with a failing test.
3. **Re-read before edit.** Always read a file immediately before modifying it.
4. **Read `context.yaml`** in any module before modifying it — it declares `purpose`, `archetype`,
   `consumes` and `forbids`.
5. **No `subprocess`.** Use `SubprocessExecutor` from `specweaver.sandbox.execution.executor`.
6. **Respect `tach.toml` boundaries.** Run `tach check` after any import change.
7. **Commit directly to `main`.** Do NOT create feature branches in this repo.
8. **Never skip a HITL gate**, and never bypass the pre-commit gate before a commit.

## Note on tooling directories

`.claude/skills/` and `.agents/skills/` hold **two copies** of the same files so Claude Code and
other agents both find them. They are separate files, and nothing syncs them automatically outside
Claude Code. **Edit both**, then run `python scripts/check_skill_sync.py` — it is part of the
pre-commit gate and fails on any drift. `.agents/` is the tool-neutral path; prefer it when reading.
