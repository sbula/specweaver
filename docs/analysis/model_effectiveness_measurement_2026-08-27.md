# Measuring which model suits which task — where the thinking got to

> **Date**: 2026-08-27 · Steve Bula + Claude
> **Status**: ANALYSIS. Nothing here is designed, nothing is minted, no capability changed.
> **Why it stopped here**: the `specweaver-design` run for `B-FLOW-03` was halted at its Phase 1
> gate. The grilling showed the capability's scope is not settled, and settling it needs this
> document rather than a design.

## The question

> *Which LLM model is the most effective and efficient one for a given kind of task?*

Stated by the user as the one that matters most. Their own framing, which the rest of this document
takes as the brief:

- Cost is **one** axis — money, energy, computing time. Quality of the end result is another.
- The measurement is **fuzzy and not easy**, and there is no measurable answer yet.
- A feature is worked by **several kinds of task** — analysis, design, implementation, test,
  investigation, research — potentially with a **different model per task**, and the quality is
  judged at the **feature** level, at the end.
- You cannot know errors in advance. So this needs **post-mortem analysis**: find the step where
  the error or the misunderstanding happened.
- **As long as single tasks are not measured, you cannot say where the mistake was.**

## Why this is an analysis and not a design

There is precedent in this directory. `llm_routing_and_cost_analysis.md` (2026-03-26) took the same
question and said the original entry:

> *conflates simple plumbing (add more providers), observability (track costs), configuration (pick
> model per task), analytics (dashboard), and AI-driven optimization (dynamic routing) into a single
> feature — making it too large and too speculative to implement as one unit.*

It split into nine sub-features across three phases. **That document is still correct and must not
be re-derived** — in particular §3.1 the credit assignment problem, §3.2 Refactor-Adjusted Cost
(verdict: feasible per pipeline), §3.3 the Attributed Lifecycle Score (sound formula, unknowable
inputs), and §3.4 the AI Arbiter (science fiction: the Arbiter Paradox, Goodhart's Law, and the
delayed feedback loop).

What has changed since 2026-03 and justifies a second document:

1. **Self-hosting.** An ASUS Ascent GX10 is planned. A locally hosted model has **zero marginal
   dollar cost**, which removes the axis the whole 2026-03 framing was built on.
2. **The task vocabulary is too short** for the kinds of task the user actually distinguishes.
3. **A quality signal already exists** and nobody has joined it to a model.
4. **The grain is wrong.** The ledgers cannot answer *per feature, per task kind*.

## The split

Three parts, and they nest. **Part 1 is the only one that is urgent**, because you cannot analyse
what was never recorded — every run between now and then is a run with no data.

| | | Reads |
|---|---|---|
| **1. The record** | what is captured, at what grain, when | — |
| **2. The quality axis** | what "good" means, from a signal that is not an LLM grading an LLM | 1 |
| **3. The post-mortem** | how you get from a failure back to the task that caused it | 1, 2 |

The user's own list — *what to gather when asking an LLM to do a task, what to collect afterwards,
how many times the call had to be refined, which feature, which kind of task* — is all Part 1.

---

# Part 1 — The record

## What is delivered

| | |
|---|---|
| `C-FLOW-01` ✅ Cost Telemetry | every call → `model`, `task_type`, tokens, `estimated_cost_usd`, `duration_ms`, `run_id` |
| `B-SENS-01` ✅ Artifact Lineage Graph | `artifact_id`, `parent_id`, `run_id`, `event_type`, `model_id` |
| `D-FLOW-03` ✅ Static Model Routing | each task kind goes to the model configured for it |
| `E-FLOW-03` ✅ Provider registry | self-describing adapters. Registers **providers**, never models |

So *which model made this* and *what one call cost* are both solved.

## The grain is the gap — measured

The two ledgers **join on `run_id` alone**.

| `llm_usage_log` (`telemetry.py`, `UsageRecord`) | `flow_artifact_events` (`core/flow/store.py:17`) |
|---|---|
| `task_type` ✓ | `artifact_id`, `parent_id`, `model_id` ✓ |
| model, tokens, cost, `duration_ms` ✓ | `event_type` ✓ |
| **no artefact id** | **no `task_type`** |
| **no feature id** | **no feature id** |

