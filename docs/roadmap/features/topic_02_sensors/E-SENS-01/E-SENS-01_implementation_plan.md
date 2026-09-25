# E-SENS-01 — Loom FS Tools

**Status**: ✅ COMPLETED (183 tests) — implemented 2026-03-10, test-first · Roadmap section 3.7
(Loom: Filesystem Tools & Atoms)

## Architecture

```
Agent    ──▶ Interface ──▶ FileSystemTool ──▶ FileExecutor        (commons/)
Engine   ──▶ FileSystemAtom ─────────────────▶ EngineFileExecutor  (commons/)
```

## As built

~2000 LOC new code (source + tests).

| File | Holds | Tests |
|:---|:---|:---|
| `loom/commons/filesystem/executor.py` | `FileExecutor` + `EngineFileExecutor` | ✅ 54 tests (+6 skipped) |
| `loom/tools/filesystem/tool.py` | `FileSystemTool` | ✅ 66 tests |
| `loom/tools/filesystem/interfaces.py` | 3 role interfaces + `create_filesystem_interface` factory | ✅ 42 tests (+1 skipped) |
| `loom/atoms/filesystem/atom.py` | `FileSystemAtom` | ✅ 21 tests |
| `context.yaml` | boundary manifests for both the tools and the atoms module | ✅ |

- **`FileExecutor` / `EngineFileExecutor`** — low-level ops (read, write, delete, mkdir, list,
  exists, stat, move) with path traversal prevention, symlink blocking, protected patterns, atomic
  writes, Windows ADS blocking.
- **`FileSystemTool`** — role-based intent gating, `FolderGrant` boundary enforcement,
  `find_placement` (keyword MVP), `search_content` (recursive). `_normalize_path` uses
  posixpath.normpath so `../` cannot bypass a grant.
- **Role interfaces** — `ImplementerFileInterface`, `ReviewerFileInterface`,
  `DrafterFileInterface`.
- **`FileSystemAtom`** — 5 intents: `scaffold`, `backup`, `restore`, `aggregate_context`,
  `validate_boundaries` (including consumes reference validation).

**Since moved** (noted 2026-09-25): `loom/` is now `src/specweaver/sandbox/filesystem/` —
executors in `core/executor.py`, atom in `core/atom.py`, tool in `interfaces/tool.py`, role
interfaces + factory in `interfaces/facades.py`.
