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
| `TECH-068` SF-01 delivered | Both edge-write traps closed. `FR-14` was firing, not latent: a real build stored 108 edges typed `CALLS` where every one was `CONTAINS`, because the engine wrote `kind` and the store read `type`. The attribute is named once now. Stale edges are cleared before each write. 20 new tests, 5 killed mutants — the graph's first corpus |
| `TECH-068` SF-02…SF-05 delivered | The seam carries imports, supertypes and call sites; `EXTENDS`/`IMPLEMENTS` told apart across five languages; `CALLS` from upstream tags queries where they ship and from queries written here where they do not. Measured on `src/specweaver`, 358 files in 2.71s: **9106 `CALLS`, 2705 `CONTAINS`, 2274 `IMPORTS`, 341 `EXTENDS`**, 989 ghosts. `NFR-1` 22.7s against a 60s budget |
| `TECH-068` pre-commit, retrospectively | **The skill was never invoked across the ticket's seventeen boundaries** — its commands were run in its place, so Phases 1, 2, 3 and 7 never happened. Run once over the whole session, it found three defects and an unexecuted decision. Two were introduced by the ticket's own work |
| The loader could not be re-read | `SF-01` taught the store to refuse a kindless edge and left `load_from_db` writing the column's name, so a graph read out of the database could never be written back. Nil on the shipped path by accident — `purge_stale_entries` hides it — and directly in `TECH-070`'s way |
| `AD-3` executed, four weeks late | Approved 2026-08-21, never done; `SF-02` shipped marked `Committed ✅` with it among its Outputs, and its plan never scheduled it. Root cause: **`allowed_imports` is not in the `context.yaml` schema and nothing read it.** Declared, imports lifted, two ledger rows, and a guardrail test that ships with it |
| The first real assertion on `graph_edges` | Nothing had ever driven a real parse through to a persisted edge — the polyglot test stops at the engine, the persist test hand-builds nodes, the only real `build_target` test counts nodes. 23 tests added this boundary, every one probed; `_clear_edges_of` went from 1 test protecting it to 6 |
| Ghost edges say what they are | `FR-12` promised the unresolved raw name in edge metadata and delivered `{}`; three of the four links were already right and the engine dropped it. `os.getcwd` and `mystery_call` are two different ghosts again. Oversized identifiers truncate rather than abort a build |
| Go and Rust joined the supertype contract | Both returned `{}` and the contract test looped over it, so the gap read as coverage. Go embedding is `EXTENDS` (**the user's call**, over a tenth `EdgeKind`); Rust separates `impl T for X` from `trait A: B` cleanly. Building it exposed that every Go type reached the graph classified as a PROCEDURE, so no Go hierarchy could ever resolve — classification now reads the parser's own answer |
| Rust traits became visible | Recorded as a limit, then re-measured on the user's challenge and found to be **one line** of query. It mattered more than the first note said: Rust has no struct inheritance, so every hierarchy edge it can emit targets a trait, and a supertrait bound produced **no edge at all** — `FR-9` delivered nothing for the language until this |
| A reload keeps its unknowns | Recorded as `T-DIVERGE`, then measured on the user's challenge and found not to be a decision at all: the test justifying it described the target as a *"lazy target that was never resolved"* — the dangling-edge model **`AD-4` retired in this same ticket** — and derived its requirement from the mechanism. Three lines of SQL; 2 of 8371 tests moved, both asserting exactly this. `TECH-070` no longer starts on a landmine |
| Every capitalised import ghosted | Found by writing the unit tests `resolve_module` never had. The case-lowering was one-sided — candidates lowered, the module stem not — so `import Models` against a collected `Models.py` resolved to a ghost while `from models import ...` against the same file resolved. The docstring had claimed case-insensitive matching all along. `NFR-8`'s **[proof: none]** is now agreement tests in both directions |
| A dead default became a contract | `BaseTreeSitterParser._supertypes_of` returned "inherits nothing" for a language that declared its type nodes and never said what they inherit. Unreachable today, wrong the moment a language is added. `SF-03` found it by mutation and wrote a test that pinned what the branch returned; it now refuses instead, naming the class and what it must implement |
| The handover had rotted to 23 MB | 332,068 lines, **122 of them distinct** — one section repeated ~10,000 times, some copies corrupted mid-line, burying content months stale. `.tmp/` is gitignored, so no diff and no gate ever saw it. `session_handover.py` was cleared by measurement, not assumption: one marker pair, a re-run changing zero bytes. It now warns when the file it writes has stopped being readable |
| `TECH-069` minted | The decision-citations gate has a ticket, six FRs, 27 tests and six killed mutants. Using it found two false-positive classes in it — a wrapped markdown bullet, and stub designs counted as un-accounted. `🔧`: no implementation plan owns the FRs |
| `TECH-070` minted | `🔴` STUB. Every graph build re-ingests every file; `TECH-068` gate G2 withdrew its ≤250 ms target for want of a path to build it on. Sequenced ahead of `B-SENS-09` |
| Nightly mutation, clear | Gate `CLEAR` for the first time in the session: 67 judged, 67 protected, 0 unprotected, 0 unmeasured. `TECH-049` and `TECH-056` corpora re-anchored onto the code the vocabulary refactor moved — the five blocking findings were drift, not gaps |
| Two reports, two names | `_mutate_campaign.py` writes `mutation_campaign_report.md`; the nightly keeps `mutation_session.md` beside its record. One word apart cost a misreading |

## Still missing

- **The `C-FLOW-11` pilot is unwired.** The dial exists; `sw implement` still runs one-shot, so no
  user path reaches `agentic` mode.
- **No gate stops `🔧` becoming `✅`.** The check that would is story-scoped and only fires when
  somebody remembers the story. `check_stale_delivered.py` catches the *other* half — prose calling
  a `🔧` capability delivered — and `T-PROVEN` now names the flip as the user's call, but nothing
  mechanical stops the flag being flipped.
- **No non-stub design accounts for the §2 triggers.** 127 of them, and `decision_citations` is ratcheted there:
  the count can fall but not rise, so nothing forces the backlog down. A design gains its
  `Decisions taken with the user` section when somebody next opens it.
- **Four `TECH-068` findings remain**, recorded in its design's *Retrospective Pre-Commit Gate*
  section. Two are chores: `BaseTreeSitterParser._supertypes_of` is unreachable, and
  `resolve_module` has no unit tests so nothing pins the case-insensitive match RT-21 depends on.
  **Nothing is open.** All eight were closed on 2026-08-22, including two first recorded as limits
  (Rust trait visibility, the ghost reload) that turned out to be small once somebody measured
  instead of estimating. The last two, filed as chores, each turned up a live defect while being
  done. `TECH-068` is now a closure decision rather than a work item — and that decision is
  `T-PROVEN`, the user's.

- **`allowed_imports` is a rule nothing reads.** `context_yaml_spec.md` declares `consumes` and
  `forbids`; `allowed_imports` appears in four `graph/**/context.yaml` files and nowhere else. One
  test now enforces it for `graph/core/builder`. Whether the package migrates to `consumes` is
  `T-ARCH`.

- **`A-SENS-02`** is the last open item in `US-11`'s Core MVS. Its grilling has three unanswered
  questions. **It is not the next thing** — the set-back capabilities above are.

## The queue

`docs/roadmap/master_story_roadmap.md`, section *Active Routing Queue*. The marker legend is at the
top of it.
