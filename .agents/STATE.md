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
| `TECH-068` closed | 2026-08-22, through `specweaver-feature` Phase 4: 16 of 16 FRs planned and cited, every tier run at full scope (7,238 unit · 911 integration · 256 e2e), NFRs re-measured and inside budget. Closing it made `nfr_sweep` fire on five rows a `🟡` had never forced anyone to answer — one was the withdrawn `NFR-3`, still sitting in the table pretending to be a requirement |
| Every capitalised import ghosted | Found by writing the unit tests `resolve_module` never had. The case-lowering was one-sided — candidates lowered, the module stem not — so `import Models` against a collected `Models.py` resolved to a ghost while `from models import ...` against the same file resolved. The docstring had claimed case-insensitive matching all along. `NFR-8`'s **[proof: none]** is now agreement tests in both directions |
| A dead default became a contract | `BaseTreeSitterParser._supertypes_of` returned "inherits nothing" for a language that declared its type nodes and never said what they inherit. Unreachable today, wrong the moment a language is added. `SF-03` found it by mutation and wrote a test that pinned what the branch returned; it now refuses instead, naming the class and what it must implement |
| The handover had rotted to 23 MB | 332,068 lines, **122 of them distinct** — one section repeated ~10,000 times, some copies corrupted mid-line, burying content months stale. `.tmp/` is gitignored, so no diff and no gate ever saw it. `session_handover.py` was cleared by measurement, not assumption: one marker pair, a re-run changing zero bytes. It now warns when the file it writes has stopped being readable |
| The test gate could not run on a third of the repo | Measured 2026-08-23: **131 of the last 400 commits — 32% — changed no Python at all**, and `tests.py` BLOCKED every one, because a tier selecting no tests was read as missing coverage without first asking whether there was any code to cover. Two landed anyway because nobody ran the gate on them. `quality.py` has had a separate `doc` track for this since it was written; the pattern was invented, proven, and applied to one of the two runners. Fixed `083e7ef9`: a boundary with no `.py` in its diff DECLARES zero tiers and passes. Condition is narrow on purpose — one Python file among a hundred documents and it blocks as before, proven by mutation |
| The framework is documented, for the first time | `docs/dev_guides/development_framework.md`. Nothing described the machinery: 76 files mentioned `quality.py` or `tests.py` and nearly all were ticket paperwork, `testing_guide.md` opens by admitting it predates both runners, and `INDEX.md` had no entry. One page — the four runners as a diagram, the 5 gates, the TECH kinds, the DAL direction trap, the ratchet pattern, and where the rules live. Written because the user lost the thread and there was nothing to read |
| Four instructions contradicted another instruction | `AGENTS.md` said `/grill-me` is the user's to invoke while three other places say the agent starts it; `phase-3-implement-tests.md` closed with *NO HITL GATE HERE* four lines under its own mandatory yield; `phase-1-intake.md` kept its own copy of the 13 trigger names, already drifted to *twelve*; `AGENTS.md` still carried *never decide money or security*, the two words §2 replaced. **Three of the four had already drifted.** All four were §5 second copies |
| `TECH-069` retired | Built 2026-08-21, retired by the user 2026-08-23 before it was ever approved. It checked that a design's `Decisions taken with the user` section named all 13 triggers — which one bullet listing them as `not touched` satisfies, and which flipping `fired — <answer>` to `not touched` satisfies while deleting the answer. It never read the rest of the design, so it could not contradict its own section. The deeper fault: guaranteeing the section EXISTS turns the safe failure — an agent finds nothing and asks — into the unsafe one, where it finds a possibly-rotten answer and builds on it. Check, baseline, 27 tests and 6 mutants deleted; the 13 triggers stay in §2 as the agent's own detector |
| `TECH-070` minted | `🔴` STUB. Every graph build re-ingests every file; `TECH-068` gate G2 withdrew its ≤250 ms target for want of a path to build it on. Sequenced ahead of `B-SENS-09` |
| A delivered FR was half-built, and two tests pinned the halves apart | `TECH-049` `FR-3` says *record the count **and the node id of every failing test***. The names were captured and `_session_record.py` took `len()` of them. It survived because **two** test files cite `FR-3` and assert opposite halves: one that `run_baseline` captures the names, one that the written record is *exactly* `{ran, green, failed}` — which pins their removal. Both green, `check_fr_coverage` green, story `COMPLETE`. Cost three nightly runs, the last on a clean commit. Fixed with the names, and the exit code beside them: `killers()` returns `[]` when pytest itself errored, so a broken conftest also read `0 failed` and named nothing. New anti-pattern recorded — **a citation count answers *is this FR mentioned*, never *is this FR met*** |
| The registry says what each capability is for | Topic entries were prose; six files, 158 entries, are now seven keyed fields — Purpose · Trigger · Needs · Reads · Produces · Enables · Done when. `R-ENTRY` rewritten in the placement contract; `Trigger` is EARS, `Done when` is feature-brief practice. **141 🟡 guesses, 145 🔴 gaps** — every field either says something or says nothing is known. Topic 07 stays prose by decision: a TECH ticket fixes an implemented story and 65 of its 67 are closed, so there is nothing left to decide. New entries take the format. What it dragged into the open: `C-INTL-01` shipped single-pass against a multi-level design with `AD-2` never built and never descoped; `C-VAL-04` cannot vouch for test quality because the tag is written by the same model as the test; `C-EXEC-02` `FR-11` promises a fork-bomb cap on a mechanism that cannot keep it; `D-INTL-08` has five language runners no user path can reach; `E-EXEC-01` is 🔴 in every field, its old entry a title with no body |
| The graph corpus had no drift detection | The 2026-08-23 nightly called `TECH-068` `FR-9` *a-rust-trait-is-invisible-again* **UNPROTECTED**. It is not — rerun against the whole suite, five tests object. The mutant was filed in `FR-9`'s campaign 1, whose declared proof covers **Java only**, so a Rust mutant scoped there is unprotected *by construction* and reads exactly like a real gap. Moved to campaign 2, beside its Go twin. It hid the larger fault: **0 of 78 mutants carried a `symbol_sha`** while every older corpus is at 100%, and `drift_of` returns `UNHASHED` and can never return `STALE` — so the whole graph corpus had drift detection off, with `TECH-070` queued next to move that exact code. 74 pinned one at a time through `--refresh`; 4 legitimately refuse. Corpus now 78/78 protected, gate `CLEAR` |
| Nightly mutation, clear | Gate `CLEAR` for the first time in the session: 67 judged, 67 protected, 0 unprotected, 0 unmeasured. `TECH-049` and `TECH-056` corpora re-anchored onto the code the vocabulary refactor moved — the five blocking findings were drift, not gaps |
| Two reports, two names | `_mutate_campaign.py` writes `mutation_campaign_report.md`; the nightly keeps `mutation_session.md` beside its record. One word apart cost a misreading |

