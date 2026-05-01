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
During our pre-commit pipeline, an internal architecture scanner crawls these YAML files and cross-references them against the Python AST imports. If a developer accidentally writes `from specweaver.core.loom.atoms import EngineAtom` from within a `tools/` file, the `context.yaml` configuration triggers an immediate linting failure halting the commit.

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

---

## 8. Mathematical Schema Overlays (Plugin Composition)

SpecWeaver leverages "plugins" defined in `context.yaml` inside of boundary resolutions to combine multiple isolated framework paradigms concurrently (e.g. `spring-boot` serving as the base archetype, overlaid with `spring-security`).

### How it works:
Instead of treating plugins as monolithic executables, SpecWeaver merges flat YAML definitions mathematically within `CodeStructureAtom._aggregate_merge`. Deep dictionaries merge safely, and crucially, lists (like `["read_unrolled_symbol"]`) mathematically perform Set Union aggregation.

### Why we do it:
To prevent agent hallucinations natively without forcing C-bindings. If the Security plugin dictates `intents: hide: ["list_symbols"]`, the dynamic merge strictly enforces those safety boundaries globally in the `dispatcher.available_tools()` layer without writing a single line of explicit Python interception logic. It forces cross-concern security into pure mathematics.

### How it works:
Inside our decomposition workflows (`ComponentChange`), the target DO-178C data tier (`proposed_dal`) is typed structurally as `DALLevel(str, Enum)` rather than `str`.

### Why we do it:
Even with aggressive system prompts detailing "DAL_A through DAL_E", Agents hallucinate or append invalid remarks like "DAL_Z" or "Critical". By explicitly binding the parsing layer to a Pydantic Enum, we offload architectural safety to the underlying Rust JSON schema parser. If the LLM hallucinates, Pydantic throws a `ValidationError`, instantly triggering our `loop_back` native HITL engine to auto-retry the LLM without crashing SpecWeaver's internal state.

---

## 8. Polyglot Abstract Syntax Tree (AST) Traceability (C09 Engine)

When SpecWeaver enforces that every feature spec is rigorously bound to an automated test (Feature 3.21 - Automated Traceability Matrix), we explicitly bypass standard coverage tools or complex code instrumentation in favor of Polyglot AST tokenization via `tree-sitter`.

### How it works:
Instead of requiring Python developers to use `@pytest.mark.trace("FR-1")`, they simply utilize identical syntactical layout regardless of the language: `# @trace(FR-1)` in Python, or `// @trace(FR-1)` in Java. SpecWeaver fires up an internal AST decoder, dynamically shifts structural parsers based on the file extension, traverses exclusively into `comment` root node types, and maps the matrix entirely in memory.

### Why we do it:
1. **No Application Dependencies**: The engine operates purely statistically and leaves zero import overhead in the user application.
2. **Infinite Language Support**: Since `tree-sitter` bindings natively abstract comment scraping, our single codebase natively provides requirement traceability into Python, Rust, Go, JavaScript, TypeScript, C++, and SQL indiscriminately, completely insulating SpecWeaver rules from framework-specific lock-in.

---

By understanding these core adaptations, you will be able to navigate SpecWeaver's unique safety systems and extend the architecture without accidentally violating our zero-trust boundaries!

---

## 9. Structural Reverse Graph-Climbing (AST Skeleton Extraction)

When building our polyglot CodeStructure AST extraction layer (Feature 3.22), we found that standard `.scm` `function_definition` queries natively orphaned critical code-block prefixes (like Python annotations `@classmethod` or TypeScript wrappers `export default class`), causing silent data corruption during agent rewrites.

### How it works:
Instead of trying to architect convoluted SCM query strings to capture every possible decorator, we inverted the parsing model. We perform a precise "inner target" SCM query to find the raw symbol name (`node_name`), and then execute a mathematical parent-walking algorithm (e.g., checking if `name_node.parent.parent.type == 'decorated_definition'`) to organically swallow all external prefixes surrounding the target.

### Why we do it:
This abstraction anomaly completely removes the need for infinite grammar mappings. Since the parent-tree strictly cascades mathematically in all 9 supported languages (C/C++, Rust, Python, Java, Kotlin, TS, SQL, Markdown), a single logical upward-walker uniformly preserves `@app.route` or `export async` wrappers indiscriminately.

