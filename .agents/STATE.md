# Where the project is

Updated at commit boundaries. For *this session's* loose ends, see `.tmp/HANDOVER.md`.

## Read this first

**Five capabilities are `🔧`, not `✅`.**

`C-VAL-05` · `B-FLOW-05` · `C-FLOW-11` · `B-SENS-03` · `D-UI-01`
(`E-VAL-03` left the list 2026-08-21: retired by the user, detector deleted — see Recently done.)

They are built, tested and proven. The `specweaver-design` **Phase 6 approval gate has never run
for any of them**.

`🔧` is not a softer `✅`, and it is not "not started". **Nothing automatic stops you flipping one
to `✅`. Do not.** Only the user can give the sign-off.

## One of them is wrong

Read the design before touching it. It says so in its own first section.

| Capability | What is wrong |
|---|---|
| `B-FLOW-05` | Its ceilings sit on `LLMSettings`. Every LLM access, payment, pricing, token and limit parameter is to live in **one central place** — file or database is still undecided |

`B-FLOW-05` is blocked on that decision.

## Live and worth knowing

`llm.max_spend_usd` defaults to **$25**. `llm.max_tokens_per_run` to **20,000,000**. A run that
reaches either stops and names the setting. The numbers are placeholders nobody agreed.

Disable with `null`. `0` means *refuse everything* — a mistyped ceiling fails closed.

## Recently done

| What | Result |
|---|---|
| `E-VAL-03` retired, executed | Detector + 3 test files + mutants deleted, `FilePromptAdapter` unwired, `escaping.py` kept (`E-INTL-01`); registry tombstoned everywhere; US-04's *sanitized* clause closed by decision |
| Graph/vector wiring (ADR-006) | `TECH-068` + `B-SENS-08`/`B-SENS-09`/`B-VAL-07` minted; locate→contextualize→verify recorded with the no-gates-on-vectors invariant; readers sequenced behind edge truth |
| Benefit-chain review, whole roadmap | 3 retirements (`A-VAL-04`, `A-EXEC-03`, `C-SENS-06`), `A-SENS-03` folded into `A-SENS-01`, `A-UI-01` re-scoped to tamper-evident agent audit, DAL consumers gated on trading-project calibration. Record: `docs/analysis/benefit_chain_analysis_2026-08-20.md` |
| Mutation data contract, six stages | Four JSON structures re-engineered after six rounds of grilling |
| Verdicts | `PROTECTED` / `UNPROTECTED` / `UNMEASURED`. Every one that is not a pass is a finding |
| The ledger | Findings close with a reason instead of vanishing. Kept 12 months |
| Test results | Read as JSON, not scraped from pytest's console |
| Mutants | Time-boxed at 900s. A hang is `UNMEASURED`, never a survival |
| The nightly gate | A run that leaves no record is an alarm, not a pass |
| Must-not-guess triggers | `PRINCIPLES.md` §2 replaced *money and security* with thirteen named triggers, each grounded in an incident here. `T-DIVERGE` and `T-ORDER` carry thresholds so they fire on something |
| The grilling, flipped | The agent starts `/grill-me` itself when a trigger fires and prints its recommendation; the reply is what closes the question. A run with no user stops rather than proceeding. Gates design Phase 1 and Phase 6, and the plan skill |
| `decision_citations` gate | Reads every design against §2 and ratchets what does not account for it. The trigger list is read from `PRINCIPLES.md`, so adding one stays a single-place edit |
| `TECH-068` designed | Design APPROVED 2026-08-21. Five sub-features, 16 FRs, none planned yet. The review found two persistence defects the ticket now owns: an edge with no kind defaults to `CALLS`, and an edge the rebuilt graph drops is never deleted — both unreachable until `CALLS` lands, both then permanent |
| `TECH-069` minted | The decision-citations gate has a ticket, five FRs, 25 tests and five killed mutants. `🔧`: no implementation plan owns the FRs |
| Nightly mutation, clear | Gate `CLEAR` for the first time in the session: 67 judged, 67 protected, 0 unprotected, 0 unmeasured. `TECH-049` and `TECH-056` corpora re-anchored onto the code the vocabulary refactor moved — the five blocking findings were drift, not gaps |
| Two reports, two names | `_mutate_campaign.py` writes `mutation_campaign_report.md`; the nightly keeps `mutation_session.md` beside its record. One word apart cost a misreading |

## Still missing

- **The `C-FLOW-11` pilot is unwired.** The dial exists; `sw implement` still runs one-shot, so no
  user path reaches `agentic` mode.
- **No gate stops `🔧` becoming `✅`.** The check that would is story-scoped and only fires when
  somebody remembers the story. `check_stale_delivered.py` catches the *other* half — prose calling
  a `🔧` capability delivered — and `T-PROVEN` now names the flip as the user's call, but nothing
  mechanical stops the flag being flipped.
- **No design accounts for the §2 triggers.** All 137, and `decision_citations` is ratcheted there:
  the count can fall but not rise, so nothing forces the backlog down. A design gains its
  `Decisions taken with the user` section when somebody next opens it.
- **`A-SENS-02`** is the last open item in `US-11`'s Core MVS. Its grilling has three unanswered
  questions. **It is not the next thing** — the set-back capabilities above are.

## The queue

`docs/roadmap/master_story_roadmap.md`, section *Active Routing Queue*. The marker legend is at the
top of it.
