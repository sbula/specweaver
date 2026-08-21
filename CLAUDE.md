# SpecWeaver

> Specification-driven development. Enforces spec quality through a 12-test battery and runs
> AI agents behind role-restricted tools.

## Read these three, in order

| File | Tells you |
|---|---|
| [`.agents/PROJECT.md`](.agents/PROJECT.md) | What this is, where things live, how to test |
| [`.agents/PRINCIPLES.md`](.agents/PRINCIPLES.md) | How we work. Not preferences — non-negotiable |
| [`.agents/STATE.md`](.agents/STATE.md) | Where the project is right now, and what is wrong with it |

Then, before your first change:
[`docs/dev_guides/working_in_this_repo.md`](docs/dev_guides/working_in_this_repo.md) — ten traps,
each one an incident that cost a session.

## The four rules that matter most

1. **Use the skill.** Find the one covering your task before improvising. `specweaver-pre-commit`
   runs before *every* commit.
2. **Twelve decisions are the user's, not yours.** Money, security posture, scope, architecture,
   defaults, anything that cannot be walked back. The triggers and the test are in
   [`PRINCIPLES.md`](.agents/PRINCIPLES.md) §2.
3. **Test first, and watch it fail.** A test that cannot fail is decoration.
4. **No subprocess.** Use `SubprocessExecutor` from `specweaver.sandbox.execution.executor`.

## Getting started

```bash
uv sync                                  # installs everything the gates need
export PATH="$PWD/.venv/bin:$PATH"       # absolute, always

python -m pytest -n auto --tb=short -q   # the suite
python scripts/quality.py cb             # the commit gate
```

Commit straight to `main`. No feature branches. The user pushes.

## Choosing a model

- **Sonnet** for most work — coding, tests, refactoring, debugging.
- **Opus** for architecture, multi-module refactors, deep debugging.
- `/compact` at ~60% context. `/clear` when the session has drifted.
