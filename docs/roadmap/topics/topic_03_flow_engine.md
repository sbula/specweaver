# Topic 03: Flow Orchestration (Nervous System)

Capabilities for the pipeline runner, routing, state management, and telemetry.

Seven keyed fields per entry, no prose (`R-ENTRY`). Values are written plainly.
**🟡 marks a guess** · **🔴 marks nothing found**. Markers are the exception.

## DAL-E: Prototyping

* **`E-FLOW-01` ✅: Config DB** (Legacy: Step 8)
  > - **Purpose:** One place to keep settings for many projects, so thresholds and config survive between runs
  > - **Trigger:** When any command reads or writes configuration
  > - **Needs:** —
  > - **Reads:** `~/.specweaver/` on disk
  > - **Produces:** db → SQLite config, per-project, with per-rule thresholds
  > - **Enables:** multi-project management · configurable validation rules
  > - **Done when:** a threshold set for one project does not affect another

* **`E-FLOW-02` ✅: YAML Pipelines** (Legacy: Step 10)
  > - **Purpose:** Define what a pipeline *is* — steps, gates, targets — as data a user can write, before anything runs it
  > - **Trigger:** When a pipeline file is parsed
  > - **Needs:** —
  > - **Reads:** pipeline YAML
  > - **Produces:** memory → a parsed step model (action + target) and gate definitions
  > - **Enables:** `D-FLOW-01` → the runner that executes it
  > - **Done when:** a pipeline file parses to a step model. No execution — that is the runner's job

* **`E-FLOW-03` ✅: Multi-Provider Registry** (Legacy: 3.13)
  > - **Purpose:** Add an LLM provider by dropping in one file, with no other change anywhere
  > - **Trigger:** At import, when adapters are scanned
  > - **Needs:** —
  > - **Reads:** `llm/adapters/` — each adapter self-describes its name, key variable and costs
  > - **Produces:** memory → a provider registry
  > - **Enables:** the adapter factory · `sw config set-provider` · `D-FLOW-03` routing
  > - **Done when:** adding a provider is one file and zero other changes
  > - **Note:** registers PROVIDERS only. Nothing registers MODELS — that gap is `C-FLOW-13`

## DAL-D: Internal Tooling

* **`D-FLOW-01` ✅: Pipeline Runner** (Legacy: Step 11)
  > - **Purpose:** Execute a pipeline and remember where it got to, so a run can be resumed rather than restarted
  > - **Trigger:** When a pipeline is run
  > - **Needs:** `E-FLOW-02` → the parsed step model
  > - **Reads:** the pipeline definition and prior run state
  > - **Produces:** db → run and step state in SQLite
  > - **Enables:** `D-FLOW-02` · `D-FLOW-04` · every pipeline capability
  > - **Done when:** a pipeline runs and its state survives a resume

* **`D-FLOW-02` ✅: sw run CLI** (Legacy: Step 13)
  > - **Purpose:** Start and watch a pipeline from the terminal, with errors that read as one clear line
  > - **Trigger:** When a user runs `sw run`
  > - **Needs:** `D-FLOW-01` → the runner
  > - **Reads:** the named pipeline
  > - **Produces:** console → step-by-step progress · `--json` output · file-based logs
  > - **Enables:** every user-driven pipeline run
  > - **Done when:** a failing run prints a friendly one-liner rather than a trace

* **`D-FLOW-03` ✅: Static Model Routing** (Legacy: 3.14)
  > - **Purpose:** Send each kind of task to the model the user chose for it — review to one, implement to another
  > - **Trigger:** When a task needs a model
  > - **Needs:** `E-FLOW-03` → the provider registry
  > - **Reads:** the task type and the user's config
  > - **Produces:** memory → a resolved provider and model
  > - **Enables:** every LLM call
  > - **Done when:** a task type maps to a model by configuration alone — no learning, no inference

* **`D-FLOW-04` ✅: Unified Runner Architecture** (Legacy: 3.16)
  > - **Purpose:** Make every command run through the same machinery, so telemetry and state work identically whether it is one step or twenty
  > - **Trigger:** When any single-shot command runs
  > - **Needs:** `D-FLOW-01` → the runner
  > - **Reads:** —
  > - **Produces:** a dynamic one-step pipeline per command
  > - **Enables:** `sw review` · `sw draft` and every other single-shot command
  > - **Done when:** a single-shot command is telemetered and state-tracked like a pipeline

* **`D-FLOW-05` 🔜: Model Catalogue Adoption**
  > - **Purpose:** Move every consumer of model facts onto one catalogue and delete the per-adapter cost tables, so pricing has a single source
  > - **Trigger:** When a model's price or capability is looked up
  > - **Needs:** `C-FLOW-13` → the catalogue. **Blocked on it**
  > - **Reads:** the model catalogue
  > - **Produces:** consumers reading one source · `sw costs` showing built-in rates, not only overrides
  > - **Enables:** honest cost reporting — today `sw costs` cannot show the 19 default rates runs are actually priced with
  > - **Done when:** no `default_costs` dict remains in any adapter

