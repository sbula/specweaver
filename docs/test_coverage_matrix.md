# SpecWeaver Test Coverage Matrix

This document acts as a live, explicitly maintained manifest of unit, integration, and E2E test coverage for the SpecWeaver ecosystem.

## `src/specweaver/commons/json.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `dumps()` | ✅ | ✅ | ✅ |
| `loads()` | ✅ | ✅ | ✅ |
| `dump()` | ✅ | ✅ | ✅ |
| `load()` | ✅ | ✅ | ✅ |

*(To be expanded sequentially during subsequent `/pre-commit` workflow generations).*

## `src/specweaver/assurance/graph/hasher.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `_ensure_gitignore()` | ✅ | — | — |
| `DependencyHasher._hash_directory()` | ✅ | — | — |
| `DependencyHasher._hash_file()` | ✅ | — | — |
| `DependencyHasher.load_cache()` | ✅ | ✅ | — |
| `DependencyHasher.save_cache()` | ✅ | ✅ | — |
| `DependencyHasher.compute_hashes()` | ✅ | ✅ | — |
