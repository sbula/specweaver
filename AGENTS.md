# SpecWeaver — agent entrypoint

> Tool-neutral. This file is a **pointer, not a copy** — everything below lives somewhere else on
> purpose, so there is nothing here to drift.

## Read these three, in order

| File | Tells you |
|---|---|
| [`.agents/PROJECT.md`](.agents/PROJECT.md) | What this is, where things live, how to test |
| [`.agents/PRINCIPLES.md`](.agents/PRINCIPLES.md) | How we work. Not preferences — non-negotiable |
| [`.agents/STATE.md`](.agents/STATE.md) | Where the project is now, and what is wrong with it |

Then, before your first change:
[`docs/dev_guides/working_in_this_repo.md`](docs/dev_guides/working_in_this_repo.md) — ten traps,
each one an incident that cost a session.

## Then

| What | Where |
|---|---|
| Skills — gated procedures for design, plan, dev, pre-commit, review | [`.agents/skills/<name>/SKILL.md`](.agents/skills/) |
| Engineering standards and the skill index | [`.agents/AGENTS.md`](.agents/AGENTS.md) |
| Architecture reference | [`docs/architecture/README.md`](docs/architecture/README.md) |
| Roadmap and registries | [`docs/roadmap/`](docs/roadmap/) |

## Note on tooling directories

`.claude/skills/` and `.agents/skills/` hold **two copies** of the same files, so Claude Code and
other agents both find them. Nothing syncs them automatically outside Claude Code. **Edit both**,
then run `python scripts/check_skill_sync.py` — it is part of the pre-commit gate and fails on any
drift. `.agents/` is the tool-neutral path; prefer it when reading.
