# Topic 04: Master Brain (Intelligence)

Capabilities for LLM integration, specification logic, and AI decision-making.

Seven keyed fields per entry, plus optional `Limits:` and `Note:` — no prose (`R-ENTRY`). Values are written plainly.
**🟡 marks a guess** · **🔴 marks nothing found**. Markers are the exception.

## DAL-E: Prototyping

* **`E-INTL-01` ✅: LLM Adapter** (Legacy: Step 3)
  > - **Purpose:** Talk to a language model through one interface, so the rest of the system never knows which provider it is
  > - **Trigger:** When any capability needs a model
  > - **Precondition:** —
  > - **Reads:** provider credentials and settings
  > - **Produces:** memory → model responses through a provider-agnostic call
  > - **Enables:** every LLM-dependent capability · the S03/S07 spec rules · the S04 dependency-direction rule
  > - **Done when:** a rule or workflow calls a model without naming a provider

* **`E-INTL-02` ✅: Spec Drafting** (Legacy: Step 4)
  > - **Purpose:** Write a spec with the model rather than from a blank page, stopping for the human at each decision
  > - **Trigger:** When a user runs `sw draft`
  > - **Precondition:** `E-INTL-01` → the model
  > - **Reads:** the user's answers and the project context
  > - **Produces:** file → a drafted spec
  > - **Enables:** `E-INTL-03` → the review it hands off to
  > - **Done when:** a spec is produced through an interactive loop with HITL stops

* **`E-INTL-03` ✅: Spec Review Engine** (Legacy: Step 4)
  > - **Purpose:** Judge a spec or a piece of code on meaning, not just on rules a regex can check
  > - **Trigger:** When `sw review` runs, or drafting hands off
  > - **Precondition:** `E-INTL-01` → the model · `C-VAL-05` → the criteria it judges against
  > - **Reads:** the spec or code under review
  > - **Produces:** memory → a verdict with findings
  > - **Enables:** every review gate
  > - **Done when:** a semantic verdict is produced and parsed reliably

## DAL-D: Internal Tooling

* **`D-INTL-01` ✅: Implementation Generator** (Legacy: Step 5)
  > - **Purpose:** Turn an approved spec into code and tests, then check the result — the loop the product exists for
  > - **Trigger:** When a user runs `sw implement`
  > - **Precondition:** `E-INTL-01` → the model · the validation battery
  > - **Reads:** the spec
  > - **Produces:** file → generated code and tests
  > - **Enables:** spec → code → tests → validation → review, end to end
  > - **Done when:** the full loop runs from a spec to a reviewed implementation

* **`D-INTL-02` ✅: Feature Decomposition** (Legacy: 3.1)
  > - **Purpose:** Split a feature too big to build in one pass into components that can each be specified and built
  > - **Trigger:** When a spec is a feature rather than a component
  > - **Precondition:** `E-INTL-01` → the model
  > - **Reads:** the feature spec
  > - **Produces:** file → component specs · a decomposition artifact
  > - **Enables:** `C-INTL-01` · `C-FLOW-03` fan-out · `C-FLOW-12` execution
  > - **Done when:** a feature spec yields component specs scored by confidence

* **`D-INTL-03` ✅: Explicit Plan Phase** (Legacy: 3.6)
  > - **Purpose:** Decide architecture, stack and constraints on the record *before* code is generated, instead of discovering them in the output
  > - **Trigger:** Between validate and implement
  > - **Precondition:** `E-INTL-01` → the model
  > - **Reads:** the validated spec
  > - **Produces:** file → a structured plan artifact · 🟡 UI mockups via Google Stitch
  > - **Enables:** `D-INTL-01` → generation against a decided plan
  > - **Done when:** architecture decisions exist as an artifact before generation runs

* **`D-INTL-04` ⚰️ RETIRED:** *(Design Questionnaire — absorbed into `D-INTL-07` Agentic Interview
  Drafting as a second rubric, 2026-08-27. Both are one adaptive interview over different rubrics
  producing different artefacts; two capabilities described one machine. Legacy 3.52; its
  architecture note survives at `../../architecture/06_lessons_and_future/synthetic_commons_and_questionnaire_design.md`
  — goal and output still stand, the fixed CLI wizard does not. ID is dead — do NOT reuse; the gap
  to `D-INTL-05` is intentional.)*

