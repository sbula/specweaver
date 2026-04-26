# Implementation Plan: Deep Semantic Hashing [SF-2: Semantic State Caching]
- **Feature ID**: 3.32
- **Sub-Feature**: SF-2 — Semantic State Caching
- **Design Document**: docs/roadmap/features/topic_02_sensors/A-SENS-01/A-SENS-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/A-SENS-01/A-SENS-01_sf2_implementation_plan.md
- **Status**: DRAFT

## 1. Sub-Feature Scope & Requirements
Implements a dedicated utility for computing and persisting shallow and structural Merkle dependencies for cross-service topology caching.
- **FR-1:** Combines `sha256` of file contents + Merkle roots of all extracted imports into a `semantic_hash`.
- **FR-2:** Reads/Writes `.specweaver/topology.cache.json`.
- **NFR-1:** Speed / Overhead (Bootstrapping must sit under 50ms total).

## 2. Technical Modifications

### A. Dependency Hasher (`src/specweaver/assurance/graph/hasher.py`) [DONE]
[NEW] `src/specweaver/assurance/graph/hasher.py`

**Purpose**: Responsible for generating hashes from `context.yaml` directories and maintaining the `topology.cache.json`.
**Key Algorithm**: Must recursively map a directory's files to `hashlib.sha256()`. Then parse local boundary dependencies. A directory's final Merkle Hash is defined as: `hash(file_hashes + imported_module_hashes)`.

**Key Signatures**:
```python
def __init__(self, project_root: Path):
    self.project_root = project_root
    self.cache_path = project_root / ".specweaver" / "topology.cache.json"

def compute_hashes(self, manifests: list[Path]) -> dict[str, Any]:
    # Analyzes module boundaries via `LanguageAnalyzers` and dedupes natively.
```

### A.2 Architecture Strictness Patch [DONE]
[MODIFY] `src/specweaver/assurance/graph/context.yaml`
- **Violation Found**: The current context consumes `specweaver/context`. The correct namespace is `specweaver/workspace/context`. This typo will be fixed natively.

### B. Configuration / PyProject (`pyproject.toml`) [DONE]
[MODIFY] `pyproject.toml`
- Added `orjson>=3.9.0` to the root `dependencies = [...]` block. This fulfills the requirement for massive performance boosts across SpecWeaver's internal serialization tasks natively.

### C. Global Universal Orjson Sweep [DONE]
[MODIFY] `src/specweaver/...` (All 29 locations)
- Because `orjson` is now a core dependency, we must not mix standards. We performed a universal codebase sweep replacing `import json` with the `specweaver.commons.json` facade everywhere.

> [!WARNING]
> **ORJSON DECODE TRAP:** Standard `json.dumps()` returns `str`. Fast `orjson.dumps()` natively returns `bytes`. The implementing agent explicitly utilized the facade `commons.json` which appends `.decode('utf-8')` to any payload passed into LLM prompt builders, Pydantic initializers, or logging frameworks, successfully proving zero crashes.

### D. OS Protection (`src/specweaver/workspace/project/git.py` or `.gitignore` injection hook) [DONE]
[MODIFY/NEW] `src/specweaver/assurance/graph/hasher.py`
- Exposes `_ensure_gitignore(project_root: Path)`. Walk up from `project_root` until finding a `.git/` directory. If found, safely append `\n/.specweaver/\n` inside a tracked `# SpecWeaver Auto-Generated` comment block to ensure NFR-2 repository purity. Silently ignore if no `.git` is found.

## 3. Resolving HITL Decisions (Phase 4 Audit)
1. **Schema Parsing via `orjson`**: We will explicitly utilize `orjson.dumps()` and `orjson.loads()` for lightning-fast graph serialization, easily achieving the `< 50ms` NFR constraint natively.
2. **Orphan Key Pruning**: The Hasher will explicitly receive the active list of valid manifests directly from `TopologyGraph.from_project()`. During cache compilation, the hasher will intersect valid keys, instantly pruning orphaned/deleted OS files.
3. **`.gitignore` Climbing**: Implemented exactly via hierarchical path-climbing.

## 4. Verification Constraints
- **Test Matrix (`tests/unit/assurance/graph/test_hasher.py`)**:
  - Test exact 50ms limits (via `timeit` bounds) using a synthetic 1,000-module dummy graph.
  - Test the `.gitignore` climber natively inside `.tmp` nested dummy trees.
  - Test orphan key pruning safely (adding/removing dummy modules).
