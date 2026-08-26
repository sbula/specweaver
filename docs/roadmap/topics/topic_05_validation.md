# Topic 05: Validation Engine (Reflexes)

Capabilities for static analysis, linting, rulesets, and automated verification.

Seven keyed fields per entry, plus optional `Limits:` and `Note:` — no prose (`R-ENTRY`). Values are written plainly.
**🟡 marks a guess** · **🔴 marks nothing found**. Markers are the exception.

## DAL-E: Prototyping

* **`E-VAL-01` ✅: Core Validation Engine** (Legacy: Step 2)
  > - **Purpose:** Judge a spec against rules and report what is wrong — the core promise, proven without spending anything on a model
  > - **Trigger:** When a user runs `sw check`
  > - **Precondition:** —
  > - **Reads:** the spec file and the active rule set
  > - **Produces:** console → rule results
  > - **Enables:** every validation capability built since
  > - **Done when:** `sw check path/to/spec.md` runs the rules and reports results

* **`E-VAL-02` ✅: Auto-Discover Standards** (Legacy: 3.5)
  > - **Purpose:** Learn a project's own conventions from its code, so generated code matches the house style instead of a generic one
  > - **Trigger:** When a user runs `sw scan --standards`
  > - **Precondition:** `D-SENS-02` → parsed source
  > - **Reads:** Python and JS/TS source — naming, error handling, type hints, docstrings, test and import patterns
  > - **Produces:** db → a `project_standards` table · a bootstrapped `CONSTITUTION.md`
  > - **Enables:** `PromptBuilder.add_standards()` → every generation call
  > - **Done when:** a scan yields standards that reach the prompt without hand configuration

* **`E-VAL-03` ⚰️ RETIRED:** *(AST Prompt Injection Sanitization — retired 2026-08-21 by the user,
  ruled nonsense under the [benefit review](../../analysis/benefit_chain_analysis_2026-08-20.md) §8:
  it filtered attacks the sandbox already survives and missed semantic poisoning; being best-effort,
  nothing could rely on it. Detector deleted; `escaping.py` stays under `E-INTL-01`; the
  structure-into-prompts successor is `B-SENS-09`.
  Record: [design](../features/topic_05_validation/E-VAL-03/E-VAL-03_design.md). ID is dead — do NOT reuse.)*

* **`E-VAL-04` 🔜: Multi-Stage Reviews**
  > - **Purpose:** Let a review run as several configured stages rather than one pass, so different questions can be asked separately
  > - **Trigger:** When a review pipeline runs
  > - **Precondition:** `C-VAL-05` → **approved**, as the rubric substrate · `E-VAL-02` · `B-VAL-02`
  > - **Reads:** rubric files, one per stage
  > - **Produces:** 🟡 a staged review verdict
  > - **Enables:** `US-1`'s configurable multi-stage reviews
  > - **Done when:** 🟡 adding a stage is a rubric file plus a `load_rubric` call, not a rule class

* **`E-VAL-05` 🔜: Suppression Ratchet (Gate-Bypass Census)**
  > - **Purpose:** Count every switched-off rule, because for an agent under a gate **adding the suppression is the cheapest correct answer** to the constraint as stated
  > - **Trigger:** At every gate, at every DAL
  > - **Precondition:** the rule battery
  > - **Reads:** source files, for suppression markers
  > - **Produces:** 🟡 a frozen ratchet count · an outright ban on blanket suppressions carrying no rule code
  > - **Enables:** every other gate — this is what guards them
  > - **Done when:** 🔴
  > - **Note:** a product capability, not repo hygiene. Runs at every DAL for that reason

## DAL-D: Internal Tooling

* **`D-VAL-01` ✅: QA Runner Tool** (Legacy: Step 12)
  > - **Purpose:** Run the project's own tests and linters, and feed the failures back for another attempt
  > - **Trigger:** After code is generated
  > - **Precondition:** —
  > - **Reads:** the generated code and the project's test tooling
  > - **Produces:** test and lint results, fed into a fix loop
  > - **Enables:** `D-INTL-01` → the implement loop
  > - **Done when:** a lint failure loops back and is fixed rather than reported

* **`D-VAL-02` ✅: Custom Rule Paths** (Legacy: 3.4)
  > - **Purpose:** Let a project define which rules run and in what order, and inherit from a base rather than restating it
  > - **Trigger:** When a validation pipeline is resolved
  > - **Precondition:** `E-VAL-01` → the engine
  > - **Reads:** YAML pipelines — with extends / override / remove / add — and project-local overrides
  > - **Produces:** memory → a resolved validation pipeline
  > - **Enables:** `sw list-rules` · `--pipeline` override · custom D-prefix rules
  > - **Done when:** a project changes its rule set without changing code, and a circular `extends` is refused

