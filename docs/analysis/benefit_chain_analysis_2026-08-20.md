# Where the Benefit Chains Ground — and Where They Don't

*2026-08-20. Requested by the user with an explicit definition: a capability **makes sense** when,
working as promised, it produces a real-life benefit something can build on; it is **nonsense** when
it can be built and tested, delivers exactly what it promises, and still nobody gains — the backup
stored on the disk it protects. This analysis applies that test to every capability and story in
the roadmap. Documents are the primary source; code is consulted only to verify claims. The test
applied throughout: **"It works. Now what?"** — following each claimed benefit until it reaches a
person who is better off, or runs out.*

*Judgments here are about the design, not the wiring. A built-but-unconsumed capability whose
benefit is real once wired (`C-FLOW-11`, `B-SENS-02`) is a **gap**, not nonsense, and is not listed
as a finding.*

## 1. The spine is sound

The terminal benefit the whole tool answers to (README, Success Criteria): *a person writes a spec,
the tool validates it, agents implement it safely, the person gets verified working code with less
effort and risk than doing it by hand.* Traced against that, the core loop grounds at every link,
and five capability families are the product's genuinely load-bearing ideas:

| Family | Why the chain grounds |
|---|---|
| **Scenario verification** (`B-FLOW-01`, US-24) | The only validation that tests *behaviour against intent* rather than syntax. Catches the failure LLM generation actually produces: code that compiles and does the wrong thing |
| **Spec rot interception** (`B-VAL-02`) | In a spec-driven tool the spec is the input to all future work; a rotten spec poisons every later generation. This benefit exists *because* the tool is spec-first — it is self-consistent in the best way |
| **The zero-trust sandbox** (topic 06) | Produces no value itself; it makes autonomy *safe enough to use at all*. A precondition benefit, and real |
| **Cost visibility and circuit breakers** (`C-FLOW-01`, `B-FLOW-05`, `C-FLOW-13`/`D-FLOW-05`) | Real money. The catalogue pair also fixes a live defect the docs record honestly: unknown models price at `$0.00` |
| **Memory bank and handover** (`B-INTL-09`, `D-INTL-06`, US-28) | Long autonomous runs die of context degradation; this is the mechanism that lets them live |

Also grounding cleanly: the constitution/standards family (generated code matches house style →
less rework), decomposition (US-21), contract drift (US-22 — after `TECH-066` made it able to find
anything), the brownfield family (US-10/11/12 — the paying-user scenario), the remote HITL
dashboard (US-6 — pipelines block on a human; unblocking remotely is hours saved), and graduated
autonomy (`C-FLOW-11` — two real modes of use, confirmed by the user).

The roadmap is also honest in places worth crediting: `B-INTL-04` calls *itself* "science fiction
today"; `B-INTL-10` carries its own "may be superseded … or retire" note. Self-diagnosis exists.

## 2. Nonsense — benefit chains that dead-end

### F1 · The "Mathematical Speed & Security (Rust)" family — `A-VAL-04`, `A-EXEC-03`

Appears as an add-on group in four stories (US-1, US-5, US-9, US-22). Promise: rewrite validation
rules and the worktree bouncer in Rust for "10x–50x performance scaling" and "guarantee absolute
memory-safe LLM sandboxing."

**It works. Now what?** A spec validation parses a few kilobytes of markdown and runs ~23 rules —
milliseconds beside the LLM call that follows it, which takes seconds to minutes. Making a 200 ms
step 50× faster inside a 30-second pipeline changes nothing anyone can feel. No analysis document
in the repo records anyone ever waiting on validation, extraction, or the bouncer. This is Amdahl's
law as a product plan: heavy investment in the fraction of wall time the LLM does not own.

The security half is a category error on top: rewriting *validation rules* in Rust does nothing for
the *sandbox*, and the sandbox's threat is what generated code does when executed — not how the
validator allocates memory.

**Exception:** `D-SENS-04` (parallel AST extraction) has a real consumer at brownfield-monorepo
scale, where an initial scan of millions of lines is genuine wall time. Its benefit gates on that
scale being reached — park it behind a measured trigger, not a schedule.