* **`D-INTL-05` ✅: Project Metadata Injection** (Legacy: 3.15)
  > - **Purpose:** Tell the model what project it is in — name, archetype, language, date — so it stops guessing context it could have been given
  > - **Trigger:** When a system prompt is built
  > - **Precondition:** `E-FLOW-01` → project config
  > - **Reads:** project name, archetype, language target, date, active config
  > - **Produces:** prompt → a metadata block in the system prompt
  > - **Enables:** every LLM call
  > - **Done when:** the model is told its project rather than inferring it

* **`D-INTL-06` ✅: Context Hydration & Handover Engine**
  > - **Purpose:** Carry task state and blockers between agents without the next one inheriting the previous one's hallucinations
  > - **Trigger:** When an agent's prompt is built, or work passes between agents
  > - **Precondition:** `B-INTL-09` → the Memory Bank
  > - **Reads:** active task state, blockers, handover notes
  > - **Produces:** prompt → structured context, Pydantic-validated, within an 8 KB token limit
  > - **Enables:** multi-agent handover
  > - **Done when:** context passes between agents validated, not copied wholesale

* **`D-INTL-07` 🔴: Agentic Interview Drafting (Grill-Style)**
  > - **Purpose:** Draft by adaptive interview rather than a fixed questionnaire — ask what this project needs asking, not a stock list
  > - **Trigger:** When a user drafts a spec, or bootstraps a greenfield project
  > - **Precondition:** `C-FLOW-11` → **BLOCKED on it** · `C-VAL-05` → soft dependency, rubric content
  > - **Reads:** the user's answers · rubric guidance as content
  > - **Produces:** file → a spec meeting SpecWeaver's contract · file → a **localized** `context.yaml` for a greenfield project
  > - **Enables:** `INT-US-02-SF03` · greenfield bootstrap without a blank canvas
  > - **Done when:** the unchanged `INT-US-02` gates pass on an interview-drafted spec
  > - **Note:** absorbs the former `D-INTL-04` (2026-08-27) — one interview harness, two rubrics, two artefacts

* **`D-INTL-08` 🔜: Polyglot Implementation Loop**
  > - **Purpose:** Let `sw implement` target a language other than Python — five runners exist and no user path can reach them
  > - **Trigger:** When `sw implement` runs against a non-Python project
  > - **Precondition:** `D-VAL-03` → the five shipped language runners
  > - **Reads:** the project's manifest, to sniff the language
  > - **Produces:** generated code in the target language
  > - **Enables:** every non-Python journey
  > - **Done when:** a non-Python target is implemented end to end
  > - **Note:** paths, artifact tags and the fence stripper are hardcoded to `.py` at four points, and no `--language` flag exists. Builds no runner — routes to the ones that exist

## DAL-C: Enterprise Standard

* **`C-INTL-01` ✅: Iterative Decomposition** (Legacy: 3.24)
  > - **Purpose:** Decompose repeatedly with quality gates between passes, rather than accepting a first split
  > - **Trigger:** When decomposition runs
  > - **Precondition:** `D-INTL-02` → the basic decomposition
  > - **Reads:** the feature spec and each pass's output
  > - **Produces:** feature → sub-features → components
  > - **Enables:** `C-FLOW-12` execution
  > - **Done when:** 🔴
  > - **Limits:** designed as multi-level and **shipped single-pass**. `AD-2` and the agent-sized split heuristic were never built and never descoped — that is `C-INTL-07`

* **`C-INTL-02` ✅: MCP Client Architecture** (Legacy: 3.32c)
  > - **Purpose:** Speak the Model Context Protocol, so external systems plug in through a standard instead of a bespoke integration each time
  > - **Trigger:** When an external context source is used
  > - **Precondition:** —
  > - **Reads:** MCP servers over JSON-RPC on stdio
  > - **Produces:** memory → context from external tools, via proxy agents and lazy resource URIs
  > - **Enables:** future Jira, Confluence and similar integrations · the MCP Explorer tool
  > - **Done when:** an external MCP source supplies context without bespoke code

