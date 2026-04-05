# Developer Guide: Special Patterns & Adaptations

SpecWeaver is designed to orchestrate zero-trust, autonomous AI agents at scale. Because traditional software architecture patterns often fail to contain LLM hallucinations or drift, we have introduced several proprietary adaptations and unique patterns into the codebase. 

This guide outlines our "special inventions" so you aren't surprised when you stumble across them.

---

## 1. `context.yaml` Architectural Boundaries

In languages like Java or C#, you can enforce module visibility (e.g., `package-private` or `internal`). Python lacks this native visibility enforcement, meaning any file can technically import any other file anywhere in the repository.

To prevent an LLM (or a junior developer) from accidentally wiring a core engine component directly into an external web router, we invented `context.yaml` boundary files.

### How it works:
You will see `context.yaml` files dropped directly into source directories (e.g., `src/specweaver/loom/tools/context.yaml`).

```yaml
module: "loom.tools"
description: "Agent-facing DMZ tool boundary"
forbids:
  - "loom.atoms.*"
  - "cli.*"
```

### Why we do it:
During our pre-commit pipeline, an internal architecture scanner crawls these YAML files and cross-references them against the Python AST imports. If a developer accidentally writes `from specweaver.loom.atoms import EngineAtom` from within a `tools/` file, the `context.yaml` configuration triggers an immediate linting failure halting the commit.

---

## 2. Decoupled Interface Definitions (`definitions.py`)

Most modern LLM application frameworks (like LangChain or LlamaIndex) dynamically build the LLM's function-calling tool schema by scraping standard Python `"""docstrings"""` and function type-hints natively at runtime.

**SpecWeaver strictly forbids this.** 

We do not trust the physical implementation code to dynamically dictate what the LLM sees. Instead, we manually design the JSON schema payload within standalone `definitions.py` files.

### Why we do it:
1. **Security Hiding:** We can inject internal parameters (like `run_context` or `project_id`) into the actual Python function signature, but deliberately omit them from the `definitions.py` schema. The LLM won't even know the parameters exist.
2. **Prompt Optimization:** We can hyper-optimize the descriptions specifically for LLM tokenizer comprehension, rather than trying to make a Python docstring readable for humans *and* AIs simultaneously.

---

## 3. Friction-Gated Execution Pipelines (The HITL Gate)

In standard software CI/CD pipelines, a flow either passes completely or fails entirely in a black box. 

Because we are dealing with non-deterministic LLMs, an agent might accurately generate code, but fundamentally misunderstand the original business goal, leading to "architectural drift."

To combat this, the Flow Engine utilizes **Friction-Gated Pipelines**.
Inside our `pipelines/*.yaml` configurations, you will see gates marked as `type: hitl` (Human-In-The-Loop).

```yaml
gate:
  type: hitl
  on_fail: loop_back
  loop_target: rewrite_spec
```

### Why we do it:
Instead of crashing or deploying blind, the engine natively pauses its thread, serializes its exact OS state, and pings the user. If the user rejects the work, the `loop_target` seamlessly rewinds the state back to a previous workflow phase and tells the agent to try again with the user's specific feedback.

---

## 4. The 10-Test Battery (Multi-Modal Validation)

A normal Python project might rely solely on Pytest. SpecWeaver runs an orchestrated **10-Test Battery** that mixes standard runtime tests with heuristic hallucination bounds.

We physically separate "Code Rules" from "Spec Rules." While standard tools test whether code *compiles*, our bespoke Static Validation Engine uses AST tree-sitter logic and structural checks to verify that the generated code exactly matches the constraints of the Markdown Design Document before tests are even allowed to run.

---

## 5. Domain-Driven Boundary Relaxations (Tach Integration)

SpecWeaver relies on `tach` to strictly enforce domain boundaries between L1, L2, L3, and L4 layers. However, there are explicit cases where we gracefully relax these boundaries for architectural efficiency.

### Example: The Validation Layer (L2) and QARunner (L4)
The Validation Engine (`src/specweaver/validation/`) is designed as internal "pure logic", separated entirely from the raw file-system Executor limits within `Loom Commons` (`src/specweaver/loom/commons/`). However, the legacy AST module inside `c05_import_direction.py` has been explicitly replaced by a subprocess invocation utilizing `PythonQARunner.run_architecture_check()`.

### Why we do it:
To prevent writing custom AST parsers across Go, Python, and TS, the Validation layer is permitted explicit boundary relaxation (`forbids: "!loom.commons.qa_runner"`) to natively reuse the same dynamic polyglot architecture parser the CLI tool consumes. This prevents massive code duplication despite technically bridging pure logic and executor boundaries.

---

## 6. Deep-Merged Polyglot Configurations (DAL Matrices)

SpecWeaver uses a strict risk-based matrix (DO-178C style "DAL") to bypass or tighten rules based on mixed-criticality execution environments. We explicitly decouple `pydantic-settings` from environment variable mapping when parsing structural rule matrices.

### How it works:
Instead of internal Pydantic hacks, we rely on a pure-Python, mathematically deterministic recursive dictionary walker (`deep_merge_dict`) combined with direct YAML (`ruamel.yaml`) hydration to layer `.specweaver/dal_definitions.yaml` over base presets, before funneling the explicitly merged dictionary structurally into `DALImpactMatrix(**merged)`.

### Why we do it:
Configuration overriding frameworks notoriously clobber massive hierarchies if user configurations omit single child branches. `deep_merge_dict` guarantees safety matrices explicitly retain all default safety toggles unconditionally, while merging exclusively targeted overrides for domain-specific risk levels (DAL).

---

## 7. Generative HARA Governance (Enum-Driven Prompts)

When AI Agents generate structured JSON proposals for complex engineering operations (like Hazard Analysis and Risk Assessment - HARA), we completely ban standard string bindings for critical data classifications.

### How it works:
Inside our decomposition workflows (`ComponentChange`), the target DO-178C data tier (`proposed_dal`) is typed structurally as `DALLevel(str, Enum)` rather than `str`.

### Why we do it:
Even with aggressive system prompts detailing "DAL_A through DAL_E", Agents hallucinate or append invalid remarks like "DAL_Z" or "Critical". By explicitly binding the parsing layer to a Pydantic Enum, we offload architectural safety to the underlying Rust JSON schema parser. If the LLM hallucinates, Pydantic throws a `ValidationError`, instantly triggering our `loop_back` native HITL engine to auto-retry the LLM without crashing SpecWeaver's internal state.

---

By understanding these core adaptations, you will be able to navigate SpecWeaver's unique safety systems and extend the architecture without accidentally violating our zero-trust boundaries!