### F2 · `C-SENS-06` Event-Sourced 4D Graph

Promise: point-in-time architectural queries and "semantic git bisect" without checkouts.

**It works. Now what?** Who has ever asked what the architecture looked like at a past commit, and
what did they do with the answer? No user story claims this capability — it exists only in the
topic doc. The repo's own principle 9 states the counter-argument: *git holds history.* A temp
worktree plus `sw graph build` answers the same rare question today. The cost side is permanent:
event-sourcing puts `valid_from`/`valid_to` on every node and edge write forever, to serve a query
with no named asker. This is the locked gate with no fence.

### F3 · `A-EXEC-02` fuzzing + `A-INTL-02` symbolic execution — for code the tool does not generate

Promise: libFuzzer harnesses and KLEE-guided 0-day discovery over generated code, for "deep memory
safety on C++/Rust targets."

**It works. Now what?** The implement loop is Python-only today — `D-INTL-08` exists precisely
because `sw implement` cannot present a non-Python target. Memory-safety fuzzing of C++ the tool
cannot produce protects nobody. The chain reaches a user only in a future where the polyglot loop
exists *and* someone builds C++/Rust through it. Sequenced before that, these are decoration; the
docs should carry that gate explicitly.

### F4 · The unconsumed precision of DAL — five levels in, one bit out

The DAL system's *idea* grounds: criticality-gated autonomy and isolation is the mechanism behind
the two-use-case vision (vibe coding on throwaway code, strict agentic mode on serious code), which
the user has affirmed as real. **The finding is about the resolution, not the idea.**

Measured 2026-08-20: `DALLevel` defines five levels and three consumer properties. In `src/`,
`confidence_threshold` — the only genuinely five-valued property — has **zero consumers**. Every
live DAL decision is binary: `is_strict` (A,B vs rest) at two sites, `rank >= threshold` (above or
below a line) at two more. The five-level DO-178C vocabulary delivers, in practice, a two-position
switch — precision no consumer uses, like temperature to 0.001° for an AC that accepts whole
degrees. The debt ledger corroborates the pattern from the other side: `TECH-041` (the code-level
DAL override unproven end to end) and `TECH-067` (the pipeline resolves a module's DAL and never
applies it) both found DAL machinery running disconnected — and nothing downstream noticed, which
is itself evidence of how much weight it bears.

Every future DAL-consuming capability (`B-VAL-05`, `C-FLOW-09`, `C-UI-01`'s DAL colouring, the
DAL-gated rubric variants) inherits this question: what decision needs more than strict/relaxed?

### F5 · `C-VAL-04`'s label — a benefit claimed by the wrong mechanism

Delivered, ✅, and *does* carry a real benefit: hard-failing when a requirement has **zero** tests
catches genuine omissions. But its registry entry credits it with "preventing Correlated
Hallucinations," and that chain dead-ends: the `@traces` tag is written by the same LLM that writes
the test, so a hallucinated test carries a well-formed tag and passes. The system already owns the
mechanism that delivers what this label promises — `A-VAL-03` mutation gates. The pieces exist; the
labels sit on the wrong boxes. Fix is one paragraph of registry prose, not code.

## 3. Bets — chains that end at a consumer nobody has named

Not nonsense; each has a plausible beneficiary who is currently hypothetical. These need a decision
about intent, not a design review.

| Capability | The unnamed consumer | The question |
|---|---|---|
| `A-UI-01` Dark Factory signed ledgers | A regulator/auditor requiring per-line LLM provenance | Has any target customer's auditor asked for this? The *unsigned* lineage graph (`B-SENS-01`, delivered) already serves the user's own debugging and cost attribution |
| `US-17`/`B-VAL-04`/`A-UI-02` SWE-bench guarantee | A release audience needing proof of non-degradation | Today there is one developer who knows what changed. Also: the score convolves the plugged-in model with the platform — pin the model or the number measures Gemini, not SpecWeaver |
| `A-VAL-02` symbolic math validation | The external trading system (US-18) | Real benefit *inside* that engagement (a transposed sign in a pricing formula costs money); no benefit outside it. Note the story wrapper — "proves secure," "0-days" — promises a different universe than formula-transcription checking, which is what the mechanism can deliver |
| `A-EXEC-01` Black Box Ledgers | An operator needing determinism beyond the delivered memory bank | `B-INTL-09` + `D-INTL-06` already captured most of this benefit at far lower token cost; the extreme version pays a full context reboot per hand-off for a marginal determinism gain |

