# Implementation Plan: 3.30a SF-1 (Plugin Schema Composition & Targeted AST Search)

This implementation plan details the steps required to resolve Framework Plugins dynamically alongside Archetypes in SpecWeaver, and to expose `decorator_filter` routing to Black-Box Agent tools.

## User Review Required

> [!IMPORTANT]  
> All architectural patterns align with previous conventions. No new external dependencies are required. A `resolve_plugins` isolated method will be added to `ArchetypeResolver` to retain backward API compatibility for `resolve()`.

## Proposed Changes

### `specweaver/core/config`

#### [x] [MODIFY] [archetype_resolver.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/config/archetype_resolver.py)
- **Concept:** Expose a secondary cache and lookup method to fetch `plugins` arrays from `context.yaml`.
- **Implementation:**
  - Add `_plugin_cache: dict[Path, list[str]]`.
  - Add `def resolve_plugins(self, target_path: Path) -> list[str]:` which traces up the tree exactly like `resolve()` but parses `data.get("plugins", [])` instead of `archetype`.

---
### `specweaver/core/loom/atoms/code_structure`

#### [x] [MODIFY] [atom.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/atoms/code_structure/atom.py)
- **Concept:** Inject `plugins` natively so `evaluator_schemas` can be logically aggregated from multiple files without a single-monolith bottleneck.
- **Implementation:**
  - Modify `__init__` to accept `plugins: list[str] | None = None`.
  - Update `_get_active_schemas(self)` (or equivalent schema resolving abstraction) to map over `[self._active_archetype] + (self._plugins or [])` when calculating merged Evaluators.
  - Plumb `decorator_filter` from the tool context into `parser.list_symbols(code, visibility=visibility, decorator_filter=decorator_filter)`.

---
### `specweaver/core/loom`

#### [x] [MODIFY] [dispatcher.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/dispatcher.py)
- **Concept:** Connect the `ArchetypeResolver` directly into `atom` initialization.
- **Implementation:**
  - Inside `_build_tool_executor` (or `from_boundary` depending on branch), fetch `resolved_plugins = resolver.resolve_plugins(...)`.
  - Pass `plugins=resolved_plugins` into the `CodeStructureAtom` construction block.

---
### `specweaver/core/loom/tools/code_structure`

#### [MODIFY] [definitions.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/tools/code_structure/definitions.py)
- **Concept:** Expose `decorator_filter` cleanly inside the JSON Schema Tool definitions sent to the LLM agent.
- **Implementation:**
  - In `LIST_SYMBOLS_SCHEMA`, add `decorator_filter` as an optional string. Description: `"Optionally filter symbols to only return those possessing a specific framework decorator/annotation (e.g., 'PreAuthorize', 'RestController')."`

#### [MODIFY] [tool.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/tools/code_structure/tool.py)
- **Implementation:** No direct routing structural change needed as `**kwargs` passes context through to the atom cleanly, though we will explicitly ensure `decorator_filter` is extracted natively from `payload.get("decorator_filter")` and mapped to `context["decorator_filter"]`.

---
### `specweaver/core/loom/commons/language`

#### [MODIFY] [interfaces.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/interfaces.py)
- **Concept:** Support `decorator_filter` natively.
- **Implementation:** Add `decorator_filter: str | None = None` to the `CodeStructureInterface.list_symbols()` protocol signature.

#### [MODIFY] `java/codestructure.py`, `kotlin/codestructure.py`, `python/codestructure.py`, `typescript/codestructure.py`, `rust/codestructure.py`
- **Concept:** Apply the filter to the physical extraction.
- **Implementation:**
  - Inside each `list_symbols()` implementation: Before yielding the resulting symbol payload, if `decorator_filter` is truthy, inspect `self.extract_framework_markers()` on the targeted `node`. Look for the array of `decorator` components. If `decorator_filter` string is not found via substring match in those decorators, completely discard the symbol from the returned array.

## Open Questions

None. The mathematical logic mirrors exactly how `visibility` targeting is currently natively filtered, yielding zero side-effects.

## Verification Plan

### Automated Tests
- Explicitly trace unit testing in `test_archetype_resolver.py` assuring `plugins: ['spring-security']` natively bubbles up from physical project hierarchies.
- Run `tests/` specifically the integration suite targeting polyglot `list_symbols` natively enforcing matching isolation on `@PreAuthorize` style mock blocks.