## Still missing

- **The `C-FLOW-11` pilot is unwired.** The dial exists; `sw implement` still runs one-shot, so no
  user path reaches `agentic` mode.
- **No gate stops `🔧` becoming `✅`.** The check that would is story-scoped and only fires when
  somebody remembers the story. `check_stale_delivered.py` catches the *other* half — prose calling
  a `🔧` capability delivered — and `T-PROVEN` now names the flip as the user's call, but nothing
  mechanical stops the flag being flipped.
- **Nothing checks that a §2 trigger was put to the user, and nothing will.** Deliberate,
  2026-08-23: the gate that claimed to went out with `TECH-069`, because a keyword check cannot tell
  asking from typing, and a record guaranteed to *exist* is worse than none — it turns the safe
  failure (agent finds nothing, asks you) into the unsafe one (agent finds a rotten answer, builds
  on it). A settled decision now goes `` `[agreed <date>]` `` **beside the fact it governs**, so it
  is one copy and rot is in front of whoever edits the fact. A trigger that did not fire is written
  nowhere. The 13 triggers in §2 remain the agent's own detector — that half was never in doubt —
  and `/grill-me` is what actually protects you. **Nothing in the repo now asks for a `Decisions
  taken with the user` section; two delivered designs still carry one as a record.**
- **Four `TECH-068` findings remain**, recorded in its design's *Retrospective Pre-Commit Gate*
  section. Two are chores: `BaseTreeSitterParser._supertypes_of` is unreachable, and
  `resolve_module` has no unit tests so nothing pins the case-insensitive match RT-21 depends on.
  **Nothing is open, and the ticket is closed.** All eight findings were resolved on 2026-08-22 —
  two first recorded as limits (Rust trait visibility, the ghost reload) that shrank to one line
  and three lines once measured, and two filed as chores that each turned up a live defect while
  being done. The readers `ADR-006` sequences behind edge truth are unblocked: `B-SENS-09`,
  `B-VAL-07`, `B-SENS-08`, `C-UI-01`, `B-SENS-06`, `A-SENS-05`. `TECH-070` precedes `B-SENS-09`.

