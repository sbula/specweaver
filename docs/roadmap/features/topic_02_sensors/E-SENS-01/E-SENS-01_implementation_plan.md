# E-SENS-01 — Loom FS Tools: as built

**Design**: [E-SENS-01_design.md](E-SENS-01_design.md)

```
Model  ──▶ ToolDispatcher ──▶ role interface ──▶ FileSystemTool ──▶ FileExecutor
Engine ──▶ FileSystemAtom (symlink) ──────────────────────────────▶ EngineFileExecutor
```

| File (`src/specweaver/sandbox/filesystem/`) | Holds | FRs |
|:---|:---|:---|
| `core/executor.py` | `FileExecutor` (root, symlink, stream and protected-file checks; atomic writes) and `EngineFileExecutor` (no protected files) | FR-1, FR-2, FR-4 |
| `interfaces/tool.py` | `FileSystemTool`: role intents, grant check | FR-1 |
| `interfaces/definitions.py` | the four read tools a model is offered | FR-3 |
| `interfaces/facades.py` | role interfaces and `create_filesystem_interface` | — |
| `core/atom.py` | `FileSystemAtom`: `symlink`, used by `D-EXEC-02` to link caches into a worktree | — |
