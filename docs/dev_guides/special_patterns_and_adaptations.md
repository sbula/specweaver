# Special Patterns & Adaptations

Use when: you meet something in the codebase that breaks a common convention and want to know why,
or you are about to solve a problem one of these patterns already solves.

Each pattern: what it is, then why. Numbers are cited from other docs (§11, §23, pattern 26) — keep
them stable.

---

## 1. `context.yaml` boundaries

Python has no module visibility (`package-private`, `internal`); any file can import any other. So
every source directory carries a `context.yaml` that declares what it may consume and what it
forbids, e.g. `src/specweaver/sandbox/execution/context.yaml`. Shape:

```yaml
module: "sandbox"
description: "Agent-facing DMZ tool boundary"
forbids:
  - "sandbox.*"
  - "cli.*"
```

**Why:** stops an LLM or a developer wiring a core engine component into an outer layer. `tach_sync`
generates `tach.toml` from these files, and `tach check` fails the commit gate on a forbidden import
(e.g. `from specweaver.sandbox import EngineAtom` inside a `tools/` file).

---

## 2. Hand-written tool schemas (`definitions.py`)

LangChain, LlamaIndex and similar build the LLM's tool schema from `"""docstrings"""` and type
hints at runtime. **SpecWeaver forbids this.** Each tool's JSON schema is written by hand in its own
`definitions.py`.

**Why:**

1. **Hidden parameters**: internal parameters (`run_context`, `project_id`) can sit in the Python
   signature and be left out of the schema. The LLM never sees them.
2. **Prompt wording**: descriptions are written for the LLM, not as docstrings that must serve humans
   and models at once.

---

## 3. HITL gates

An LLM can generate working code that misses the business goal. So pipelines (`pipelines/*.yaml`)
carry human gates, `type: hitl`:

```yaml
gate:
  type: hitl
  on_fail: loop_back
  loop_target: rewrite_spec
```

**Why:** instead of failing or shipping blind, the engine parks the run, persists its state and waits
for the user. On rejection, `loop_target` rewinds to an earlier step and re-runs it with the user's
feedback. Details: `pipeline_engine_guide.md` §13.

---

## 4. The test battery

Beyond pytest, SpecWeaver runs a battery of validation rules (10 at the time of writing; the product
now describes a 12-test battery). "Spec rules" and "code rules" are separate. The static validation
engine uses tree-sitter AST checks and structural checks to confirm generated code matches the
Markdown design's constraints **before** tests run.

---

## 5. Validation stays pure logic (C05 import direction)

`assurance/validation` is `archetype: pure-logic` and `forbids: specweaver/sandbox/*` (the executor
layer, `Loom Commons`). The C05 rule
(`c05_import_direction.py`) still needs the polyglot architecture check that `sandbox.qa_runner`
provides. It gets it without importing it: the flow layer's validation hydrator
(`core/flow/handlers/validation_hydrator.py`) runs the check and puts the result in
`rule.context["qa_architecture_result"]`; C05 only reads it.

Replaced: C05 used to call `PythonQARunner.run_architecture_check()` itself under a boundary
relaxation (`forbids: "!sandbox.qa_runner"`). Hydration keeps one polyglot parser (Go, Python, TS)
without letting validation import the sandbox. See §12 for the hydration mechanism.

---

## 6. Deep-merged DAL matrices

A DO-178C-style DAL matrix tightens or relaxes rules per module criticality. `pydantic-settings` is
not used for it.

**How:** `.specweaver/dal_definitions.yaml` is read with `ruamel.yaml` and layered over the base
presets by `deep_merge_dict` (a recursive dict walker, `core/config/settings.py`). The merged dict
goes into `DALImpactMatrix(**merged)`.

**Why:** override frameworks drop whole sub-trees when a user config omits one child key.
`deep_merge_dict` keeps every default safety toggle and changes only the keys the user set.

---

## 7. Enums for LLM-proposed classifications (HARA)

