# Where the project is

Updated at commit boundaries. For *this session's* loose ends, see `.tmp/HANDOVER.md`.

## Read this first

**Six capabilities are `🔧`, not `✅`.**

`E-VAL-03` · `C-VAL-05` · `B-FLOW-05` · `C-FLOW-11` · `B-SENS-03` · `D-UI-01`

They are built, tested and proven. The `specweaver-design` **Phase 6 approval gate has never run
for any of them**.

`🔧` is not a softer `✅`, and it is not "not started". **Nothing automatic stops you flipping one
to `✅`. Do not.** Only the user can give the sign-off.

## Two of them are wrong

Read the design before touching either. Each says so in its own first section.

| Capability | What is wrong |
|---|---|
| `E-VAL-03` | It is named *AST* Prompt Injection Sanitization. It scans rendered text line by line. It does not conform to its own specification |
| `B-FLOW-05` | Its ceilings sit on `LLMSettings`. Every LLM access, payment, pricing, token and limit parameter is to live in **one central place** — file or database is still undecided |

`B-FLOW-05` is blocked on that decision. `E-VAL-03` is not blocked; it needs rebuilding.

## Live and worth knowing

`llm.max_spend_usd` defaults to **$25**. `llm.max_tokens_per_run` to **20,000,000**. A run that
reaches either stops and names the setting. The numbers are placeholders nobody agreed.

Disable with `null`. `0` means *refuse everything* — a mistyped ceiling fails closed.

## Recently done

| What | Result |
|---|---|
| Mutation data contract, six stages | Four JSON structures re-engineered after six rounds of grilling |
| Verdicts | `PROTECTED` / `UNPROTECTED` / `UNMEASURED`. Every one that is not a pass is a finding |
| The ledger | Findings close with a reason instead of vanishing. Kept 12 months |
| Test results | Read as JSON, not scraped from pytest's console |
| Mutants | Time-boxed at 900s. A hang is `UNMEASURED`, never a survival |
| The nightly gate | A run that leaves no record is an alarm, not a pass |
| Skills | `/grill-me` now gates design Phase 1 and Phase 6, and the plan skill |

## Still missing

- **The `C-FLOW-11` pilot is unwired.** The dial exists; `sw implement` still runs one-shot, so no
  user path reaches `agentic` mode.
- **No gate stops `🔧` becoming `✅`.** The check that would is story-scoped and only fires when
  somebody remembers the story. `check_stale_delivered.py` now catches the *other* half — prose
  calling a `🔧` capability delivered — but nothing stops the flag itself being flipped.
- **`A-SENS-02`** is the last open item in `US-11`'s Core MVS. Its grilling has three unanswered
  questions. **It is not the next thing** — the six above are.

## The queue

`docs/roadmap/master_story_roadmap.md`, section *Active Routing Queue*. The marker legend is at the
top of it.