---

## 10. The Dual-Consumer Atom Bypass & AST Auto-Indentation

When implementing the **Polyglot AST Symbol Writer (Feature 3.22, SF-2)** to allow agents to seamlessly edit deeply nested code structures, we explicitly authorized a massive architectural exception known as the Dual-Consumer Atom Bypass, paired with an AST auto-indenter proxy.

### How it works:
Standard design dictates atoms only return localized data formats (e.g. `AtomResult`) and rely entirely on `impl` tool mapping facades to execute actual side effects (like writing strings safely to disk). `CodeStructureAtom` violates this rule explicitly. It intercepts the mutated byte-strings calculated by internal tree-sitter parsers and executes a direct `self._executor.write(path, mutated_code)` side effect completely hidden from the encompassing tool router.
Furthermore, any multi-line string injected into this write is pre-processed by an `_auto_indent` proxy that intercepts the AST's exact integer-based integer margin layout and flawlessly prepends recursively calculated padding.

### Why we do it:
1. **Double Handling Loop Hallucination:** If the Atom simply surfaced the newly mutated 2,000-line Python struct payload back to the Agent facade, the AI context window would instantly blow out trying to pipe that return sequence sequentially into an independent `FileWriter` tool call. Atomic persistence within the CodeStructureAtom eliminates context-bloat definitively.
2. **Strict Indentation Immunity:** By forcing the engine to intercept LLM-generated string blocks and perform padding against Tree-Sitter boundaries natively rather than within regex bounds, we effectively inoculate SpecWeaver against LLM `IndentationErrors` and trailing brace failures across languages.

---

## 11. Git Worktree Sandboxing (Mathematical Diff Striping & OS Lock Resilience)

When allowing LLM agents inside a Pipeline Orchestrator (Feature 3.26) to generate multi-file refactoring steps, we face catastrophic risk if an AI hallucinates massive deletions across a dirty host `src/` directory. 

### How it works:
Instead of restricting agents purely via prompt rules or abstract AST overlays, the execution engine dynamically builds an isolated `.worktrees/` directory directly linked to the current Git repository using `git worktree add`. The agent writes code here. At completion, `_intent_strip_merge` parses the generated `.diff` hunk by hunk. Any path that isn't explicitly green-lit by the module's `context.yaml` boundaries is **mathematically erased from the patch** before executing a `git apply --strategy-option=ours`. 

Simultaneously, `_intent_worktree_teardown` utilizes a progressive 5-iteration timing backoff loop (`0.05, 0.1, 0.2, ...`) directly wrapping physical `shutil.rmtree` combined with `git worktree prune`.

### Why we do it:
1. **The mathematical stripe:** Completely and definitively blocks Agents from bypassing API limits to rewrite central configurations (`Pipfile`, `pom.xml`, `README.md`). We physically drop those hunks rather than failing the run, letting the valid logic merge cleanly. Documentation claims (`doc_updates.md`) are explicitly whitelisted as isolated channels.
2. **The OS locking backoff:** Windows systems aggressively index and run Anti-Virus locks on freshly modified physical directories (`.worktrees/`). Attempting a standard 0ms deletion results in fatal access crashes, halting the entire pipeline. The progressive micro-backoff elegantly yields exactly long enough for OS locks to release, tearing down the sandbox securely under 2 seconds.

---

## 12. Rule Context Hydration (The **kwargs Bypass)

When injecting polyglot AST models generated by `CodeStructureAtom` directly into Python validation rules, we bypass standard explicit constructor typing via the runtime `Rule.context` property mechanism.

### How it works:
Instead of requiring `def __init__(self, required_markers: list = None, ast_payload: dict = None):`, the `PipelineRunner` traps system-injected structs (`step.params.pop("ast_payload")`) precisely during rule initialization, shifting them strictly into a dynamic `rule.context = payload` property post-instantiation, natively freeing `**kwargs` bindings exclusively for YAML param mapping.

### Why we do it:
If system parameters collided dynamically against pure logic rules during strictly typed `**kwargs` unwrapping via `**step.params`, new rules would permanently crash against `TypeError: unexpected keyword argument` the second the Engine scaled up its contextual system variables. By forcefully splitting payload injection into a post-init hydration wrapper, Validation Rules are mathematically unbound from Executor constraints, allowing `C12ArchetypeCodeBoundsRule` to read directly from `.context` while maintaining `PARAM_MAP` integrity.