* **`C-INTL-03` 🔜: Reverse-Weaving** (Legacy: 3.43)
  > - **Purpose:** Produce a baseline spec for code that never had one, so a legacy system can enter the workflow at all
  > - **Trigger:** 🟡 When adopting an existing codebase
  > - **Precondition:** `D-SENS-02` → AST skeletons
  > - **Reads:** legacy source · PDFs and diagrams, multi-modally
  > - **Produces:** 🟡 draft baseline spec documents
  > - **Enables:** brownfield adoption
  > - **Done when:** 🔴

* **`C-INTL-04` 🔜: Conversation Summarization** (Legacy: 4.6)
  > - **Purpose:** Keep a long drafting conversation inside the context window by summarising old turns and keeping recent ones whole
  > - **Trigger:** When the context window fills
  > - **Precondition:** `E-INTL-01` → the model
  > - **Reads:** prior conversation turns
  > - **Produces:** prompt → recent turns plus a summary of the rest
  > - **Enables:** long drafting and review sessions
  > - **Done when:** 🔴

* **`C-INTL-05` ✅: Configurable Prompt Render Profiles**
  > - **Purpose:** Change what a prompt contains and in what order by configuration, instead of editing the renderer every time a context source is added
  > - **Trigger:** When a prompt is rendered
  > - **Precondition:** —
  > - **Reads:** the active render profile
  > - **Produces:** prompt → blocks rendered per profile
  > - **Enables:** the 2-tier handover standard · every capability adding a context source
  > - **Done when:** adding a context source needs no change to the renderer

* **`C-INTL-06` 🔜: Envelope-vs-Content Prompt Externalization**
  > - **Purpose:** Keep the prompt's *structure* in code and move its *content* to files, so what the agent is told can change without a release
  > - **Trigger:** When a prompt is assembled, in either execution mode
  > - **Precondition:** `C-INTL-05` → profiles · `C-FLOW-11` → work units that read the files directly
  > - **Reads:** mounted files — constitution, standards, agent memory
  > - **Produces:** prompt → a deterministic envelope referencing external content
  > - **Enables:** one source of truth for both `oneshot` and `agentic`
  > - **Done when:** 🟡 shipped `C-INTL-05` behaviour is unchanged
  > - **Note:** redirects `TECH-006`'s factory-centralization destination. Part of the "middle way" trio with `C-FLOW-11` and `C-VAL-05`

* **`C-INTL-07` 🔜: Multi-Level Recursive Decomposition**
  > - **Purpose:** Build the multi-level decomposition `C-INTL-01` was designed for and shipped without
  > - **Trigger:** When decomposition needs more than one level
  > - **Precondition:** `D-INTL-02` · `C-INTL-01` → what shipped
  > - **Reads:** the decomposition plan
  > - **Produces:** a nested component structure — a schema change, since `DecompositionPlan.components` is flat
  > - **Enables:** `C-FLOW-12` → which executes the fan-out, and is not this
  > - **Done when:** 🔴
  > - **Note:** the persisted artifact is a frozen `INT-US-21` seam that `C-FLOW-12` consumes, so this is a schema change before a control-flow one

## DAL-B: High-Assurance

* **`B-INTL-01` ✅: Archetype Rule Sets** (Legacy: 3.29)
  > - **Purpose:** Apply the standards a given kind of project actually has, without the user configuring them by hand
  > - **Trigger:** When a project's archetype is known
  > - **Precondition:** `E-FLOW-01` → project config
  > - **Reads:** the archetype — `kotlin-service`, `rust-worker` and similar
  > - **Produces:** auto-provisioned rules bound to that archetype
  > - **Enables:** framework-appropriate validation without hand configuration
  > - **Done when:** an archetype provisions its own rules and plugins