## 4. A structural risk: four graphs, overlapping facts

The system maintains four graph-shaped stores: module topology from declared `context.yaml`
(`D-SENS-01`), the extracted symbol-level knowledge graph (`B-SENS-02`), the Merkle dependency-hash
topology (`A-SENS-01`), and artifact lineage (`B-SENS-01`). Lineage is orthogonal. The first two
answer overlapping dependency questions from different sources — declared intent vs extracted
reality — which is the repo's own "one fact, one place" principle violated at product scale. The
documents already record the consequences: `TECH-064` (polyglot architecture checks reporting
success while doing nothing) and the `B-SENS-07` analysis (boundary decisions spread over five
tools, two of them stubs). `B-SENS-07`'s "supersedes rather than joins" direction is the right
instinct — the risk is new capabilities quietly building on the losing graph while the
consolidation is pending.

## 5. Vocabulary as a symptom, restated under the benefit lens

The earlier finding stands and sharpens: "mathematically," "perfectly," "guarantee absolute" appear
almost exclusively on the capabilities in sections 2 and 3. Under the benefit test the pattern has
an explanation — where a chain grounds in a real gain, the entry describes the gain (`B-FLOW-05`:
"a breaker that ships disabled stops nothing"); where it doesn't, the vocabulary supplies the
confidence the chain can't. The words are a usable audit index.

## 6. Score

