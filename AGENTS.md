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

`.agents/skills/` holds the skills. Each `.claude/skills/<name>` is a **symlink** to
`.agents/skills/<name>`, so Claude Code and other agents read the same files. **Edit only
`.agents/skills/`.** `python scripts/check_skill_sync.py` is part of the pre-commit gate and fails
if the two trees ever differ.

> [!WARNING]
> **Windows:** the symlinks need git's `core.symlinks`, or Claude Code finds no skills. Setup and
> repair: [`CONTRIBUTING.md`](CONTRIBUTING.md#dev-setup).