## DAL-C: Enterprise Standard

* **`C-FLOW-01` ✅: Cost Telemetry** (Legacy: 3.12)
  > - **Purpose:** Record what every LLM call cost and which task it served, so spend can be seen rather than guessed
  > - **Trigger:** On every LLM call
  > - **Needs:** `E-FLOW-03` → provider and cost data
  > - **Reads:** each request's model, prompt tokens and completion tokens
  > - **Produces:** db → usage records with estimated cost and task type
  > - **Enables:** `sw usage` · `sw costs` · `D-UI-06` · `B-FLOW-03` · `A-FLOW-01`
  > - **Done when:** every call lands in the ledger attributed to a task type

* **`C-FLOW-02` ✅: Router-Based Control** (Legacy: 3.25)
  > - **Purpose:** Send a spec down a different path depending on what it is — simple to a fast track, complex to full decomposition
  > - **Trigger:** When a step carries a `router` key
  > - **Needs:** `D-FLOW-01` → the runner
  > - **Reads:** the assessment of the work in hand
  > - **Produces:** a chosen branch through the pipeline
  > - **Enables:** `C-FLOW-10` → deferred routing on top
  > - **Done when:** one pipeline takes two different paths for two different inputs

* **`C-FLOW-03` ✅: Multi-Spec Fan-Out** (Legacy: 3.27)
  > - **Purpose:** Run independent components in parallel safely — predicting which files each will touch, so they cannot collide
  > - **Trigger:** When decomposition produces several component specs
  > - **Needs:** `D-SENS-01` → the topology graph, to predict blast radius
  > - **Reads:** component specs and their predicted file impact
  > - **Produces:** child pipelines in isolated sandboxes, each with a `SW_PORT_OFFSET` hash
  > - **Enables:** parallel component delivery without merge conflicts or port collisions
  > - **Done when:** disjoint components run fully in parallel and the parent waits for all children

* **`C-FLOW-04` 🔜: Work Packet Bundling** (Legacy: 3.49)
  > - **Purpose:** Group tiny independent components into one worktree, so the overhead of isolation does not exceed the work
  > - **Trigger:** 🟡 When fan-out would produce many very small components
  > - **Needs:** `C-FLOW-03` → the fan-out it optimises
  > - **Reads:** the component set and its sizes
  > - **Produces:** 🟡 aggregated work packets, one worktree each
  > - **Enables:** 🟡 lower git I/O and fewer context initialisations
  > - **Done when:** 🔴

* **`C-FLOW-05` ✅: Interactive Gate Variables (HITL)** (Legacy: 3.26c)
  > - **Purpose:** When a human rejects something, make that rejection outrank a linter finding on the retry — the person is more right than the tool
  > - **Trigger:** When a HITL gate is rejected and generation loops back
  > - **Needs:** `D-FLOW-01` → gate state
  > - **Reads:** the human's rejection text
  > - **Produces:** prompt → a `<dictator-overrides>` section weighted above ordinary findings
  > - **Enables:** loop-back generation that acts on the human's reason first
  > - **Done when:** a human rejection outranks a linter error in the next prompt

* **`C-FLOW-06` ✅: Refactoring Phase 3 Optimizations** (Legacy: 3.32d)
  > - **Purpose:** Cut token and time cost on the paths that were measurably expensive — condense context, limit tests by impact, route context dynamically
  > - **Trigger:** Various — per optimisation
  > - **Needs:** `D-SENS-02` → AST skeletons · `D-SENS-01` → impact data
  > - **Reads:** source files and the topology graph
  > - **Produces:** condensed context · impact-limited test selection · DAL risk evaluation · standards scaffolding
  > - **Enables:** cheaper runs across the board
  > - **Done when:** all five optimisations are in place with DI boundaries intact

* **`C-FLOW-07` 🔜: HITL Root-Cause Tagging** (Legacy: 5.5a)
  > - **Purpose:** When a human has to step in, capture *why* — bad spec, hallucination — so failures can be attributed rather than merely counted
  > - **Trigger:** When a human intervenes at a gate
  > - **Needs:** 🟡 `B-FLOW-03` → friction events to attach a reason to
  > - **Reads:** the human's chosen tag
  > - **Produces:** 🟡 a tagged friction record
  > - **Enables:** the attribution engine · `A-FLOW-01` routing suggestions
  > - **Done when:** 🔴