When an LLM proposes structured data for engineering decisions (e.g. Hazard Analysis and Risk
Assessment — HARA), critical classifications are never plain strings.

**How:** in decomposition (`ComponentChange`), `proposed_dal` is typed as `DALLevel` (a `StrEnum`,
`commons/enums/dal.py`), not `str`.

**Why:** even with a prompt listing "DAL_A through DAL_E", models answer "DAL_Z" or "Critical". With
an enum, Pydantic's schema parser rejects that with a `ValidationError`, which triggers the
`loop_back` retry instead of corrupting SpecWeaver's state.

---

## 8. Plugin schema overlays

`context.yaml` can declare plugins that stack framework archetypes (e.g. `spring-boot` as the base,
`spring-security` on top).

**How:** `CodeStructureAtom._aggregate_merge` merges the plugins' flat YAML definitions: dicts merge
deeply, lists (like `["read_unrolled_symbol"]`) are unioned.

**Why:** if the security plugin says `intents: hide: ["list_symbols"]`, the merged config removes
that tool in `dispatcher.available_tools()` — no Python interception code.

---

## 9. AST skeleton extraction by parent-walking

Feature 3.22. A `.scm` `function_definition` query alone loses prefixes such as `@classmethod` or
TypeScript's `export default class`, so rewrites silently dropped them.

**How:** query only for the symbol's name node (`node_name`), then walk up the parents (e.g.
`name_node.parent.parent.type == 'decorated_definition'`) to include every wrapper around it.

**Why:** one upward walker covers all 9 supported languages (C/C++, Rust, Python, Java, Kotlin, TS,
SQL, Markdown) and keeps `@app.route` or `export async` without per-grammar query strings.

---

## 10. `CodeStructureAtom` writes to disk itself, with auto-indent

Feature 3.22, SF-2 (Polyglot AST Symbol Writer). An approved exception to the atom rule.

**How:** atoms normally return data (`AtomResult`) and leave side effects to `impl` tool facades.
`CodeStructureAtom` instead takes the mutated bytes from its tree-sitter parser and calls
`self._executor.write(path, mutated_code)` directly. Every multi-line string it inserts first goes
through `_auto_indent` (`workspace/ast/parsers/_editing.py`), which pads it to the AST node's margin.

**Why:**

1. **Context size**: returning a mutated 2,000-line file to the agent, only for it to pipe that into a
   separate `FileWriter` call, would blow the context window.
2. **Indentation**: padding against tree-sitter node boundaries, not by regex, prevents LLM
   `IndentationErrors` and brace errors across languages.

---

## 11. Git worktree sandboxing

Feature 3.26. An LLM generating a multi-file change could delete large parts of a dirty host `src/`.

**How:** the engine creates an isolated `.worktrees/` checkout with `git worktree add`; the agent
writes there. On reconcile, `_intent_strip_merge` merges the branch (`git merge -X ours`), then
restores or deletes every changed file not in `RunContext.isolation.allowed_paths`. `README.md` and
`docs/` are always stripped; `doc_updates.md` always survives. `_intent_worktree_teardown` removes the
worktree and, on failure, retries `shutil.rmtree` with a 5-step backoff (`0.05, 0.1, 0.2, ...`)
followed by `git worktree prune`. Modes and policy: `pipeline_engine_guide.md` §7.

**Why:**

1. **Strip, don't fail**: an agent cannot rewrite central config (`Pipfile`, `pom.xml`, `README.md`).
   Those files are dropped and the valid changes still land.
2. **Windows locks**: indexing and anti-virus lock freshly written directories under `.worktrees/`; an
   immediate delete fails and halts the pipeline. The backoff waits for the locks and finishes under
   2 seconds.

Replaced: the allow-list used to come from `context.yaml` boundaries and was applied with a filtered
`git apply`. It now comes from the run's `allowed_paths`, which the composition root sets.

---

## 12. Rule context hydration (the `**kwargs` bypass)

Validation rules get system-injected data (e.g. `CodeStructureAtom` AST payloads) through the
`Rule.context` property, not constructor arguments.

