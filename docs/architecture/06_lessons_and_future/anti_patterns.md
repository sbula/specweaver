# Anti-Patterns (Learned)

| Anti-Pattern | Why It's Wrong |
|--------------|----------------|
| Putting tool-consuming code in `commons/` | Violates `forbids: tools/*` |
| Creating parallel security classes (e.g. `WorkspaceBoundary`) | Duplicates `FolderGrant` + `FileExecutor._validate_path()` |
| Centralizing tool definitions in a separate module | Each tool should own its own `ToolDefinition` list |
| God-object dispatcher reimplementing I/O | Delegate to actual tool methods instead |
| Naming modules by what the agent *does* ("research") | Name by what the code *is* |
| Domain modules importing from `sandbox/*` | 12 of 16 modules explicitly forbid this — use `flow/` as the bridge |
| Hiding dependencies via inline imports inside methods | Bypasses `tach` and obscures the actual module coupling density |
| Unchunked bulk graph ingestion into SQLite | Triggers `database is locked` deadlocks (RT-4); always batch `executemany` into 5,000-row chunks |