* **`C-FLOW-08` 🔜: Pluggable Webhook & CI Invocation**
  > - **Purpose:** 🟡 Let a successful run kick off something outside SpecWeaver — a CI job, a notification
  > - **Trigger:** On successful validation
  > - **Needs:** `D-FLOW-01` → run outcome
  > - **Reads:** 🟡 webhook configuration
  > - **Produces:** 🟡 authenticated webhook calls · Jenkins / GitHub Actions triggers
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`C-FLOW-09` 🔜: DAL CI/CD Risk Evaluation**
  > - **Purpose:** Reject a change that degrades the architecture — a lower-assurance module reaching into a higher one
  > - **Trigger:** 🟡 On a pull request
  > - **Needs:** `D-SENS-01` → the topology graph · DAL assignments
  > - **Reads:** the changed imports
  > - **Produces:** 🟡 an accept/reject verdict on the change
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Gate:** do not design per-level behaviour yet. Every live DAL consumer decides strict-or-relaxed only; the real tier count is an empirical question the trading project answers

* **`C-FLOW-10` 🔜: Deferred Router Mapping** (Legacy: 3.25)
  > - **Purpose:** Let a route wait for something — pause at a gate, persist, and pick the branch when the answer arrives
  > - **Trigger:** When a routed step cannot decide yet
  > - **Needs:** `C-FLOW-02` → basic routing · `D-FLOW-01` → state persistence
  > - **Reads:** persisted `GATE_PENDING` state
  > - **Produces:** 🟡 a suspended run that resumes on the deferred decision
  > - **Enables:** 🟡 `INT-US-04-SF05` advanced routing
  > - **Done when:** 🔴

* **`C-FLOW-11` 🔧: Graduated Autonomy — DAL-Driven Execution-Mode Dial**
  > - **Purpose:** Let how much freedom the agent gets be a setting, not a constant — tight on critical work, loose on cheap work
  > - **Trigger:** When a step runs and its mode is read
  > - **Needs:** `D-FLOW-01` → the runner · the run's DAL · `B-FLOW-05` → the spend ceiling
  > - **Reads:** the step's `mode: oneshot | agentic` · `[autonomy]` install settings
  > - **Produces:** either a single-shot call, or a bounded tool loop behind a replaceable `AgentRuntime`
  > - **Enables:** agentic execution where the DAL permits it
  > - **Done when:** a run refuses `agentic` above `agentic_max_dal`, and `oneshot` behaves exactly as before
  > - **Not wired:** `sw implement` still runs one-shot, so no user path reaches `agentic` mode

* **`C-FLOW-12` 🔜: Autonomous DAG Execution**
  > - **Purpose:** Actually execute the decomposed DAG — `INT-US-21` produces the plan and deliberately stops before running it
  > - **Trigger:** 🟡 When a decomposition has produced a component DAG
  > - **Needs:** `C-EXEC-07` · `TECH-014` → **sequenced behind both**
  > - **Reads:** the decomposition output
  > - **Produces:** 🟡 per-component specs, race-hardened fan-out, `proposed_dal`-driven isolation
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Note:** writes its own seam pin as its first commit; the base ships none, `FR-9(a)` having been descoped

* **`C-FLOW-13` 🔜: Model Catalogue**
  > - **Purpose:** One versioned file holding every model's price, adapter and capabilities — so a new model is a data change, not a source change and a release
  > - **Trigger:** When a model fact is looked up
  > - **Needs:** —
  > - **Reads:** the catalogue file
  > - **Produces:** pricing · serving adapter · capabilities · how stale each answer is
  > - **Enables:** `D-FLOW-05` → the consumers that switch over
  > - **Done when:** an unknown model does not silently price at `$0.00`
  > - **Measured:** 19 rates live in five adapter classes · `qwen.py` untouched since 2026-05-04 · three entries are retired preview builds · `*-latest` aliases price a moving target with a
  >   fixed number

## DAL-B: High-Assurance

* **`B-FLOW-01` ✅: Scenario Testing Pipeline** (Legacy: 3.28)
  > - **Purpose:** Run the code pipeline and a scenario pipeline side by side, so when they disagree the cause can be attributed
  > - **Trigger:** When a scenario pipeline is run
  > - **Needs:** `D-FLOW-01` → the runner
  > - **Reads:** structured YAML scenarios · Python Protocol contracts
  > - **Produces:** a JOIN gate verdict · an arbiter agent's error attribution
  > - **Enables:** contract-first delivery
  > - **Done when:** both pipelines meet at a JOIN gate and a failure is attributed to one side

