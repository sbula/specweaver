# C-EXEC-01 SF-08 — TopologyGraph to Tach Adapter

**Status**: APPROVED · **FRs owned**: FR-5 · **Feature ID**: 3.20a · Design:
[C-EXEC-01_design.md](C-EXEC-01_design.md) §Sub-features → SF-08

FR-5 (a `TopologyGraph` written out as the target project's `tach.toml`) is new — this sub-feature
shipped without a requirement. Recorded 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-01-SF02-MIG`. Its first mutant was *equivalent*: disabling the `[[modules]]` purge changes
nothing while the graph is populated, because the rebuild reassigns the key; the purge matters only
for an emptied topology, which is now the test.

**Since moved:** `src/specweaver/project/tach_sync.py` → `src/specweaver/workspace/project/tach_sync.py`
(`sync_tach_toml(graph, target_path)`); `scan` is wired in `workspace/project/interfaces/cli.py`.
Paths below are as of the plan's date.

## Goal

When SpecWeaver maps the bounded contexts of a target codebase (`context.yaml` → `TopologyGraph`),
write them into the target's `tach.toml` so its CI/CD checks them.

## Decisions

| # | Question | Chosen | Why |
|---|---|---|---|
| 1 | Module placement | `src/specweaver/project/tach_sync.py` | `graph/` is `pure-logic` and cannot do file I/O; `project/` (`adapter` archetype) already owns `.specweaver/` setup and filesystem work |
| 2 | Serializer | add `tomlkit` to `pyproject.toml` | Python 3.11's `tomllib` is read-only; `tomli-w` drops developer comments; `tomlkit` keeps formatting, comments and root properties |
| 3 | Sync strategy | keep root definitions (e.g. `exclude = []`, `source_roots = ["."]`); destructively overwrite `[[modules]]` and `[[interfaces]]` | `context.yaml` is the single source of truth; `tach.toml` must mirror `TopologyGraph.nodes` |
| 4 | UX | run inside `sw scan` (`src/specweaver/cli/projects.py`), no new flag or command | Mimics `scaffold.py`: returns a `TachSyncResult` and prints the modified counts |

## Changes

1. **`pyproject.toml`** — add `tomlkit>=0.12.0` to the main `dependencies` array.
2. **NEW `src/specweaver/project/tach_sync.py`** — imports `TopologyGraph` and `tomlkit`;
   `sync_tach_toml(graph: TopologyGraph, project_path: Path) -> TachSyncResult`:
   - load the file via `tomlkit.parse` if `(project_path / "tach.toml").exists()`, else
     `tomlkit.document()`;
   - set root `source_roots = ["."]` and `exact = true`;
   - delete any existing `"modules"` / `"interfaces"` arrays;
   - for each `TopologyNode` in `graph.nodes.values()`: a `[[modules]]` block (`path` = the node's
     Python import path, `depends_on` = `consumes`); if `node.exposes` is set, an `[[interfaces]]`
     block (`from` = module path, `expose` = `exposes`);
   - write `tomlkit.dumps()` over `tach.toml`; return a `TachSyncResult` dataclass counting updated
     module paths.
3. **`src/specweaver/project/context.yaml`** — `consumes` gains `specweaver/graph`; `exposes` gains
   `sync_tach_toml` and `TachSyncResult`.
4. **`src/specweaver/cli/projects.py`** — in the `scan()` Typer command, after `context.yaml`
   auto-inference: `graph = TopologyGraph.from_project(project_path)`,
   `result = sync_tach_toml(graph, project_path)`, then a rich console line (e.g.
   `[bold]Tach Sync[/bold]: synchronized X modules boundaries into tach.toml`).

## Tests

- `tests/unit/project/test_tach_sync.py`:
  - no `tach.toml` → a new one built from a mocked `TopologyGraph`;
  - an existing `tomlkit` document with `exclude = ["dist"]` → old modules removed, `exclude` kept.
- `pytest tests/unit/project/test_tach_sync.py`; an E2E check of `import tomlkit`.
- Gate: `ruff check`, `mypy`; the architecture check passes since `project/context.yaml` consumes
  `graph`.