**How:** a rule never declares `def __init__(self, required_markers: list = None, ast_payload: dict = None):`.
The validation executor (`assurance/validation/executor.py`) pops system payloads out of the step
params (`step_params.pop("ast_payload", {})`) and sets `rule.context = payload` after construction.
`**kwargs` stays reserved for YAML params.

**Why:** unpacking `**step.params` into a rule would crash every rule with
`TypeError: unexpected keyword argument` as soon as the engine adds a system parameter. With
post-init hydration, `C12ArchetypeCodeBoundsRule` reads `.context` while `PARAM_MAP` stays intact.

---

## 13. Flat archetype evaluators (no LSP)

The validation engine checks framework annotations (Kotlin's `@RestController`, Rust's
`#[derive(Clone)]`) without language servers or compiler plugins.

**How:** `SchemaEvaluator` reads flat YAML files (`fastapi.yaml`, `actix-web.yaml`) in
`workflows/evaluators/frameworks/` that map decorators/macros to what they do. Files are per
**archetype**, not per language: no `java.yaml`, but a `spring-boot.yaml` with
`metadata.supported_languages: ["java", "kotlin"]`.

**Why:**

1. **Speed**: an LSP or rust-analyzer adds 5–10 seconds per check inside generation loops. The YAML
   lookup takes about `0.01` seconds.
2. **No cross-framework matches**: `supported_languages` means a `FastAPI` construct in a `Node.js`
   TypeScript worker simply does not match, instead of breaking the parser.
3. **`decorator_filter`**: the same markers (via `extract_framework_markers`) power
   `list_symbols(decorator_filter="PreAuthorize")`, so an agent finds annotated symbols without
   reading whole files.

---

## 14. JSON facade (`orjson`)

Feature 3.32 (`< 50ms` NFR targets). All `import json` usage was replaced by the Rust-backed
`orjson`, behind one facade: `specweaver.commons.json`. Every module imports
`from specweaver.commons import json` (29+ modules), never `orjson.dumps().decode('utf-8')` by hand.

**Why:**

1. **`bytes` vs `str`**: `orjson.dumps()` returns `bytes`. Passing bytes to Pydantic, log formatters or
   prompts fails with `TypeError: input must be a string, not bytes`. The facade does the
   `.decode('utf-8')`, so callers always get a UTF-8 `str`.
2. **Stable key order**: LLM caching needs identical strings. The facade maps `sort_keys=True` to
   `orjson.OPT_SORT_KEYS`.

---

## 15. Topology cache (`.specweaver/topology.cache.json`)