- **`allowed_imports` is a rule nothing reads.** `context_yaml_spec.md` declares `consumes` and
  `forbids`; `allowed_imports` appears in four `graph/**/context.yaml` files and nowhere else. One
  test now enforces it for `graph/core/builder`. Whether the package migrates to `consumes` is
  `T-ARCH`.

- **Four `TECH-068` mutants can never have drift detection.** Three anchor on bare constants
  (`_GHOST_TYPE_PREFIX`, `_GHOST_PROCEDURE_PREFIX`, `BaseTreeSitterParser._NAME_NODE_TYPES`) and one
  on `context.yaml`. Only `def` and `class` carry an enclosing scope to fingerprint, and
  `--refresh` refuses the rest rather than pinning a lie. Each stays `UNHASHED`, so the code under
  it can move without the nightly saying so. The remedy where a claim matters is to re-anchor the
  mutant on the function that *reads* the constant — not to loosen the hasher.

- **The topic format has 24 ad-hoc field names beside its seven.** `Gate`, `Blocked on` and
  `Hard requirement` all mean *precondition*, which is what `Needs` is for. Nine more — `Cannot do`,
  `Known wrong`, `Not wired`, `Honest limit`, `Thin content` — all mean *what this does not do*, and
  **no field exists for it**. Introduced by the conversion itself, across 158 entries. Undecided:
  fold the preconditions into `Needs` and add one `Limits` field, or leave it.

- **The 800-character entry cap is undecided.** It fired twice during the conversion (`B-FLOW-05`,
  `C-VAL-05`) and both times was met by redistribution rather than by raising it. The rule says "as
  short as possible, as long as needed"; the gate enforces 800. They disagree.

- **The knowledge graph has no reader, and none is designed.** `ADR-006` names eight —
  `B-SENS-08`, `B-SENS-09`, `B-VAL-07`, `B-FLOW-04`, `C-UI-01`, `B-SENS-06`, `A-SENS-05`,
  `B-INTL-08` — and **every one is `🔜`/`🔮` with no design document at all**. Measured 2026-08-24:
  `GraphOrchestrator` and `SqliteGraphRepository` are referenced only inside `graph/`; the sole
  entry point is `sw graph build`, typed by hand. `B-SENS-09` (packing a subgraph into `sw draft` /
  `implement` / `review` prompts) is the only one that reaches a user path — it is what would make
  the graph pay for itself.

- **`TECH-070` rests on two unknowns and its urgency is unmeasurable, not low.** Its case is
  *"every build re-ingests every file"*, quoting **358 files / 2.71 s**. That figure is SpecWeaver
  parsing **its own source** — a test fixture, not a workload. The graph is built over the *target
  project*, and there is no target project. Its second argument — *"`B-SENS-09` packs per turn, so a
  full rebuild compounds"* — is an assumption about a design nobody has written. Both become
  measurable the moment a reader exists.

- **`mutation.py --gate` is BLOCKED** on five `TECH-056 FR-1` findings, all `UNMEASURED
  [scope-already-red]` — collateral of the 2026-08-24 red baseline, not findings about the code.
  Dispositioning them is the human act the gate exists to force; an agent clearing its own run's
  findings is the exact defect `TECH-056` fixed. A green baseline tonight clears them on its own.

- **The gate runners have no test for their own docs-only path beyond the unit tier.** `083e7ef9`
  proves `run_selections` returns a declared zero, and CB-2 exercised it end to end by being
  documentation-only. Nothing runs the *whole* runner over a synthetic docs-only diff, so a future
  change to `paths_for` or the profiles could re-break it silently.

- **`A-SENS-02`** is the last open item in `US-11`'s Core MVS. Its grilling has three unanswered
  questions. **It is not the next thing** — the set-back capabilities above are.

## The queue

`docs/roadmap/master_story_roadmap.md`, section *Active Routing Queue*. The marker legend is at the
top of it.