* **`B-INTL-02` ✅: Macro Evaluator** (Legacy: 3.30)
  > - **Purpose:** Show the model what the code *becomes*, not what it says — a derive macro or a Spring annotation generates behaviour the raw signature hides
  > - **Trigger:** When a file using such a construct is indexed
  > - **Precondition:** `D-SENS-02` → the parsed AST
  > - **Reads:** Rust procedural macros · Kotlin compiler plugins · Spring Boot annotations
  > - **Produces:** memory → unrolled runtime reality
  > - **Enables:** `B-SENS-08` → the same schemas, as edges rather than comments
  > - **Done when:** an annotated symbol reports what it expands to

* **`B-INTL-03` 🔜: Synthetic Commons** (Legacy: 3.51)
  > - **Purpose:** Notice that several components need the same thing, and factor it out *before* they each build their own
  > - **Trigger:** When decomposition has produced sub-features
  > - **Precondition:** `D-INTL-02` → the decomposition
  > - **Reads:** drafted sub-features
  > - **Produces:** 🟡 a synthetic "Tier 0" feature holding the shared parts
  > - **Enables:** components sharing logic instead of duplicating it in parallel
  > - **Done when:** 🔴

* **`B-INTL-04` 🔮: Dynamic AI Arbiter** (Legacy: 5.8)
  > - **Purpose:** 🟡 Pick a model automatically from a score attributed across the lifecycle
  > - **Trigger:** 🔴
  > - **Precondition:** a persistent knowledge graph · labelled training data (`C-FLOW-07`) · a solution to credit assignment
  > - **Reads:** 🟡 telemetry, friction and outcome data
  > - **Produces:** 🟡 automatic model selection
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Note:** the entry itself calls this science fiction today

* **`B-INTL-05` 🔜: Dynamic Tool Gating via Archetypes** (Legacy: 3.30a)
  > - **Purpose:** Give an agent only the tools its role should have, decided by the project's archetype rather than handed out uniformly
  > - **Trigger:** At generation runtime, when tool definitions are assembled
  > - **Precondition:** `B-INTL-01` → archetypes · `C-FLOW-11` → the role model
  > - **Reads:** the active archetype from `context.yaml`
  > - **Produces:** a filtered set of JSON Schema tool definitions
  > - **Enables:** framework-appropriate agent capability
  > - **Done when:** 🔴
  > - **Note:** the tool-allowlist half of "role = tools + mounted skills + DAL-scoped gates". Skill-mounting is the other half — design jointly with `C-FLOW-11`

* **`B-INTL-06` 🔜: Multi-Agent Isolation Patterns** (Legacy: 4.5)
  > - **Purpose:** Keep agents reviewing the same thing from contaminating each other, so several opinions stay independent
  > - **Trigger:** 🟡 When more than one agent works on one subject
  > - **Precondition:** `C-FLOW-11` → single-agent work units · `C-EXEC-06` → session isolation
  > - **Reads:** —
  > - **Produces:** 🟡 N isolated work units
  > - **Enables:** multi-agent review without collective hallucination
  > - **Done when:** 🔴
  > - **Note:** multi-agent is N work units, not a separate execution substrate

* **`B-INTL-07` 🔜: Error Attribution Arbiter**
  > - **Purpose:** When a scenario test fails, judge whether the code is wrong or the scenario is — a question a pass/fail cannot answer
  > - **Trigger:** At the JOIN gate of the scenario pipeline
  > - **Precondition:** `B-FLOW-01` → the JOIN gate · `E-INTL-01` → the model
  > - **Reads:** the test failure, the code, and the YAML scenario
  > - **Produces:** 🟡 an attribution verdict — code at fault, or scenario at fault
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`B-INTL-08` 🔮: Semantic Code Review**
  > - **Purpose:** Explain how a change alters call and dataflow chains, **beside** the text diff — not instead of it
  > - **Trigger:** 🟡 When a change is reviewed
  > - **Precondition:** `B-VAL-07` → the graph diff · `C-VAL-05` → review criteria as rubric content
  > - **Reads:** the graph diff and the change
  > - **Produces:** 🟡 a review narrative accompanying the diff
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Limits:** does not replace text diffs — that wording named a consumer that cannot exist — nobody reads a dataflow-graph diff instead of code