* **`D-VAL-03` ✅: Polyglot QARunner** (Legacy: 3.19)
  > - **Purpose:** Run any language's own toolchain — `cargo`, `gradlew`, `pytest` — through one interface, judging by exit code rather than by parsing Python-shaped output
  > - **Trigger:** When tests or linters run for a target project
  > - **Precondition:** —
  > - **Reads:** the target project's toolchain
  > - **Produces:** memory → normalized results from exit codes and stderr
  > - **Enables:** `D-INTL-08` → the polyglot implement loop that cannot yet reach these runners
  > - **Done when:** five language runners execute as a black box, with no Python AST assumptions

* **`D-VAL-04` ✅: Adaptive Assurance Standards** (Legacy: 3.32a)
  > - **Purpose:** On an empty repository there is no house style to copy, so inject idiomatic targets instead of mining nothing
  > - **Trigger:** When standards are resolved for a project
  > - **Precondition:** `E-VAL-02` → the analyzer it toggles
  > - **Reads:** `specweaver.toml` → mimicry or best-practice mode
  > - **Produces:** memory → the standards injected into prompts
  > - **Enables:** greenfield builds without a context vacuum
  > - **Done when:** an empty repo yields idiomatic standards rather than none

* **`D-VAL-05` ✅: Code Validation Rules (C01–C08)** (Legacy: Step 5)
  > - **Purpose:** Check generated code mechanically — syntax, type hints, coverage — before anything semantic is asked of a model
  > - **Trigger:** When `sw check code` runs
  > - **Precondition:** `E-VAL-01` → the engine
  > - **Reads:** generated code
  > - **Produces:** rule findings, C01 through C08
  > - **Enables:** the implement loop's validation step
  > - **Done when:** the code rule set runs and reports

## DAL-C: Enterprise Standard

* **`C-VAL-01` ✅: Constitution Artifact** (Legacy: 3.2)
  > - **Purpose:** State a project's governing rules once, in one document, and put them in front of the model on every call
  > - **Trigger:** When any prompt is built
  > - **Precondition:** —
  > - **Reads:** `CONSTITUTION.md`, resolved by walking up from the target
  > - **Produces:** prompt → the constitution, within a configurable size limit
  > - **Enables:** every LLM call · `sw constitution show/check/init`
  > - **Done when:** a project's rules reach every call without being restated per prompt

* **`C-VAL-02` ✅: Domain Profiles** (Legacy: 3.3)
  > - **Purpose:** Configure a project by naming what kind of thing it is, rather than setting each option by hand
  > - **Trigger:** When a project's profile is set
  > - **Precondition:** `E-FLOW-01` → the config DB
  > - **Reads:** the chosen profile — web-app, data-pipeline, library, microservice, ml-model
  > - **Produces:** db → bulk-written config overrides
  > - **Enables:** five preset bundles · five CLI commands
  > - **Done when:** choosing a profile sets the whole bundle in one act

* **`C-VAL-03` ✅: Dynamic Risk Rulesets** (Legacy: 3.20b)
  > - **Purpose:** Judge risky code harder than cheap code, without maintaining two rule sets
  > - **Trigger:** When the battery runs against a module
  > - **Precondition:** `D-VAL-02` → pipeline inheritance · the module's DAL
  > - **Reads:** the module's domain risk level
  > - **Produces:** strict or relaxed constraints over the fixed battery
  > - **Enables:** FFI boundary checks outsourced to native tools — Tach, ArchUnit, ESLint
  > - **Done when:** one battery behaves differently by DAL, resolved fractally

* **`C-VAL-04` ✅: Traceability Matrix Check** (Legacy: 3.21)
  > - **Purpose:** Catch a requirement with **no test at all** — an omission detector, and only that
  > - **Trigger:** When generated tests are validated
  > - **Precondition:** `D-SENS-02` → the test file AST
  > - **Reads:** the spec's FRs and NFRs · `@traces(req_id)` tags in generated tests
  > - **Produces:** a hard pipeline failure when a requirement has zero tests
  > - **Enables:** `C-UI-02` → the traceability matrix view
  > - **Done when:** a requirement with no test fails the pipeline
  > - **Limits:** does not vouch for test *quality*. The tag is written by the same model as the test, so a hallucinated test carries a well-formed tag. Quality is `A-VAL-03`'s job