Feature 3.32. The `TopologyGraph` (the project's structural map) needs tree-sitter parsing of every
`context.yaml` boundary.

**How:** `DependencyHasher` hashes source files into Merkle roots and stores them in
`<project_root>/.specweaver/topology.cache.json`. It adds `/.specweaver/` to the repo's root
`.gitignore`.

**Why:**

1. **`< 50ms` NFR**: later runs compare fingerprints instead of re-reading thousands of files.
2. **Worktrees (§11)**: `.specweaver` is symlinked into each worktree, so the sandbox uses the trunk's
   cache.

> [!CAUTION]
> **Never flush the cache while building the graph.**
> `TopologyGraph` computes `graph.stale_nodes` from the cache, so the cache is the baseline the diff
> is measured against. If `TopologyGraph.from_project()` rewrote `topology.cache.json`, the next run
> would see no changes and let broken code skip validation. Only the CLI orchestrator (`pipelines.py`; since moved (2026-09-25):
> `core/flow/interfaces/cli.py`) saves it (`DependencyHasher.save_cache()`), and only after `PipelineRunner` returns
> `RunStatus.COMPLETED`. Saving from inside `flow` would break the `flow`/`graph` boundary.

> [!CAUTION]
> **Tombstones (deleted dependencies)**
> A deleted module disappears from the directory scan, but its consumers still declare
> `consumes: [deleted_module]` in their `context.yaml`. `_calculate_stale_seeds` flags any consumer
> with a dangling reference as a `stale_seed`, so its tests run and fail.

---

## 16. Vault Binding Shield (Option D)

Feature 3.32c (MCP credentials). Risk: a user or LLM runs `git commit` with `.specweaver/vault.env`.

**How:** `PipelineRunner.run()` and `PipelineRunner.resume()` run a pre-flight check. If
`.specweaver/vault.env` exists, `GitAtom` (`_intent_is_tracked`) runs
`git ls-files --error-unmatch .specweaver/vault.env`.

**Why:**

1. **Layering**: configuration (`context.yaml` models) lives in the L2 `config` and `assurance`
   layers. Calling `subprocess.run(["git", "ls-files"])` there would break the Tach bounds. The check
   sits in the orchestrator (L3 Flow), which may use `Loom Atom`s.
2. **No fallback**: a tracked vault means the repo is compromised. The runner raises `RuntimeError`
   and stops — no rollback, no HITL — before credentials can be pushed.

---

## 17. Thread-pumped JSON-RPC executor (`MCPExecutor`)

Feature 3.32c SF-2. Local MCP servers speak JSON-RPC over stdio. External SDKs (the `mcp` PyPI
package) were rejected: they need an async event loop, which the `async_ready: false` core layers
(`commons`) forbid.

**How:** not `asyncio.create_subprocess_exec`. `MCPExecutor` starts `subprocess.Popen` with
`subprocess.PIPE` buffers (a declared TID251 exemption: `SubprocessExecutor` is one-shot and cannot
hold a long-lived pipe). For timeouts without `select`/`fcntl` (which fail on Windows):

1. A daemon `threading.Thread` runs `iter(process.stdout.readline, "")`.
2. It feeds an unbounded `queue.Queue`.
3. `call_rpc` correlates replies by request id (`self._request_id += 1`) and reads with
   `_queue.get(timeout=...)`.

**Why:** a hung container stalls only the reader thread; `call_rpc` times out cleanly. No `AsyncIO`
is needed further down, so validation stays synchronous.

---

## 18. Idempotent graph tombstoning (UPSERT)

Flushing the in-memory NetworkX `TopologyGraph` to SQLite hit `UNIQUE constraint` deadlocks when an
agent saved a file whose old graph nodes were still stored.

**How:** in `sqlite3`, one batched `executemany` with `ON CONFLICT(semantic_hash) DO UPDATE SET is_active=1` — no
`SELECT` then `UPDATE`/`INSERT` in Python. Nodes of stale files are never `DELETE`d; they are
tombstoned (`is_active=0`).

**Why:**

1. **Resurrection (RT-13)**: if an agent deletes a file or function, its node is tombstoned. If a HITL
   gate then rolls the branch back, the next scan hits the same `semantic_hash` and sets
   `is_active=1` again. No node or LLM `metadata` is lost.
2. **No deadlocks (RT-4)**: 5,000 conditional inserts from Python lock the database; one SQL batch
   does not hold the GIL.

---

## 19. `semantic_hash` is the node ID (no integer mapping)

`TECH-004` deleted an integer remapping layer (`_hash_to_int`, `_int_to_hash`, `_next_int_id`) that
mapped `semantic_hash` strings to autoincrement `int` IDs for NetworkX. It was a premature
optimisation (no centrality math at scale exists) and the root cause of three bugs: **AP-4** (type
mismatch on flush), **AP-10** (ID-map corruption when loading a loaded graph), **AP-11**
(non-roundtrippable load/flush).

- **Canonical ID**: public APIs and `InMemoryGraphEngine` use the `semantic_hash` string as the
  `NetworkX` node key. Round trips need no translation.
- **Storage ID**: autoincrement integers (`ROWID`) are internal foreign keys inside
  `SqliteGraphRepository` (edge-table efficiency) and never leave it.

---

## 20. Lazy `%s` logging

Feature 3.33. Use the standard `logging` module with `%s` interpolation. No `f-strings` or `.format()`
in `logger.debug()` / `logger.info()` calls.

Every module has `logger = logging.getLogger(__name__)`.
Write: `logger.debug("Parsing spec: %s", spec_path)`
Never: `logger.debug(f"Parsing spec: {spec_path}")`

**Why:**

1. **Cost**: an f-string is built before the call, even when the CLI runs at `INFO` or `WARNING`
   and the `DEBUG` record is thrown away. With `%s`, formatting happens only after the level check — no cost for disabled levels.
2. **Aggregation**: tools like Datadog or ELK group records by the static message string. f-strings
   make every message unique.

---

## 21. Async SQLite: FK PRAGMA and `expire_on_commit`

Feature B-INTL-09 (Agent Memory Bank), SQLite with `sqlalchemy[asyncio]`.

**How:**

1. **PRAGMA hook**: `register_fk_pragma_listener(engine)` (`core/config/database.py`) registers
   `@event.listens_for(engine.sync_engine, "connect")` and runs `PRAGMA foreign_keys=ON` on every new
   connection, in production and in tests.
2. **`expire_on_commit=False`** on test fixtures and the CQRS `AsyncSession` factories. Otherwise
   SQLAlchemy lazily reloads expired attributes after `commit()`, and with no running greenlet (sync
   teardown, assertions) that fails with `MissingGreenlet`.

**Why:** unlike PostgreSQL or MySQL, SQLite starts every connection with `foreign_keys=OFF`, and `aiosqlite` opens pooled
connections without honouring `?foreign_keys=1` in the URL. Without the hook, deleting an `Epic`
leaves its `Task` rows orphaned instead of running `ON DELETE CASCADE`.

**Timestamps**: `SQLAlchemy` `default=datetime.now` runs in Python, and rapid inserts in async loops
collided or lost the timezone. In `specweaver.workspace.memory.repository`, **every mutation method
creates `datetime.now(UTC)` itself and passes it to the model** — `default=` is not used.

---

## 22. Invoke interpreters by resolved path (Windows `System32` shadowing)

Found in `BashActionAtom` (C-EXEC-02 SF-01), which runs `.specweaver/scripts/` through
`SubprocessExecutor`.

**How:** with Git for Windows and WSL both installed, `shutil.which("bash")` finds Git's `bash.exe`
(it follows `%PATH%`). But `subprocess.Popen(["bash", ...])` (list argv, `shell=False`) uses
Windows `CreateProcess`, which searches `C:\Windows\System32` — home of the WSL launcher stub —
**before** `%PATH%`. So WSL's `bash` runs, whatever the `PATH` order.

Rule: call `shutil.which("bash")` once and pass the **returned absolute path** as `argv[0]`, never
the bare string `"bash"`. Path format (`C:\...` vs `C:/...`) does not matter once the binary is
right.

**Why:** a `shutil.which()` check followed by `Popen` with the bare name is two independent lookups
that can disagree. Any Atom or Tool that runs a named interpreter must resolve once and reuse that
path.

---

## 23. Swap the execution target by subclassing the executor

`ContainerSubprocessExecutor` (B-EXEC-01) runs QA-runner commands in an ephemeral Podman/Docker
container instead of the host, without changing the result contract callers rely on.

**How:** `PythonQARunner.__init__(cwd, executor: SubprocessExecutor | None = None)` — and the other
language runners — are typed to the concrete `SubprocessExecutor`, not a protocol. A wrapper that
merely holds a `SubprocessExecutor` would fail strict mypy unless that signature were widened across
5 language runners. So `ContainerSubprocessExecutor(SubprocessExecutor)` **subclasses** it and
overrides only `execute()`: it wraps `cmd` into a `<podman|docker> run ...` argv and calls
`super().execute(wrapped_cmd, ...)`, reusing the parent's timeout escalation, credential stripping
and `SubprocessResult` construction.

**Why:**

1. **No call-site changes**: anything typed `SubprocessExecutor | None` accepts the subclass (Liskov
   substitution, not a parallel interface).
2. **Not a parallel security class**: the subclass delegates to the parent's machinery rather than
   duplicating it, so it does not hit the anti-pattern that forbids re-implementing
   `WorkspaceBoundary`-style primitives.
3. **Reuse it**: to swap a component's execution target (another sandbox tier, a remote executor, a
   dry-run recorder) behind a stable, concretely typed constructor, reach for this before a new
   abstraction.

