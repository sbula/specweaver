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

**Start `/grill-me` yourself the moment a trigger from §2 appears.** Put every question to the
user and wait: each answer is theirs. A question still open blocks the phase — it never becomes a
default.

**Print your recommended answer beside each question.** It is what makes a reply cheap and fast,
and it shows the user what you would have assumed.

**The reply is what closes the question.** Move to the next phase once every question in the
frontier carries the user's own words. *You decide* counts — record it as a delegation naming the
question and who delegated it. With no user in the run — cron, CI, a headless agent — a fired
trigger stops the work and writes down the open question.

## 2. What is never yours to decide

You work alone. The triggers below are the exception: settle them **with the user**, never by
assuming.

**The test.** If this is wrong and it ships, does the user have to pay, accept risk, migrate, or be
told? Then it was never yours.

| Group | Trigger | Fires on |
|---|---|---|
| Cost and exposure | `T-SPEND` | A number that turns into a bill — ceilings, budgets, model choice, retry counts, turn limits |
| | `T-BOUNDARY` | Anything untrusted code can reach — DAL thresholds, bind addresses, credential paths, sandbox limits, and what counts as untrusted |
| | `T-POSTURE` | What happens when a check cannot run — fail open or fail closed, whether a missing measurement counts as a pass |
| The agreement | `T-DIVERGE` | Building something that would not satisfy the capability's own name, or would leave an FR in its table unmet — including when the substitute looks better |
| | `T-SCOPE` | What the thing will not do — Non-Goals, deferrals, retirements, half-a-capability calls |
| | `T-ORDER` | Which of two open journeys goes first, where the routing queue, the focus points and `STATE.md` all leave it open |
| | `T-PROVEN` | Calling something proven — flipping `🔧` to `✅`, judging a mutant equivalent, declaring a claim covered or a gate green |
| Expensive to take back | `T-ARCH` | Where a thing lives and what it may need — the one central home, a new service to operate, a boundary an ADR already set |
| | `T-NAME` | A name anything can depend on — CLI flags, config keys, API fields, verdict vocabularies |
| | `T-UNDO` | An act that cannot be walked back — deletes, migrations, rewriting history, dropping a public surface |
| Shipped, then lived with | `T-DEFAULT` | A value the user lives with and is never asked about — chunk sizes, thresholds, time-boxes, warning percentages |
| | `T-DATA` | Data that persists or leaves — retention, what is stored, what goes to a third party |
| | `T-OBLIGATION` | A promise that binds the user — dependency licences, third-party terms, compliance claims |

A trigger that fires goes to the user unsettled. It does not get a default, a placeholder, or a
reasonable-looking assumption. **Documenting a guess does not stop it being a guess.**

Everything else is yours: module shape, test tier, fixture design, a library with no cost and no
security surface, either of two implementations that both meet every FR. So is anything an ADR, a
design's *Decisions taken with the user* section, or this file has already settled — read it, and
build on it. A settled decision covers the exact question it answered; a new number, a new surface
or a wider scope is a fresh trigger, not a precedent.

Measured 2026-08-19: twenty-five product-visible decisions were taken by an agent in one session.
Every one was written into a design. Not one was agreed. `T-OBLIGATION` is the only trigger above
with no local incident behind it; every other one names something this repo has hit.

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