One run holds many tasks and many artefacts. So today the system can answer *"what did run R cost
by task type"* and *"which model made artefact A"*, and **cannot** answer *"which model did the
design task for feature F, and what did it cost"* — which is the question.

**The feature identity exists at the moment it is discarded.** `feature_name_from_spec()`
(`core/flow/handlers/decomposition_artifacts.py:76`) and `_derive_feature_name()`
(`core/flow/handlers/draft.py:306`) compute it for rendering. Neither ledger stores it.

**There is no session identity and no task-instance identity.** `run_id` is a UUID for one pipeline
invocation (`core/flow/engine/state.py:107`), with `parent_run_id` for nesting. Nothing groups the
several invocations that one task takes.

### The grain the user requires

```
feature  →  task (kind + instance)  →  session(s)  →  call(s)
```

- **feature** — absent. Derivable today.
- **task instance** — absent. A task may span several sessions, and a post-mortem may narrow the
  fault to one or two tasks, so the instance must be separable from the kind.
- **session** — `run_id` can serve; one invocation is one session.
- **call** — `llm_usage_log` row. Exists.

## The task vocabulary is too short

`TaskType` (`infrastructure/llm/models.py:29`) is:

```
DRAFT · REVIEW · PLAN · IMPLEMENT · VALIDATE · CHECK · UNKNOWN
```

The kinds the user distinguishes include **analysis**, **investigation** and **research**. All three
land in `UNKNOWN` today. This enum is simultaneously the routing key (`ModelRouter.get_for_task`)
and a telemetry column, so widening it is a `T-NAME` decision, not a refactor.

## Cost is wider than dollars

`[agreed 2026-08-27]` **Wall-clock, not energy.** `duration_ms` is already recorded on every call
and **read by nothing**. A power sensor is a hardware dependency for a number that, on one machine,
is close to a constant multiple of a number already being thrown away. Revisit only if the constant
stops holding.

The self-hosting consequence is sharper than it first appears:

| Axis | State |
|---|---|
| tokens | measured |
| dollars | measured, and **about to be meaningless** for locally hosted work |
| wall-clock | measured, **read by nothing** |
| energy | not measured |

## `estimate_cost` returning `0.0` means two different things

`telemetry.py:84-86` returns `0.0` for any model absent from the cost table, with a
`logger.warning`. That currently conflates **this is free** with **I have no idea what this costs**.

Today that is a defect. Once a model is hosted locally it becomes a **daily** occurrence on purpose,
and the two readings must be told apart. `model_pricing_2026-08-16.md` already frames the choice —
*refuse, warn loudly, or record the cost as unknown rather than `0.00`* — and it is still open.

## The price table is materially wrong — re-measured 2026-08-27

`model_pricing_2026-08-16.md` said *"re-take the census before designing against it."* Done. It got
worse than that census recorded.

| Finding | Evidence |
|---|---|
| **Anthropic is priced at `$0.00` across the board** | the keys are `claude-4-6-sonnet` / `claude-4-6-opus` (`adapters/anthropic.py:59-61`); the real ids reverse those segments. `estimate_cost` does a plain dict lookup with **no normalisation**, so neither row can ever match |
| Opus 4.6 is priced 3× too high | `$15/$75` per 1M in the table; **$5/$25** in reality. Moot given the row is unreachable |
| Gemini Flash is ~10–19× too cheap | `gemini-3-flash-preview` is `$0.10/$0.40` (`adapters/gemini.py:81`); current Gemini 3.x Flash is **$0.75–$1.50 in, $3.75–$9 out** |

Underpricing makes a ceiling trip **late**. On the default provider, a `$25` breaker would let
roughly **$250–475** through before firing.

Current rates, for the record — Anthropic from the `claude-api` skill (cached 2026-06-24), the rest
from a 2026-08-27 web search:

| | $/1M in | $/1M out |
|---|---|---|
| Claude Opus 5 · 4.8 · 4.7 · 4.6 | 5 | 25 |
| Claude Sonnet 5 · Sonnet 4.6 | 3 | 15 |
| Claude Haiku 4.5 | 1 | 5 |
| Claude Fable 5 | 10 | 50 |
| Gemini 3 Pro (≤200K) | 2 | 12 |
| Gemini 3.6 Flash | 1.50 | 7.50 |
| Gemini 3.5 Flash-Lite | 0.30 | 2.50 |
| gpt-5.6-sol (after the 22 Aug cut) | 4 | 20 |
| gpt-5.6-terra | 2 | 12 |