> [!CAUTION]
> **Host-specific paths do not survive the swap.** After wiring it into `PythonQARunner` (Commit
> Boundary 2), `run_debugger()` still built its command from `sys.executable` — the host
> interpreter's path. `run_tests`, `run_linter` and `run_complexity` already used the bare string
> `"python"`, resolved inside whatever environment runs it. Only a **real-engine integration test**
> caught it; a mock accepts any argv. When an execution target becomes swappable, audit every call
> site for host assumptions (interpreter paths, absolute tool paths, host env vars), and pair the
> pattern with at least one real, unmocked run against the new target.

---

## 24. Self-naming writers: derive the name, assert the round trip

`FeatureDrafter.draft(name, output_dir)` takes no target path; it **derives** its output as
`output_dir / f"{name}_feature_spec.md"` and returns it. Downstream steps (`validate+feature`,
`decompose+feature`) read `context.spec_path`. Wrapped naively, the drafter writes a file nobody
opens: the step PASSES, the next one says "spec not found".

**How:** `DraftFeatureHandler` (`core/flow/handlers/draft.py`) computes the `name` that makes the
writer produce the path already wanted:

1. **Guard the shape first**: reject any `spec_path` not matching `<non-empty>_feature_spec.md` with
   an ERROR before prompt building or LLM setup — a bad name costs zero tokens.
