# SpecWeaver — engineering agents

> Specification-driven development. Enforces spec quality through a 12-test battery and runs
> AI agents behind role-restricted tools.

## Read these three, in order

| File | Tells you |
|---|---|
| [`PROJECT.md`](PROJECT.md) | What this is, where things live, how to test |
| [`PRINCIPLES.md`](PRINCIPLES.md) | How we work. Not preferences — non-negotiable |
| [`STATE.md`](STATE.md) | Where the project is right now, and what is wrong with it |

Then, before your first change:
[`../docs/dev_guides/working_in_this_repo.md`](../docs/dev_guides/working_in_this_repo.md).

## Skills

Read the skill's `SKILL.md` in full before starting, then each phase file as you reach it. Never
skip a phase. Never bypass a HITL gate.

| Skill | Use it when |
|---|---|
| `specweaver-feature` | Driving a feature end to end |
| `specweaver-design` | Designing a capability → `[ID]_design.md` |
| `specweaver-implementation-plan` | Planning one sub-feature |
| `specweaver-dev` | Implementing a commit boundary, test-first |
| `specweaver-pre-commit` | The 7-phase gate before **every** commit |
| `specweaver-red-blue-review` | Adversarial review of a design, plan or diff |
| `specweaver-ticket` | Minting a `TECH-NNN` or capability ID without collision |
| `specweaver-live-llm` | **Only** on an explicit ask to hit a real provider API — it bills |

**You start `/grill-me` yourself** the moment a `PRINCIPLES.md` §2 trigger appears — then put every
question to the user and wait. Their reply is what closes it; a question you answer on their behalf
is the guess the rule exists to stop.

## The four rules that matter most

1. **Use the skill.** Before improvising a procedure.
2. **Some decisions are never yours.** Money, security posture, scope, names, defaults, anything
   that cannot be walked back. The thirteen triggers and the test that finds them are in
   [`PRINCIPLES.md`](PRINCIPLES.md) §2 — read them there, not from a summary.
3. **Test first, and watch it fail.**
4. **No subprocess.** Use `SubprocessExecutor`.
