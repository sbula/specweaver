# Adding a Tool and Atom

Use when: you add an agent or engine capability (e.g. File I/O, Git, Web Search) to SpecWeaver.

LLMs are untrusted (zero-trust), so no capability is exposed directly. Each capability serves two
consumers, the **Untrusted LLM Agent** and the **Trusted Flow Engine**, through parallel components
on a shared executor:

```text
For the Agent (Untrusted):
LLM Agent ──▶ Role Interface ──▶ Intent Tool ──▶ Executor (Raw I/O)
(Note: Complex tools like `CodeStructureTool` may securely encapsulate trusted `Atoms` and logical capabilities like `SchemaEvaluator` under the hood to prevent duplicating parsing logic, but they still strictly enforce Role/Folder Grants before delegation.)

For the Engine (Trusted):
Flow Engine ──▶ Atom ──▶ Executor (Raw I/O)
```

## Components

Layout: `src/specweaver/sandbox/<domain>/core/` (executor, atom) and
`src/specweaver/sandbox/<domain>/interfaces/` (tool, definitions, facades).

| Component | File | Job | Rule |
|---|---|---|---|
| Executor | `core/executor.py` (e.g. `FileSystemExecutor`, `GitExecutor`) | Raw I/O: subprocess execution, transport security (symlink blocking, binary parsing, path traversal protection) | Never imports the tool or atom |
| Tool | `interfaces/tool.py` | Operations by Intent. Enforces `ROLE_INTENTS` (e.g. no compilations for a role that lacks the intent) and `FolderGrant` boundaries | |
| Interface | `interfaces/facades.py`, `sandbox/dispatcher.py` | Removes unauthorized commands before the LLM sees them: absent from the dispatch table or dropped from the payload | |
| Atom | `core/atom.py` | Unrestricted operations for the flow engine only. Bypasses `ROLE_INTENTS` and `FolderGrant`, calls the Executor | NEVER imports the Tool |

A Tool *may* instantiate an Atom to reuse its operations, after validating role constraints.

### Dynamic masking and exclusions

- **Dynamic Masking (Feature 3.30a):** orthogonal `plugins` (e.g. `spring-security`) in
  `context.yaml` use `intents.hide` to make `ToolDispatcher` remove tool methods (like `edit_file`)
  from the LLM globally, without Python changes.
- **Dynamic System Exclusions (Feature 3.32b):** `ToolDispatcher` applies polyglot filesystem
  exclusions for tools like `FileSystemTool`. It reads the injected
  `analyzer_factory.get_all_analyzers()` (Flow Context DI) and pushes language-specific exclusions
  (e.g. `node_modules`, `target`) down into the raw executors, bypassing the agent.

## Steps

Example: `SearchWeb`.

1. **Executor**: `src/specweaver/sandbox/web/core/executor.py`. Native logic via API boundaries or
   `SubprocessExecutor`.
2. **Tool**: `src/specweaver/sandbox/web/interfaces/tool.py`. Put capabilities behind Intents.
3. **Definitions**: the `ToolDefinition` payload sent to the LLM (OpenAI/Anthropic compatible
   schema) in `definitions.py`.
4. **Facades**: role facades (e.g. `ReviewerWebInterface` vs `ImplementerWebInterface`) in
   `facades.py`.
5. **Atom**: `src/specweaver/sandbox/web/core/atom.py` with a `run(context)` method for autonomous,
   non-LLM use by the Flow Engine.
6. **Single-op or multi-op**: decide per domain. "Atom" only means *engine-internal, not
   agent-facing*; it says nothing about how many operations `run()` covers.
   - One operation: read the expected keys straight off `context` (see `RuleAtom`).
   - Several related operations: read an `intent`/`action` key and dispatch internally (see
     `QARunnerAtom`'s `run_tests`/`run_linter`/`run_complexity`/`run_compiler`/`run_debugger`/`run_architecture`,
     or `LanguageAtom`'s `detect_language`/`convert_scenario`).
   - Do not copy the shape of another Atom without checking how many operations your domain has.
7. **Wire up**: the Tool facade inherits `BaseTool` (`specweaver.sandbox.base`) and implements the
   `role` property and `definitions()`.
8. **Register**: add a lazy-loaded closure to `specweaver.sandbox.registry.get_standard_registry()`
   that cherry-picks only the `kwargs` it needs (e.g. `role`, `cwd`). The Flow Engine resolves and
   injects the tool through `ToolRegistry`; no manual binding in `dispatcher.py`.

## Rules

- **Never** put a Tool in `commons/`. Tools need the Executor layer.
- **Never** add parallel security checks. Use `FolderGrant` and the path-traversal hooks.
- Keep trusted/untrusted apart in `context.yaml`: `interfaces/` consumes `core/`, never the
  reverse. (Older docs: `manifest.yaml` / `forbids: atoms/*`.)

## Exception: architect-only tools (MCP)

Some tools, like `MCPExplorerTool`, are NOT allowed in standard pipelines. They use dedicated
facades such as `ArchitectMCPInterface`, mapped only to the L2 Architect role. Reference for
validating role intents at `ToolDispatcher` binding: `sandbox/mcp/interfaces/tool.py`.