---

## 13. Flat Archetype Evaluators (The LSP Bypass)

When configuring the Core Validation Engine to parse structural AST constraints natively against framework-specific annotations (e.g. Kotlin's `@RestController` or Rust's `#[derive(Clone)]`), we deliberately bypassed the standard industry approach of booting up heavy runtime Language Servers (LSPs) or compiler plugins.

### How it works:
Instead of trying to parse raw source code through heavy background processes, `SchemaEvaluator` parses flat YAML declarative files (e.g., `fastapi.yaml`, `actix-web.yaml`) stored directly in `workflows/evaluators/frameworks/`. These YAML files define strict mathematical unrollings mapping raw decorators/macros directly to their underlying abstract logic. 
Furthermore, the mappings are isolated by **Archetype** rather than **Language**. There is no `java.yaml` containing Spring Boot and Quarkus. Instead, there is a distinct `spring-boot.yaml` securely guarded by `metadata.supported_languages: ["java", "kotlin"]`.

### Why we do it:
1. **Speed & Stability**: Firing up a background LSP or rust-analyzer instance during critical AI Generation loops adds a devastating 5–10 second latency tax per check, crippling iterative loop speeds. Unrolling YAML abstractions in-memory dynamically reduces structural mapping times to `0.01` seconds.
2. **Preventing Cross-Framework Hallucinations**: By enforcing flat archetype models bound natively by `supported_languages`, if an LLM hallucinates a `FastAPI` construct into a `Node.js` Typescript worker, the validation explicitly drops the archetype matching organically rather than tearing down the parser natively.
3. **Targeted AST Filtering (`decorator_filter`)**: Because we extract these framework markers explicitly through internal polyglot tree-sitter mappings (e.g., `extract_framework_markers`), we natively power the Agent's `list_symbols(decorator_filter="PreAuthorize")` tool. This bypasses the need for the LLM to read massive source files line-by-line; instead, the physical AST extractor actively filters and drops any symbol that lacks the declared framework annotation text, guaranteeing pristine targeted visibility.

---

## 14. Deep Serialization Facade (The Orjson Override)

When scaling SpecWeaver's internal logging, payload serialization, and topology caching to meet extreme `< 50ms` NFR targets (Feature 3.32), we systematically replaced all native Python `import json` usage with the Rust-backed `orjson` library.

### How it works:
Instead of forcing developers to use `orjson.dumps().decode('utf-8')` perfectly every time across 29+ modules, we built a single unified facade module `specweaver.commons.json`. The entire codebase points to this one entrypoint (`from specweaver.commons import json`). 

### Why we do it:
1. **The Pydantic Poison Pill**: Standard `json.dumps()` returns standard `str` UTF-8 primitives. Fast `orjson.dumps()` natively returns raw `bytes`. Passing raw bytes into downstream Pydantic instantiators, logging frameworks layer formatters, or LLM System Prompts notoriously crashes them with `TypeError: input must be a string, not bytes`. The facade explicitly wraps `orjson` and intercepts the `.decode('utf-8')` transformation strictly to preserve zero-friction string parity across the engine.
2. **Deterministic Sort Consistency**: LLM caching thrives on exact token string-matching. The facade actively captures mapping flags (like `sort_keys=True`) and strictly routes them into `orjson.OPT_SORT_KEYS`, mathematically ensuring JSON structure guarantees natively at the lowest engine level.

---

## 15. Semantic State Caching (The Persistent `.specweaver` Cache)

When evaluating architecture boundaries and computing execution dependencies (Feature 3.32), SpecWeaver generates a global structural map known as the `TopologyGraph`. Building this graph relies on polyglot TreeSitter parsing for every `context.yaml` source boundary globally.

### How it works:
Instead of recursively parsing the AST mappings globally on every run, SpecWeaver leverages `DependencyHasher`. It dynamically digests the nested source files into Merkle Root signatures, mapping them deterministically to physical OS structures. It persists this signature matrix in `<project_root>/.specweaver/topology.cache.json`. Crucially, this caching block explicitly injects itself securely into the repo's root `.gitignore` to prevent source pollution.

