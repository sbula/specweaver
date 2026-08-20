# How we work here

These are not preferences. Breaking one is how the incidents in this repo happened.

## 1. Use the skill. It is not optional

Before starting any task, find the skill that covers it. They are in `.claude/skills/`.

| Doing this | Run this first |
|---|---|
| Designing a capability | `specweaver-design` |
| Planning a sub-feature | `specweaver-implementation-plan` |
| Writing code | `specweaver-dev` |
| **Any commit** | `specweaver-pre-commit` |
| Reviewing a design or a diff | `specweaver-red-blue-review` |
| Minting an ID | `specweaver-ticket` |

**`specweaver-pre-commit` runs before every commit, not after.** It was skipped once and found a
HIGH finding when run afterwards — on code already committed.

**`/grill-me` can only be invoked by the user.** A design starts by asking them to run it, then
stopping. Do not ask its questions in your own words instead.

## 2. Two things are never yours to decide

- Anything that **spends money** — budgets, ceilings, model choice, retry counts that multiply cost.
- Anything that **relaxes a security boundary** — a DAL threshold, a bind address, a credential
  path, a sandbox limit.

Measured 2026-08-19: twenty-five product-visible decisions were taken by an agent in one session.
Every one was written into a design. Not one was agreed.

**Documenting a guess does not stop it being a guess.**

## 3. Test first, and let it fail

Red, then green. A test written after the code passes on its first run, so it asserts what the code
does rather than what it must do.

**Break your own guard and watch it fail.** A test that cannot fail is decoration, and this repo
keeps finding them.

For each thing you build, cover all four: happy path, boundary, graceful degradation, hostile input.

## 4. Integration belongs to the story

There are no integration stories. `ADR-005` retired them.

A story owns every test it needs, including ones that span features. If a related piece is not built
yet, write the test now as `pytest.mark.xfail(strict=True)` naming the blocker.

A **seam FR** — one that needs something from outside the feature — is proven at integration or e2e
tier. A unit test with the other side mocked proves the mock.

## 5. One fact, one place

A number stored beside the thing it summarises is a second copy, and two copies can disagree.
Derive it instead.

This has bitten twice: a stale verdict outlived the run it described, and a count ratchet let
fourteen new violations through because someone else's cleanup had made room.

## 6. Finish before starting

Do not open new work while set-back work is open. Do not file a ticket instead of fixing a thing.

**Filing is not resolving.** Before filing, answer out loud: can I check this now? Can I fix it now?
Does this need a decision I cannot take? Only the third is a reason to file.

## 7. Before you touch a file

- **Re-read it first.** Always read a file immediately before changing it.
- **Read the module's `context.yaml`.** It states the module's purpose and what it may depend on.
- **Do not guess.** If something is unclear, stop and ask. Never assume.

## 8. Boundaries are enforced, not suggested

No cross-layer imports. `tach.toml` holds the rules; `tach check` verifies them.

No `subprocess`. Use `SubprocessExecutor` from `specweaver.sandbox.execution.executor`.

## 9. Code says what is true now

No ticket IDs in comments. No "was X until Y". No dates. Git holds history.

## 10. Verify what the check verifies

A green check may not have looked at your code. Read its output and confirm it examined what you
think it did.

Real examples: a proof-tier check reported zero violations because it never saw the new designs;
a mutation gate reported CLEAR from a report twenty-four hours old.

## 11. Commit straight to `main`

No feature branches in this repo. The user pushes; `git push` is not in the agent's allow-list.

Format: `<type>(<scope>): <description>` — `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
