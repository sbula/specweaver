# Sandbox (Execution Engine)

Three-layer architecture with strict dependency direction: **tools → atoms → commons**.

## Layers

- **tools/** — Agent-facing capability providers. Each tool has role-specific interfaces.
  - `filesystem/`, `git/`, `qa_runner/`, `code_structure/`, `web/`
- **atoms/** — Engine-internal workflow operations. Called by the flow engine, NOT by agents directly.
  - `filesystem/`, `git/`, `mcp/`, `qa_runner/`, `code_structure/`
- **commons/** — Shared executors and helpers. Pure infrastructure.
  - `filesystem/` (FileExecutor), `git/` (GitExecutor), `language/` (tree-sitter AST), `mcp/` (JSON-RPC bridge), `protocol/` (OpenAPI/proto parsers), `qa_runner/`

## Dependency Direction (STRICT)

```
tools → atoms → commons
  ↓        ↓        ↓
  (may import from layers below, NEVER above)
```

- A `tool` may import from `atoms` and `commons`. Never the reverse.
- An `atom` may import from `commons`. Never from `tools`.
- `commons` imports from NOTHING in sandbox. It is the leaf layer.

## Conventions

- All subprocess execution goes through `SubprocessExecutor` (in `commons/`).
- Role interfaces (e.g., `WriterFilesystemTool`, `ReaderFilesystemTool`) restrict agent capabilities.
- Security boundaries are enforced via the dispatcher + arbiter pattern.

## Test Commands

```bash
python -m pytest tests/unit/sandbox/ -v --tb=short
python -m pytest tests/integration/sandbox/ -v --tb=short
```

<!-- Last verified: 2026-07-12 -->