Sources: [Gemini pricing 2026](https://www.cloudzero.com/blog/gemini-pricing/) ·
[Gemini 3 pricing](https://www.eesel.ai/blog/google-gemini-3-pricing) ·
[OpenAI pricing 2026](https://www.cloudzero.com/blog/openai-pricing/) ·
[OpenAI per-token table](https://www.morphllm.com/openai-api-pricing)

## Two ceilings are not configuration, though a delivered FR says they are

`B-FLOW-05` `FR-5` reads *"The ceilings are configuration... Reads `llm.max_spend_usd` and
`llm.max_tokens_per_run`"*. `factory.py:144-145` does read them off `settings.llm` — but
`_llm_settings()` (`core/config/bootstrap/settings_loader.py:102`) builds `LLMSettings` from the DB
profile and **never populates either field**. Both are always the Pydantic defaults
(`settings.py:70-71`). **There is no path by which an operator can change them.**

`C-FLOW-11` has the same hole: `load_settings_async` constructs `SpecWeaverSettings(...)` without
`autonomy=`, so `max_turns = 10` (`settings.py:147`) is equally unreachable.

---

# Part 2 — The quality axis

## The constraint, already established

`llm_routing_and_cost_analysis.md` §3.4 rules out an LLM judging an LLM: the Arbiter Paradox (a
hallucinated root cause poisons the whole metric), the cost of running an arbiter with weeks of
context, Goodhart's Law, and the delayed feedback loop. **Any quality signal used here has to be
deterministic and cheap.**

## The signal already exists, unjoined

SpecWeaver already produces deterministic, feature-level verdicts about a target project:

| | |
|---|---|
| the 12-test spec battery | spec quality |
| `C-VAL-04` ✅ Traceability Matrix Check | requirements ↔ tests |
| `D-VAL-01` ✅ QA Runner | the project's tests |
| `A-VAL-03` 🔜 Mutation Testing Gates | whether a test would notice the behaviour going away |

`B-SENS-01` knows which model produced the artefact. **Nothing writes down "the battery said X
about the thing model Y produced."** That join is the single largest gap in Part 2, and it is a
join, not an algorithm.

## Rework as the second signal

`B-FLOW-03`'s premise — *how much of a step's output did the next step have to throw away* — is
§3.2's Refactor-Adjusted Cost, which that analysis marked **feasible for single-pipeline
tracking**. It is deterministic, cheap, and not gameable by a model judging a model.

Two corrections came out of the grilling and are **not yet agreed**:

- **Record, do not flag.** The entry says *"a rewrite above 20% is flagged"*. Flagging discards
  everything below the threshold, so a post-mortem can never ask whether a step was unusually bad
  *for its kind of task*. A threshold is a display decision, not a storage decision.
- **The name is then wrong.** A capability that records feature, task instance, model, survival
  ratio **and** a verdict is not *Friction Detection* — friction is one of its columns.

## What `A-UI-02` is not

`A-UI-02` Standardized Benchmarking CI runs SWE-bench to prove **SpecWeaver** has not regressed
before a release. It is the wrong instrument for *which model suits which task* and should not be
counted toward it.

---

# Part 3 — The post-mortem

## It already has a capability, under another name

`A-FLOW-01` 🔜 Data-Driven Routing: *"Suggest a better model for a task from evidence — 'this model
causes three times the rework on planning' — and **leave the choice to the human**. Done when it
suggests and never auto-applies."* Preconditions: `C-FLOW-01` telemetry, `B-FLOW-03` friction.

**"The attribution engine"** appears in `C-FLOW-07`'s `Enables` field and in `TECH-033`'s design.
It is prose in both, minted nowhere — and on the evidence above it is `A-FLOW-01`. Correcting those
two references is a two-word edit, not a new capability.

## The walk-back path exists

A failure surfaces later than the step that caused it. `flow_artifact_events.parent_id` chains an
artefact to its parent and `model_id` names who made each one, so the walk back is already
traversable — once the rows carry feature and task identity (Part 1).

## Human labelling is the feasible half

`C-FLOW-07` 🔜 HITL Root-Cause Tagging captures *why* a human intervened. §3.3 is explicit that the
fault weight is *"unknowable without either human labeling (feasible) or an AI Arbiter
(speculative)"*. The roadmap already picked the feasible one.

---

# The capability map

Six delivered, nine unbuilt with no design, one contested. **No unbuilt one has a feature
directory.**

| Layer | ID | State |
|---|---|---|
| Record | `C-FLOW-01` Cost Telemetry | ✅ |
| Record | `B-SENS-01` Artifact Lineage Graph | ✅ |
| Record | `D-FLOW-03` Static Model Routing | ✅ |
| Record | `E-FLOW-03` Provider registry | ✅ |
| Record | `B-FLOW-03` Friction Detection | 🔜 no design |
| Record | `C-FLOW-07` HITL Root-Cause Tagging | 🔜 no design |
| Evaluate | `A-FLOW-01` Data-Driven Routing | 🔜 no design |
| Model facts | `C-FLOW-13` Model Catalogue | 🔜 no design |
| Model facts | `D-FLOW-05` Model Catalogue Adoption | 🔜 blocked on `C-FLOW-13` |
| Display | `C-UI-03` Analytics Dashboard | 🔜 no design |
| Display | `D-UI-06` REST API — Telemetry & Auditing | 🔜 no design |
| Quality | `C-VAL-04` · `D-VAL-01` | ✅ |
| Quality | `A-VAL-03` Mutation Testing Gates | 🔜 |
| Quality | `C-VAL-05` Rubrics-as-Content | 🔧 |
| Contested | `B-FLOW-05` Token-Burn Circuit Breakers | 🔧 |
| Not this | `A-UI-02` Standardized Benchmarking CI | 🔜 |

`[agreed 2026-08-27]` **A UI capability displays. It never collects or evaluates.** `C-UI-03` and
`D-UI-06` are edges — a dashboard and an HTTP surface — and the evaluation belongs in the flow
domain regardless of which capability ends up owning it.

`[agreed 2026-08-27]` **Do not scatter this across more capabilities than it needs.** The map above
already holds every layer; the working assumption is that this needs **no new capability**, and any
proposal to mint one has to argue against that first.

`[agreed 2026-08-27]` **`B-SENS-01` being `✅` is not a wall.** It delivered what it promised —
*every generated artifact traces back to the model and request that made it*. The requirement has
grown to *per feature, per task kind*, and a changed requirement gets a follow-up rather than being
treated as a defect in closed work.

## `B-FLOW-05` is contested and still unanswered

Its topic entry has said this since 2026-08-19 and still does:

> ⚠️ **Contested.** Built as a spend guard — two ceilings that stop a run. The user states its real
> value is a number for choosing which model suits which task. **The title and the design disagree
> with the user. Needs you**

The entry also notes it shares one benefit with `C-UI-03` and `D-UI-06` — three capabilities, one
benefit, flagged and never resolved.

The argument that emerged here, **not agreed**: a runaway loop needs a stop whether or not anyone is
choosing models, and the two have opposite requirements — a breaker must be certain and cheap, the
routing evidence is fuzzy and expensive. Merging them makes the certain thing depend on the fuzzy
one.

---

# Open questions

Every one of these went to the user and none is answered. None has a default.

1. **What is `B-FLOW-05`?** A spend guard, or the measurement that feeds model choice. `T-SCOPE`.
2. **Does the assessment record and not flag?** And if it records, is it still called *Friction
   Detection*? `T-NAME`, `T-SCOPE`.
3. **Where do `feature` and the exact join key land** — widening the two delivered ledgers, or a new
   table that would carry a second copy of model and cost? `T-ARCH`, and `PRINCIPLES.md` §5 bears on
   it.
4. **What does a missing price mean** — refuse, warn, or record unknown? `T-POSTURE`, and
   self-hosting makes it live.
5. **Does `TaskType` grow** to carry analysis, investigation and research, and who owns that? `T-NAME`.
6. **The dollar ceiling number.** `$25` was an agent's guess and remains one. `T-SPEND`.

## What must not be re-derived

- `llm_routing_and_cost_analysis.md` — credit assignment, RAC, ALS, the Arbiter Paradox. Still correct.
- `model_pricing_2026-08-16.md` — the census and the catalogue argument. Its instruction to re-take
  the census before designing was followed on 2026-08-27; the results are in Part 1.
- The measurements in Part 1. Each carries a `file:line`; re-check rather than re-discover.