* **`B-INTL-09` 🟡: Agent Memory Bank**
  > - **Purpose:** Give agents a durable place to keep tasks, dependencies and defects, so work survives a session ending
  > - **Trigger:** When an agent records or reads task state
  > - **Precondition:** —
  > - **Reads:** —
  > - **Produces:** db → Task, Epic, TaskDependency (DAG), StateTransition and Defect entities in SQLite
  > - **Enables:** `D-INTL-06` → context hydration · `US-28`
  > - **Done when:** 🟡 SF-01 schema and migration shipped; the repository half — OCC, state machine, circuit breakers, zombie recovery, DAG propagation — is not marked complete
  > - **Note:** absorbs the former `C-EXEC-05` and `B-INTL-10`

* **`B-INTL-10` 🔮: Declarative Prompt Optimization**
  > - **Purpose:** 🟡 Tune prompt structure automatically from telemetry, DSPy-style, rather than by hand
  > - **Trigger:** 🟡 When the runner selects a prompt profile
  > - **Precondition:** `C-FLOW-01` → telemetry · `E-FLOW-01` → profile storage
  > - **Reads:** 🟡 telemetry, routing and active models
  > - **Produces:** 🟡 compiled prompt profiles
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Limits:** may be superseded — premised on owning slot-prompt assembly — the layer `C-INTL-06` and `C-FLOW-11` shrink. At design time, re-scope onto rubric content or retire

## DAL-A: Mission-Critical

* **`A-INTL-01` 🔜: Adversarial Spec Review** (Legacy: 3.50)
  > - **Purpose:** Attack a spec for contradictions and edge cases **before** generation, so failures are found in text rather than in code
  > - **Trigger:** During `sw draft`, before generation
  > - **Precondition:** `E-INTL-01` → the model · 🟡 the arbiter agent
  > - **Reads:** the spec
  > - **Produces:** 🟡 adversarial findings against the spec
  > - **Enables:** fewer downstream rollout failures
  > - **Done when:** 🔴

* **`A-INTL-02` 🔜: LLM Symbolic Execution** (Legacy: 4.14)
  > - **Purpose:** 🟡 Find memory-safety defects by guiding a symbolic compiler with heuristics that prune its execution tree
  > - **Trigger:** 🔴
  > - **Precondition:** `D-INTL-08` → the polyglot implement loop · a real C/C++ or Rust target
  > - **Reads:** native code
  > - **Produces:** 🟡 memory-safety defect reports, via KLEE
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Limits:** KLEE targets native code, and the trading system as planned is not such a target

* **`A-INTL-03` 🔜: Socratic Drafting** (Legacy: 5.6)
  > - **Purpose:** 🟡 Ask drafting questions shaped by the project's own topology, rather than a generic list
  > - **Trigger:** During `sw draft`
  > - **Precondition:** `D-SENS-01` → the topology graph
  > - **Reads:** 🟡 the topology graph and the draft in progress
  > - **Produces:** 🟡 topology-aware questions
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`A-INTL-04` 🔜: Memory Consolidation** (Legacy: 5.7)
  > - **Purpose:** Stop stored knowledge growing forever by deciding, when new overlaps old, whether to keep, update, delete or add
  > - **Trigger:** When new knowledge overlaps existing knowledge
  > - **Precondition:** `B-INTL-09` → the memory bank · `E-INTL-01` → the model that decides
  > - **Reads:** existing and incoming knowledge
  > - **Produces:** 🟡 a consolidated store
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`A-INTL-05` 🔜: Multi-Repo Refactoring Orchestration**
  > - **Purpose:** 🟡 Make one interface change across many repositories at once, and track it to completion
  > - **Trigger:** 🔴
  > - **Precondition:** 🟡 `A-SENS-04` → the federated system graph
  > - **Reads:** 🟡 20+ isolated repositories
  > - **Produces:** 🟡 synchronized, tracked interface changes
  > - **Enables:** 🔴
  > - **Done when:** 🔴