### Why we do it:
1. **The `< 50ms` NFR Guarantee:** An engine scanning thousands of files per `Flow` command loop incurs agonizing I/O drag. By isolating recursive reads behind mathematical semantic fingerprints, SpecWeaver resolves subsequent global boundaries physically in milliseconds.
2. **The Symlink Sandbox Extension:** As part of the Worktree Bouncer context (Pattern 11), ensuring `.specweaver` is symlinked natively into temporary ephemeral sandboxes means the inner loop instantly tracks against the main trunk's caching speeds without having to manually reconstruct gigabytes of dependencies or AST tree paths.

> [!CAUTION]
> **The Cache-Flush Dilemma (Topological Stale Nodes)**
> Because `TopologyGraph` reads the `.specweaver` cache to compute a set of `graph.stale_nodes`, it has effectively morphed into a **temporal snapshot** representing the codebase's mathematical diff at exact instantiation.
> **DO NOT AUTO-FLUSH THE CACHE DURING GRAPH BOOTSTRAP!** 
> If `TopologyGraph.from_project()` evaluates the tree and immediately overwrites `topology.cache.json`, you explicitly destroy the baseline. The very next pipeline operation that boots the Graph will see zero changes and flag everything as clean, letting corrupted test suites bypass the Validation Engine. 
> The Semantic Cache must ONLY be explicitly saved (`DependencyHasher.save_cache()`) by the **CLI Orchestrator** (`pipelines.py`) strictly after the `PipelineRunner` yields a successful `RunStatus.COMPLETED` state. Coupling the flush inside the `flow` engine violates DMZ boundaries between `flow` and `graph`.

> [!CAUTION]
> **Tombstone Discovery (Ghost Dependencies)**
> When computing staleness (`_calculate_stale_seeds`), if a dependent module is completely deleted from the disk, it vanishes from the physical directory scan mapping. However, historical consumers of that module will still explicitly declare an overarching `consumes: [deleted_module]` relationship inside their `context.yaml`. 
> The crawler explicitly flags any consumer possessing a dangling dependency reference natively as a `stale_seed` to guarantee upstream consumers fail their test suites predictably.

---

## 16. The Vault Binding Shield (Option D)

When upgrading the core pipeline to support external credentials for Model Context Protocol (MCP) integrations (Feature 3.32c), we faced a severe credential leakage risk: how do we prevent users or LLMs from accidentally `git commit`ting `.specweaver/vault.env` to the remote repository?

### How it works:
Instead of trying to manipulate or parse `Pydantic` settings during YAML loading, we fundamentally bypass the configuration layer. `PipelineRunner.run()` and `PipelineRunner.resume()` autonomously invoke a pre-flight filesystem check early in the boot sequence. If `.specweaver/vault.env` exists, the `PipelineRunner` natively dispatches pure `GitAtom` intents (`_intent_is_tracked`) to check `git ls-files --error-unmatch .specweaver/vault.env`. 

### Why we do it:
1. **Architectural Pure-Logic Boundaries**: Configuration models (`context.yaml`) are located in L2 `config` and `assurance` layers. Running arbitrary `subprocess.run(["git", "ls-files"])` from inside configuration violates our Tach domain bounds cleanly, cross-contaminating physical executables into pure domain logic. By injecting the check exclusively into the orchestrator layer (L3 Flow), we natively utilize valid `Loom Atom` paths to execute Git binaries securely.
2. **Dictatorial Execution Integrity**: If `GitAtom` returns that the vault file is tracked, the Runner actively shuts down the interpreter via a violent `RuntimeError`. It assumes the repository is inherently compromised. There is no fallback, no auto-rollback, and noHITL mitigation—it kills the pipeline immediately to prevent pushing credentials upstream.

---

## 17. The Thread-Pumped JSON-RPC Executor (Loom Commons)

When integrating Model Context Protocol (MCP) servers locally via standard I/O (stdio) in feature 3.32c SF-2, we entirely rejected external integration SDKs (like `mcp` PyPI packages). Existing libraries force heavy asynchronous event loop requirements which explicitly violate the `async_ready: false` bounding configurations within our core execution layers (`commons`).