* **`C-VAL-05` 🔧: Rubrics-as-Content Validation**
  > - **Purpose:** Change what a review asks for by editing a file, not by changing code and releasing
  > - **Trigger:** When a review step loads its criteria
  > - **Precondition:** `E-INTL-03` → the review engine · the run's DAL
  > - **Reads:** markdown rubrics — shipped defaults, then `.specweaver/rubrics/` overrides, then a `<id>.<DAL>.md` variant
  > - **Produces:** prompt → review criteria · verdict record → rubric id, version, sha256 and source path
  > - **Enables:** `E-VAL-04` · `B-VAL-03` · `B-INTL-08` · `D-INTL-04` · `D-INTL-07`
  > - **Done when:** editing a rubric changes the next review's verdict, with no code change
  > - **Limits:** thin content — three rubric files ship, no project override exists. `FR-2`–`FR-4` serve a user who does not exist yet

* **`C-VAL-06` 🔜: Structural Code-Health Rules**
  > - **Purpose:** Detect the structural failures that actually hurt — **a god object scores 1 on cyclomatic complexity**, which is what the battery measures today
  > - **Trigger:** When the code battery runs
  > - **Precondition:** `D-SENS-02` → parsed structure
  > - **Reads:** source files
  > - **Produces:** three rules → cognitive complexity · instance-attribute count · signature shape
  > - **Enables:** `B-VAL-06` → LCOM4, which says where to cut what this detects
  > - **Done when:** 🔴
  > - **Limits:** out of scope — LCOM4 and coupling (`B-VAL-06`) · mutation (`A-VAL-03`) · the DAL policy layer (`C-VAL-03`)

## DAL-B: High-Assurance

* **`B-VAL-01` ✅: AST Drift Detection** (Legacy: 3.18)
  > - **Purpose:** Notice when code has moved away from what was agreed, using the parse tree rather than text comparison
  > - **Trigger:** When drift is checked
  > - **Precondition:** `D-SENS-02` → the AST
  > - **Reads:** implementation source and its recorded shape
  > - **Produces:** drift findings
  > - **Enables:** `B-VAL-02` → the interceptor that blocks on them
  > - **Done when:** a parser-backed drift is detected where a text diff would miss it

* **`B-VAL-02` ✅: Spec Rot Interceptor** (Legacy: 3.23)
  > - **Purpose:** Stop the spec and the code drifting apart — the second-day problem, where a hotfix lands and the document quietly stops being true
  > - **Trigger:** On build or commit
  > - **Precondition:** `B-VAL-01` → drift detection
  > - **Reads:** the implementation AST and the spec markdown
  > - **Produces:** a blocked build until the two are reconciled
  > - **Enables:** documentation that stays true after the first hotfix
  > - **Done when:** a divergence between code and spec blocks the commit

* **`B-VAL-03` 🔜: Semantic Completeness Review** (Legacy: 3.42)
  > - **Purpose:** Ask whether the tests cover what the spec actually promised — unhappy paths, error bounds, expected outcomes — not just whether tests exist
  > - **Trigger:** When generated tests are reviewed
  > - **Precondition:** `C-VAL-05` → the rubric substrate · `E-INTL-01` → the model
  > - **Reads:** the generated test suite and the spec
  > - **Produces:** 🟡 ERRORs for missing branch coverage, as rule `C10`
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Note:** rubric-first. The `C10` rule class is a thin engine shim; the completeness criteria live in a versioned, DAL-gated rubric file, not in Python

* **`B-VAL-04` 🔜: SWE-Bench QA Gates** (Legacy: 3.47)
  > - **Purpose:** Prove a SpecWeaver change has not made the platform worse, before trusting it with real work
  > - **Trigger:** Before a release
  > - **Precondition:** `D-FLOW-01` → the pipelines under test · a pinned model, multi-run, with known variance. **Unpinned, the score measures the plugged-in model rather than the platform**
  > - **Reads:** a deterministic suite of synthetic SWE-bench bugs
  > - **Produces:** 🟡 a token-cost and success-rate score
  > - **Enables:** the release gate for real-money projects
  > - **Done when:** 🔴

* **`B-VAL-05` 🔜: DAL Architecture Gate**
  > - **Purpose:** Refuse a dependency that crosses an assurance boundary the wrong way — a critical component reaching into a prototype one
  > - **Trigger:** When `sw check` runs
  > - **Precondition:** `B-SENS-02` → the persistent knowledge graph · DAL assignments
  > - **Reads:** a package's dependencies
  > - **Produces:** 🟡 a rule finding on a boundary violation
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Limits:** per-level behaviour is not designed yet. Every live DAL consumer decides strict-or-relaxed only; the tier count is an empirical question the trading system answers

* **`B-VAL-06` 🔜: Cohesion & Coupling Metrics (LCOM4, CBO, Instability)**
  > - **Purpose:** Say **where to cut** a class, not merely that it is too big — LCOM4's connected components *are* the split, which is an instruction rather than a score
  > - **Trigger:** When structural health is measured
  > - **Precondition:** `C-VAL-06` → the cheap rules it must not gate · 🟡 tooling that does not exist for Python
  > - **Reads:** source structure
  > - **Produces:** 🟡 LCOM4 components · CBO · instability
  > - **Enables:** refactoring guidance rather than a warning
  > - **Done when:** 🔴
  > - **Limits:** whether it gates or only advises is undecided

