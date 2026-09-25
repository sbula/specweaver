# A-SENS-01 SF-02 — Semantic State Caching

**Status**: DRAFT (every change below is DONE; the design tracker records it committed) ·
**Feature ID**: 3.32 · **FRs owned**: FR-1, FR-2, NFR-1 · **Depends on**: SF-01 ·
Design: [A-SENS-01_design.md](A-SENS-01_design.md) §Sub-features → SF-02

## Goal

A utility that computes and persists shallow and structural Merkle dependencies for cross-service
topology caching.

- **FR-1:** `sha256` of file contents + Merkle roots of all extracted imports → `semantic_hash`.
- **FR-2:** reads/writes `.specweaver/topology.cache.json`.
- **NFR-1:** bootstrapping under 50ms total.

## Changes

1. **Dependency hasher** · `[NEW]` `src/specweaver/assurance/graph/hasher.py` — hashes
   `context.yaml` directories and maintains `topology.cache.json`. Maps a directory's files to
   `hashlib.sha256()` recursively, then parses local boundary dependencies. A directory's Merkle hash
   is `hash(file_hashes + imported_module_hashes)`. Key signatures:

```python
def __init__(self, project_root: Path):
    self.project_root = project_root
    self.cache_path = project_root / ".specweaver" / "topology.cache.json"

def compute_hashes(self, manifests: list[Path]) -> dict[str, Any]:
    # Analyzes module boundaries via `LanguageAnalyzers` and dedupes natively.
```

2. **Architecture fix** · `src/specweaver/assurance/graph/context.yaml` — `consumes` said
   `specweaver/context`; the correct namespace is `specweaver/workspace/context`.
3. **Dependency** · `pyproject.toml` — `orjson>=3.9.0` added to root `dependencies = [...]` for
   faster serialization.
4. **orjson everywhere** · `src/specweaver/...` (all 29 locations) — `import json` replaced with the
   `specweaver.commons.json` facade, so the codebase does not mix the two.
5. **`.gitignore` protection** · `src/specweaver/assurance/graph/hasher.py` (not
   `src/specweaver/workspace/project/git.py`) — `_ensure_gitignore(project_root: Path)` walks up from
   `project_root` to the first `.git/`; if found, appends `\n/.specweaver/\n` inside a tracked
   `# SpecWeaver Auto-Generated` comment block (NFR-2). No `.git` → silently skipped.

> [!WARNING]
> **orjson decode trap:** `json.dumps()` returns `str`; `orjson.dumps()` returns `bytes`. The
> `commons.json` facade appends `.decode('utf-8')`, so payloads passed to LLM prompt builders,
> Pydantic initializers and logging stay `str`.

## Tests

`tests/unit/assurance/graph/test_hasher.py`:

| Case | Proves |
|---|---|
| synthetic 1,000-module graph, `timeit` bound | the 50ms limit |
| nested dummy trees under `.tmp` | the `.gitignore` climber |
| add/remove dummy modules | orphan key pruning |

## Decisions (audit)

1. **Serialization via `orjson`**: `orjson.dumps()` / `orjson.loads()` to meet `< 50ms`.
2. **Orphan key pruning**: the hasher receives the active manifest list from
   `TopologyGraph.from_project()` and intersects keys, pruning deleted files.
3. **`.gitignore` climbing**: hierarchical path-climbing, as in change 5.
