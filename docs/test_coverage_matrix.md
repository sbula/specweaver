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

## `src/specweaver/core/flow/engine/runner.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `PipelineRunner._verify_vault_security()` | ✅ | — | — |
| `PipelineRunner.resume()` | ✅ | ✅ | ✅ |
| `PipelineRunner.run()` | ✅ | ✅ | ✅ |

## `src/specweaver/core/loom/commons/mcp/executor.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `MCPExecutor.__init__()` | ✅ | ✅ | ❌ |
| `MCPExecutor._read_loop()` | ✅ | ✅ | ❌ |
| `MCPExecutor.close()` | ✅ | ✅ | ❌ |
| `MCPExecutor.is_alive()` | ✅ | ✅ | ❌ |
| `MCPExecutor.call_rpc()` | ✅ | ✅ | ❌ |

## `src/specweaver/core/loom/atoms/mcp/atom.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `MCPAtom._ensure_started()` | ✅ | ❌ | ❌ |
| `MCPAtom.run()` | ✅ | ❌ | ❌ |
| `MCPAtom.close()` | ✅ | ❌ | ❌ |
| `MCPAtom._intent_initialize()` | ✅ | ❌ | ❌ |
| `MCPAtom._intent_read_resource()` | ✅ | ❌ | ❌ |

## `src/specweaver/core/loom/atoms/git/atom.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `GitAtom._intent_is_tracked()` | ✅ | — | — |
| `GitAtom._intent_worktree_teardown()` | ✅ | — | — |
| `GitAtom._intent_strip_merge()` | ✅ | — | — |

## `src/specweaver/infrastructure/llm/_skeleton.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `extract_ast_skeleton()` | ✅ | — | — |

## `src/specweaver/infrastructure/llm/prompt_builder.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `PromptBuilder.add_file()` | ✅ | — | — |
| `PromptBuilder.add_mentioned_files()` | ✅ | — | — |

## `src/specweaver/workspace/parsers/exclusions.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| SpecWeaverIgnoreParser.ensure_scaffolded() | ✅ | ✅ | ✅ |
| SpecWeaverIgnoreParser.get_compiled_spec() | ✅ | ✅ | ✅ |

## `src/specweaver/workspace/parsers/interfaces.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| CodeStructureInterface.get_binary_ignore_patterns() | ✅ | — | — |
| CodeStructureInterface.get_default_directory_ignores() | ✅ | — | — |

## `src/specweaver/workspace/parsers/base.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `BaseTreeSitterParser` | ✅ | ✅ | ✅ |


## `src/specweaver/workspace/parsers/markdown/codestructure.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `SCM_*_QUERY` | — | ✅ | ✅ |
| `add_symbol()` | — | ✅ | ✅ |
| `_is_symbol_valid()` | — | ✅ | — |
| `_find_symbol_node()` | — | ✅ | — |
| `_find_target_block()` | — | ✅ | — |
| `_format_replacement()` | — | ✅ | — |
| `_format_body_injection()` | — | ✅ | — |
| `extract_framework_markers()` | — | ✅ | — |
| `extract_traceability_tags()` | ✅ | ✅ | — |
| `get_binary_ignore_patterns()` | ✅ | ✅ | — |
| `get_default_directory_ignores()` | ✅ | ✅ | — |

## `src/specweaver/workspace/analyzers/factory.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `get_test_file_pattern()` | ✅ | — | — |
| `extract_test_mapped_requirements()` | ✅ | ✅ | — |

## `src/specweaver/assurance/validation/rules/code/c09_traceability.py`
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| `_find_and_parse_tests()` | ✅ | ✅ | ✅ |


## src/specweaver/core/flow/handlers/mcp_assembler.py
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| evaluate_and_fetch_mcp_context() | ✅ | ✅ | ✅ |

## src/specweaver/core/flow/handlers/review.py
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| ReviewSpecHandler | ✅ | ⚪ | ✅ |
| ReviewCodeHandler | ✅ | ⚪ | ✅ |


## src/specweaver/core/loom/tools/mcp/tool.py & interfaces.py
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| _execute_mcp_query() | ✅ | ❌ | ❌ |
| ArchitectMCPInterface | ✅ | ❌ | ❌ |

## src/specweaver/core/loom/dispatcher.py
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| create_standard_set() | ✅ | ✅ | ✅ |

## src/specweaver/workspace/project/scaffold.py
| Class / Function | Unit | Integration | E2E |
|------------------|------|-------------|-----|
| _scaffold_context_yaml() | ✅ | ✅ | ✅ |
| scaffold_project() | ✅ | ✅ | ✅ |