* **`B-FLOW-02` 🔜: OpenTelemetry Agent Tracing** (Legacy: 3.44)
  > - **Purpose:** 🟡 See a run's internal structure in the tools an enterprise already uses, instead of only in SpecWeaver's own logs
  > - **Trigger:** While a pipeline runs
  > - **Needs:** `D-FLOW-01` → the run hierarchy
  > - **Reads:** runner state transitions
  > - **Produces:** OTel spans to an endpoint — Jaeger, Datadog
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`B-FLOW-03` 🔜: Friction Detection** (Legacy: 4.5c)
  > - **Purpose:** Notice when one agent has to rewrite most of what a previous agent produced, and attribute that cost upstream
  > - **Trigger:** When a downstream step modifies upstream output
  > - **Needs:** `C-FLOW-01` → telemetry to attribute against
  > - **Reads:** `git diff` between the two outputs
  > - **Produces:** 🟡 a friction event attributed to the upstream model
  > - **Enables:** `C-FLOW-07` tagging · `A-FLOW-01` routing suggestions
  > - **Done when:** 🟡 a rewrite above 20% is flagged. Pure diff maths — no LLM

* **`B-FLOW-04` 🔜: Hybrid RAG Orchestration** (Legacy: 5.4)
  > - **Purpose:** Find candidate code from a fuzzy description, then hand those candidates to the graph for exact expansion — the **locate** step
  > - **Trigger:** When a task needs to find relevant code without an exact symbol name
  > - **Needs:** `A-SENS-02` → vectors · `B-SENS-03` → chunks
  > - **Reads:** the vector store
  > - **Produces:** memory → ranked candidates, scored by semantic similarity, recency decay and importance
  > - **Enables:** `B-SENS-09` → exact graph closure over the candidates
  > - **Done when:** 🔴
  > - **Rule:** its output never feeds a gate or a blast radius. No correctness decision consumes vector output (`ADR-006` decision 3)

* **`B-FLOW-05` 🔧: Token-Burn Circuit Breakers**
  > - **Purpose:** ⚠️ **Contested.** Built as a spend guard — two ceilings that stop a run. The user states its real value is a number for choosing which model suits which task. **The title
  >   and the design disagree with the user. Needs you**
  > - **Trigger:** Before every LLM request, and after every completed call
  > - **Needs:** `C-FLOW-01` → token and cost data
  > - **Reads:** `llm.max_spend_usd` · `llm.max_tokens_per_run` · accumulated usage
  > - **Produces:** a run that stops and names the ceiling it hit
  > - **Enables:** `C-FLOW-11` → the cap on an agentic loop
  > - **Done when:** a run exceeding either ceiling stops and says which one
  > - **Blocked on:** where LLM limits live — see its design and `STATE.md`. `D-UI-06` and `C-UI-03` share this benefit

## DAL-A: Mission-Critical

* **`A-FLOW-01` 🔜: Data-Driven Routing** (Legacy: 4.5d)
  > - **Purpose:** Suggest a better model for a task from evidence — "this model causes three times the rework on planning" — and leave the choice to the human
  > - **Trigger:** 🟡 When enough telemetry and friction data exists
  > - **Needs:** `C-FLOW-01` → telemetry · `B-FLOW-03` → friction events
  > - **Reads:** the telemetry and friction ledgers
  > - **Produces:** 🟡 model-swap suggestions
  > - **Enables:** the human choosing a model on evidence
  > - **Done when:** 🟡 it suggests and never auto-applies

* **`A-FLOW-02` 🔜: Hash GC** (Legacy: 5.3)
  > - **Purpose:** 🟡 Remove graph nodes whose code is gone, so the store does not grow forever
  > - **Trigger:** 🔴
  > - **Needs:** `A-SENS-01` → hashes · `B-SENS-02` → the nodes
  > - **Reads:** 🟡 the node set and current hashes
  > - **Produces:** 🔴
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`A-FLOW-03` 🔜: Dead Code Detection & Analysis** (Legacy: 5.9)
  > - **Purpose:** Find code nothing can reach, and hand a human the list to judge — not delete it automatically
  > - **Trigger:** 🟡 On demand
  > - **Needs:** `B-SENS-02` → reachability edges · `A-SENS-02` → the Postgres graph at scale
  > - **Reads:** the persistent topology graph
  > - **Produces:** 🟡 a report of unreachable functions and methods
  > - **Enables:** human review → keep or delete
  > - **Done when:** 🔴

* **`A-FLOW-04` 🔜: Blast-Radius Circuit Breaker**
  > - **Purpose:** Stop an autonomous fix that would touch more of the system than it is allowed to
  > - **Trigger:** Before an autonomous hotfix is applied
  > - **Needs:** `B-SENS-02` → graph traversal · `TECH-068` and `B-SENS-08` → complete edges
  > - **Reads:** the knowledge graph, same seam as `B-EXEC-03`
  > - **Produces:** 🟡 a halt when the topological impact exceeds tolerance
  > - **Enables:** 🔴
  > - **Done when:** 🔴