2. **Slice, never `removesuffix`**: `str.removesuffix` silently does nothing when the suffix is
   missing, so `foo.md` would give `name="foo"` and write `foo_feature_spec.md`.
3. **Reject the empty stem**: `_feature_spec.md` passes a suffix check, gives `name=""`, and round
   trips perfectly. Only an explicit non-empty check catches it.
4. **Assert the round trip**: compare the returned path with `context.spec_path`; ERROR on mismatch.
   Steps 1–3 make it correct today; step 4 fails loudly if the writer's naming ever changes.

**Why:**

1. **The failure is silent and misattributed** — an orphaned spec, reported at another step.
2. **Cheaper than the alternatives**: widening `FeatureDrafter.draft()` changes a shipped signature;
   renaming after the fact leaves a window where the wrong file exists.
3. **Reuse it** for any component that names its own output (report writers, exporters, scaffolders,
   code generators): derive the input, guard the shape before expensive work, assert the round trip
   at the wrapper, not three steps downstream.

---

## 25. Consistent-rename fixpoint (refactor-safety gate)

`scripts/tests.py --kind refactor` catches "refactors" whose tests were bent to hide a bug. The rule
is `_is_safe_file_diff` in `scripts/_refactor_diff_safety.py`, grown in TDD-pinned stages: pure
additions and dotted-path moves (TECH-001 SF-04) are safe by construction; a *literal identifier
rename* consistent across a file — the shape of TECH-005 SF-03's table renames in test SQL strings —
is recognized by `_infer_token_rename_map`.

**How:** one greedy pass cannot handle **several simultaneous renames** (`nodes` -> `graph_nodes` on
most lines, `edges` -> `graph_edges` on one): a line from the wrong rename can match by coincidence.
The gate resolves a **fixpoint**: each round locks in only removed lines whose candidates — after
dropping those conflicting with pairs already fixed — reduce to exactly one `(old_token, new_token)`
pair; repeat until nothing changes. A line still ambiguous at the end, or whose only match was taken,
is unexplained, and the file is **not** safe. Bare numbers are never candidates (`[A-Za-z_]\w*`):
otherwise `assert result == 5` -> `assert result == 3` next to a real rename was once taken as "the"
rename and let a weakened assertion through.