136 designs, ~90 distinct capabilities traced. The spine — roughly two-thirds of all capabilities,
including nearly everything delivered — grounds in real benefit. Clear dead-ends: the Rust
speed/security family (minus `D-SENS-04`'s gated case), `C-SENS-06`, the C++/Rust security tooling
ahead of its prerequisite, DAL's unconsumed resolution, and one mislabeled benefit on `C-VAL-04`.
Four more are bets awaiting a named consumer. That is a healthier ratio than the session's earlier
formal findings suggested: the project's core idea survives the harshest test available — *assume
it all works, then ask who is better off.*

## 7. Resolutions — the user's answers, same day

The four open questions were put to the user. Answers, and what each changes:

**DAL (Q1).** The first real target is an automated day-trading system: risk management, news
analysis, market-data analysis, real-money execution — genuinely mixed criticality. The DAL *idea*
is therefore validated by a real project. The tier *count* is explicitly unknown, including to the
user. **Resolution: the tier count is an empirical question the trading project will answer — no
new DAL-consuming capability (`B-VAL-05`, `C-FLOW-09`, DAL-gated rubrics) should hard-code five
levels before that calibration exists.** The measured fact stands: today's consumers use one bit.

**Audit (Q2).** The regulator is aspirational; the real consumer is the user himself — auditing
what agents did on a home server while he is 500 km away. That re-grounds the family, and it
re-scopes `A-UI-01`: the adversary of the audit trail is not a fraudster but **the agent itself**,
which runs with write access on the machine that produces the record. Tamper-evidence has a real
consumer under that framing; "Enterprise regulatory audits" does not. The need decomposes into
delivered lineage (`B-SENS-01` ✅) + remote read (`D-UI-06`, US-6) + a tamper-evidence layer —
`A-UI-01` re-scoped to that, shorn of the regulatory costume.

**Trading system (Q3).** Real, late planning. `A-VAL-02` grounds inside it (formula-transcription
errors cost real money). The wrapper — "proves secure", "0-days" — still promises a different
universe than the mechanism delivers and should be re-worded. The C++/Rust security tooling
(`A-EXEC-02`, `A-INTL-02`) stays gated: no evidence the trading system is a native-code target.

**SWE-bench (Q4).** Confirmed as the product-track twin of the repo's own dev gates: a regression
gate for the platform before trusting it with projects that touch real money. That grounds it —
and *raises* the stakes on the confound: a gate guarding a trading deployment must not report
model noise as platform stability. Model-pinned, multi-run, known-variance is now a requirement,
not a suggestion.

**Net effect on the score:** three of the four bets ground; `A-EXEC-01` (Black Box Ledgers) remains
the one open bet. The dead-ends in section 2 are unchanged except DAL, which moves from
"unconsumed precision" to "precision awaiting calibration by the first real project."

## 8. Follow-up round — findings first omitted, and their resolutions

The user asked what the report had filtered. Honest answer: courtesy passes were given to entries
already marked 🔮 or self-flagged, and to `E-VAL-03` as "in flux". The definition has no courtesy
tier. The omitted findings, with the decisions taken the same day:

- **`E-VAL-03` — nonsense, ruled by the user.** Working perfectly, the injection filter blocks the
  crude attacks the sandbox/review/scenario layers already survive, and cannot touch semantic
  poisoning ("use MD5 for the auth hashing"), which carries no instruction-shaped text. Being
  best-effort, nothing may ever rely on it — a control nobody can build on. `escaping.py`
  (structural correctness, `E-INTL-01`) is separate and stays. Disposition of the ID and the
  shipped `injection.py` is still open; the slot's name re-read as *structure into prompts* has a
  real benefit chain (fewer hallucinated symbols) and is the candidate replacement.
- **`B-INTL-08` as stated — nonsense.** "Replaces text-based PR diffs with Graph Diffs": no human
  reads a dataflow-graph diff, and the LLM reads text natively. As *augmentation* it would ground.
  No action ordered yet.
- **`A-EXEC-01` — nonsense-leaning**, not merely an open bet: the delivered memory bank
  (`B-INTL-09` + `D-INTL-06`) already captured the benefit; a full context reboot per hand-off buys
  marginal determinism at a large permanent token cost. No action ordered yet.
- **The fleet-of-20+ family** (`A-INTL-05`, `A-SENS-04`, `A-EXEC-04`, the fleet halves of
  US-19/US-26): every chain terminates at a fleet existing in no named project. Grounding or
  parking is an open user decision.
- **`A-VAL-05`** (visual quality gates) and **`A-VAL-06`** (industry bridges): consumers unnamed.
  Open.
- **`A-SENS-03` vs `A-SENS-01` — resolved: folded.** Two mechanisms claimed one benefit (graph
  freshness without full rescans). Lazy hash sync (`A-SENS-01`, delivered) guarantees freshness at
  read time — the only time freshness is consumed — and eager events would need hash comparison as
  their own recovery path anyway. `A-SENS-03` re-scoped to a thin trigger invoking `A-SENS-01`
  sync, built only when a daemon-mode consumer exists.
- **Target check, on request:** the co-authoring → MVP target (human+LLM brainstorm/falsify/verify
  a spec, then prototype) maps entirely onto capabilities judged sense; no retirement touches it.
  Its critical path is `C-FLOW-11`'s wiring — `D-INTL-07`, the grill-style co-drafting, is
  hard-blocked on it.

**Actions executed 2026-08-20** (user-approved plan): `A-VAL-04`, `A-EXEC-03`, `C-SENS-06` retired;
`A-SENS-03` folded into `A-SENS-01`; `A-UI-01` re-scoped to Tamper-Evident Agent Audit Ledger;
`A-VAL-02`/US-13 re-worded to formula-transcription checking; `B-VAL-04`/US-17 given the
model-pinning requirement; `C-VAL-04`'s design and registry prose corrected; measurement gates on
`D-SENS-04`, `A-EXEC-02`, `A-INTL-02`; DAL calibration gates on `US-20`, `B-VAL-05`, `C-FLOW-09`,
and the capability-matrix naming convention.