* **`B-VAL-07` 🔜: Graph-Invariant Verification**
  > - **Purpose:** Catch a dependent the generation broke and never touched — today nothing checks unchanged dependents at all
  > - **Trigger:** After a generated change, before merge
  > - **Precondition:** `B-SENS-02` → the graph · `TECH-068` → real edges
  > - **Reads:** the graph before and after the change
  > - **Produces:** 🟡 a finding for each dangling `CALLS` / `IMPLEMENTS` / `EXTENDS` edge
  > - **Enables:** `B-INTL-08` → the review narrative built on this
  > - **Done when:** 🔴
  > - **Limits:** graph-**checked**, not guaranteed, on dynamic languages. Reads traversal only, never vector output

## DAL-A: Mission-Critical

* **`A-VAL-01` ✅: Protocol/Schema Analyzers** (Legacy: 3.31)
  > - **Purpose:** Catch a contract change in one service before it breaks another, by parsing the contract files themselves
  > - **Trigger:** When a contract file is validated
  > - **Precondition:** `D-SENS-02` → the parser layer
  > - **Reads:** `.proto` (gRPC) · `openapi.yaml` · AsyncAPI
  > - **Produces:** contract-drift findings, as rule `C13`
  > - **Enables:** polyglot microservice contract checking
  > - **Done when:** a drifted contract is caught against the AST

* **`A-VAL-02` 🔜: Symbolic Math Validation** (Legacy: 3.39)
  > - **Purpose:** Check that a formula in the code is the formula in the spec — **a transposed sign in a pricing formula costs real money**
  > - **Trigger:** 🟡 When generated code contains a formula the spec states
  > - **Precondition:** 🟡 the spec's stated formulas
  > - **Reads:** generated code and spec formulas
  > - **Produces:** 🟡 transcription findings
  > - **Enables:** the trading system journeys (`US-13`, `US-18`)
  > - **Done when:** 🔴
  > - **Limits:** re-scoped — the ML half — "verify FinBERT calculations" — was removed. A neural net's outputs cannot be formally verified, and "proves secure / discovers 0-days" promised
  >   a different universe than the mechanism delivers

* **`A-VAL-03` 🔜: Mutation Testing Gates** (Legacy: 4.7)
  > - **Purpose:** Prove a test would notice the behaviour going away, rather than that it passes
  > - **Trigger:** 🟡 At a verification gate
  > - **Precondition:** `D-VAL-01` → the test runner
  > - **Reads:** source and its tests
  > - **Produces:** 🟡 mutation and assertion-density verdicts
  > - **Enables:** the test-quality half `C-VAL-04` explicitly cannot cover
  > - **Done when:** 🔴
  > - **Note:** `TECH-049` is the dev-tooling equivalent for this repo. They are separate tracks

* **`A-VAL-04` ⚰️ RETIRED:** *(Rust PyO3 Validations — retired 2026-08-20 by the
  [benefit review](../../analysis/benefit_chain_analysis_2026-08-20.md): validation is milliseconds
  beside the LLM calls that dominate every pipeline, and rewriting rules in Rust does nothing for
  the sandbox — the sandbox's threat is what generated code does, not how the validator allocates
  memory. ID is dead — do NOT reuse.)*

* **`A-VAL-05` 🔜: Multi-Modal Visual Quality Gates (V-Series)** (Legacy: 4.11)
  > - **Purpose:** 🟡 Check that a rendered UI matches its specification, which no text rule can do
  > - **Trigger:** 🟡 When a UI component is validated
  > - **Precondition:** 🟡 a vision model · headless browser rendering
  > - **Reads:** rendered UI, via Playwright in Docker
  > - **Produces:** 🟡 visual drift findings, as `V-Series` rules
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`A-VAL-06` 🔜: Industry Standard Bridges** (Legacy: 3.41)
  > - **Purpose:** Interoperate with the contract and fact tooling teams already run, rather than replacing it
  > - **Trigger:** 🟡 When cross-service contracts are checked
  > - **Precondition:** 🟡 `A-VAL-01` → the contract parsers
  > - **Reads:** Pact.io contracts · Glean fact graphs · ArchCodex
  > - **Produces:** 🟡 cross-service contract findings
  > - **Enables:** `US-22` P-3 and P-4 — **owned by this capability**, assigned by the user 2026-08-20
  > - **Done when:** 🟡 a schema change in one service surfaces as an untraced requirement in another
  > - **Note:** its design declares both journeys as seam FRs, tests written red first
