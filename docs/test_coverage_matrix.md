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
| `DependencyHasher.load_cache()` | ✅ | ✅ | ✅ |
| `DependencyHasher.save_cache()` | ✅ | ✅ | ✅ |
| `DependencyHasher.compute_hashes()` | ✅ | ✅ | ✅ |

## `src/specweaver/assurance/graph/topology.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `TopologyGraph.from_project()` | ✅ | ✅ | ✅ |
| `TopologyGraph._calculate_stale_seeds()` | ✅ | ✅ | ✅ |
| `TopologyGraph.stale_nodes` | ✅ | ✅ | ✅ |

## `src/specweaver/infrastructure/llm/_skeleton.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `extract_ast_skeleton()` | ✅ | — | — |

## `src/specweaver/infrastructure/llm/prompt_builder.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `PromptBuilder.add_file()` | ✅ | — | — |
| `PromptBuilder.add_mentioned_files()` | ✅ | — | — |