### How it works:
Instead of `asyncio.create_subprocess_exec`, the `MCPExecutor` boots standard `subprocess.Popen` pipelines attached to native `subprocess.PIPE` buffers. To perform timeout-aware stream isolation natively on Windows without `select` or `fcntl` crashes:
1. It sparks a daemon `threading.Thread` loop executing purely `iter(process.stdout.readline, "")`.
2. This loop pipes directly into an unbounded `queue.Queue`.
3. The foreground `call_rpc` process utilizes explicit sequence increment correlation (`self._request_id += 1`) and parses the queue stream blocks via `_queue.get(timeout=...)`.

### Why we do it:
This architectural separation isolates arbitrary Docker blockages cleanly. `call_rpc` successfully idles and traps delays, rejecting stale queue loops natively without cross-contaminating the main thread execution path. It completely negates the requirement for complex `AsyncIO` integration downline in the engine stack, ensuring validation layers remain functionally pure synchronous generators.


## Pre-Fetched Context Envelope (MCP Integration)

**Feature**: 3.32c (Pre-Fetch Assembler)

### The Problem
Injecting global tools into LLM pipelines for MCP integration causes severe System Prompt token saturation, and allows LLMs to rapidly exhaust tool invocation limits, leading to latency overheads.

### The Solution
The Flow Engine mathematically analyzes the `context.yaml` `consumes_resources` block to extract standard MCP URIs ahead of time. Before any LLM step is dispatched, the `MCPAtom` fetches remote resources sequentially over `stdio` and formats them into a serialized text block.
This physical payload is explicitly injected into the `<environment_context>` block of the agent prompt as a static snapshot.

### Architectural Mandates
1. **No LLM Tool Definitions:** No dynamic tool calling is allowed for Context Schemas.
2. **Docker Containment:** The `MCPAtom` strictly mandates `docker run -i --rm` for executing node/python servers, explicitly forbidding local `npx` zombie processes and unauthorized shell escalations.

---

## 18. Idempotent Graph Tombstoning (The UPSERT Bypass)

When flushing the in-memory NetworkX `TopologyGraph` to SQLite for the Persistent Storage Adapter (SF-2), we faced massive `UNIQUE constraint` deadlocks whenever an LLM agent requested to save an updated code file without deleting the previous version of the graph structure.

### How it works:
Instead of `SELECT`ing every node and deciding whether to `UPDATE` or `INSERT` in Python, we strictly enforce `sqlite3`'s mathematical `ON CONFLICT(semantic_hash) DO UPDATE SET is_active=1` within a single batch `executemany` chunk. Furthermore, nodes belonging to stale files are never `DELETE`d; instead they are explicitly "Tombstoned" (`is_active=0`).

### Why we do it:
1. **The Resurrection Rule (RT-13):** If an agent accidentally deletes a file or function, the graph tombstones it. If the agent hits a HITL barrier, the pipeline rolls back the git branch. The next orchestrator scan instantly "resurrects" the tombstoned node back to `is_active=1` simply by hitting the identical `semantic_hash` during the `UPSERT`. No data or LLM `metadata` context is ever lost during agent hallucinations.
2. **Batch Deadlock Immunity (RT-4):** Executing 5,000 Python conditional inserts locks the database. Offloading the logic entirely to native SQL C-bindings bypasses GIL lock starvation entirely.

---

## 19. Integer-Mapped Centrality (The RT-17 Math Fix)

When reconstituting the Persistent SQLite backup back into an in-memory `NetworkX` graph, using string-based `semantic_hash` as the primary NetworkX Node ID resulted in a 400% latency spike during complex Centrality or Pathing mathematical analysis (e.g. `nx.betweenness_centrality`).

### How it works:
Instead of importing the string hashes as primary keys, `load_from_db()` strictly assigns the SQLite `INTEGER PRIMARY KEY AUTOINCREMENT` `id` as the physical `NetworkX` node identifier. The `semantic_hash` is explicitly relegated to an internal `node["semantic_hash"]` attribute dictionary. 

### Why we do it:
NetworkX math operations natively optimize for `int` bindings via C-extensions or Numpy arrays under the hood. String manipulation permanently destroys this optimization. By passing back a synchronized `hash_to_id` map (`dict[str, int]`) to the Orchestrator, external string-based lookups remain `O(1)` without polluting the core graphing engine's math execution bounds.