**Why:**

1. **Extending tests stays easy; hiding a bug stays hard.** A blanket "no test diffs" check blocks a
   renamed table as hard as a bug-hiding edit, and people learn to route around it. Each extension
   admits one more *provably* safe pattern — never an escape hatch.
2. **Reuse it**: a diff classifier separating "mechanical, provably safe" from "same shape, different
   behaviour" should use fixpoint/constraint propagation once several substitutions can coexist in a
   file, and pair each new safe pattern with an adversarial test of the bug-hiding shape it must still
   reject.

---

## 26. Union-only contribution in change-driven test selection

`scripts/tests.py` picks tests from what a diff touched. It assumed every change was a `src/` change.
A `scripts/`-only change (nothing mapped `scripts/` to its `tests/unit/scripts/` mirror) and then a
tests-and-docs-only change both resolved to zero paths and were
reported as *"you changed source that nothing mirrors"*, though in the second case no source had
changed.

**How:** a changed **test** file now contributes its own module, as a source file does (`_tier_relative`
maps `tests/unit/core/flow/test_x.py` → `core/flow/test_x.py`), and the two sets are **unioned**.

- A changed test can **add** a module to the run. It can never redirect or remove one.
- So *"editing a test must not be what decides which tests run"* still holds: under a union a test
  **contributes**, it does not **decide**.
- The mapping is **tier-specific**: a test's tier is in its own path, while a source file serves every
  tier. Otherwise editing an e2e test would pull in unit paths.
- At `touched` scope a changed test resolves to **itself** — the `test_{stem}*.py` glob would look for
  `test_test_x*.py`.

Mapping is by **directory**, an admitted proxy: an integration test spanning three modules maps to the
directory it sits in. The source side uses the same proxy, and the code says so.

**Why:**

1. **A blocked gate names the cause it can prove.** `_blocked_reason()` *computes* which applies:
   source-with-no-mirror, tests-with-no-mirror, or nothing-in-this-tier-at-all.
2. **Reuse it**: when a selector derives scope from a change set, prefer union-only contribution, so a
   new input class can widen the selection but never narrow it. A selector that narrows on unfamiliar
   input fails silently green. A gate that refuses must tell its reasons apart in code — a hard-coded
   reason is an untested claim.
3. **Operator messages need tests.** The false message survived because nothing read it.

---

## 27. Polyglot traceability via comment tags (C09)

Feature 3.21 (Automated Traceability Matrix): every spec requirement must map to a test. No coverage
tools, no instrumentation, no `@pytest.mark.trace("FR-1")`.

**How:** the same tag in every language — `# @trace(FR-1)` in Python, `// @trace(FR-1)` in Java.
The engine picks a tree-sitter parser by file extension, visits only `comment` nodes, and builds the
matrix in memory.

**Why:**

1. **No application dependency**: static analysis only; nothing is imported into the user's code.
2. **Any language**: tree-sitter handles comment extraction, so one codebase traces Python, Rust, Go,
   JavaScript, TypeScript, C++ and SQL with no framework lock-in.

---

## 28. Pre-fetched MCP context envelope

Feature 3.32c (Pre-Fetch Assembler). Giving the LLM MCP tools floods the system prompt and burns tool
calls.

**How:** the flow engine reads the `consumes_resources` block of `context.yaml`
(`core/flow/handlers/mcp_assembler.py`) to get MCP URIs ahead of time. Before an LLM step, `MCPAtom`
fetches those resources sequentially over `stdio` and formats them as text, injected into the
prompt's `<environment_context>` block as a static snapshot.

Rules:

1. **No LLM tool definitions** for context schemas — no dynamic tool calls.
2. **Container only**: `MCPAtom` runs servers only under `docker` or `podman`, and rejects host-escape
   arguments (`--privileged`, `--network=host`, `--cap-add`, …) and host mounts (`/`, the docker
   socket, `/etc`, `/root`). No local `npx` processes or shell escalation.
