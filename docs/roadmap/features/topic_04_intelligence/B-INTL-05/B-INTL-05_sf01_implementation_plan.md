# B-INTL-05 SF-01 — Plugin Schema Composition & Targeted AST Search

**Feature ID**: 3.30a · **FRs owned**: FR-1, FR-2 · **Depends on**: none · Design:
[B-INTL-05_design.md](B-INTL-05_design.md) §Sub-features → SF-01

## Goal

Resolve framework plugins alongside archetypes, and expose `decorator_filter` routing to black-box
agent tools.

Follows existing conventions; no new external dependencies. A separate `resolve_plugins` method on
`ArchetypeResolver` keeps `resolve()` backward compatible. Open questions: none — the filter works
like the existing `visibility` filter, with no side effects.

## Changes

1. **[x] `src/specweaver/core/config/archetype_resolver.py`** — a second cache and lookup for
   `plugins` arrays in `context.yaml`:
   - `_plugin_cache: dict[Path, list[str]]`
   - `def resolve_plugins(self, target_path: Path) -> list[str]:` walks up the tree exactly like
     `resolve()`, but parses `data.get("plugins", [])` instead of `archetype`.
2. **[x] `src/specweaver/core/loom/atoms/code_structure/atom.py`** — inject `plugins`, so
   `evaluator_schemas` aggregate from several files instead of one monolith:
   - `__init__` accepts `plugins: list[str] | None = None`.
   - `_get_active_schemas(self)` (or the equivalent schema-resolving step) maps over
     `[self._active_archetype] + (self._plugins or [])` when merging Evaluators.
   - Pass `decorator_filter` from the tool context into
     `parser.list_symbols(code, visibility=visibility, decorator_filter=decorator_filter)`.
3. **[x] `src/specweaver/core/loom/dispatcher.py`** — connect `ArchetypeResolver` to atom
   construction. In `_build_tool_executor` (or `from_boundary`, depending on branch), fetch
   `resolved_plugins = resolver.resolve_plugins(...)` and pass `plugins=resolved_plugins` to
   `CodeStructureAtom`.
4. **`src/specweaver/core/loom/tools/code_structure/definitions.py`** — in `LIST_SYMBOLS_SCHEMA`,
   add `decorator_filter` as an optional string. Description:
   `"Optionally filter symbols to only return those possessing a specific framework decorator/annotation (e.g., 'PreAuthorize', 'RestController')."`
5. **`src/specweaver/core/loom/tools/code_structure/tool.py`** — no routing change (`**kwargs`
   passes context to the atom), but extract `decorator_filter` explicitly from
   `payload.get("decorator_filter")` into `context["decorator_filter"]`.
6. **`src/specweaver/core/loom/commons/language/interfaces.py`** — add
   `decorator_filter: str | None = None` to the `CodeStructureInterface.list_symbols()` protocol
   signature.
7. **`java/codestructure.py`, `kotlin/codestructure.py`, `python/codestructure.py`,
   `typescript/codestructure.py`, `rust/codestructure.py`** — in each `list_symbols()`, before
   yielding a symbol: if `decorator_filter` is truthy, inspect `self.extract_framework_markers()` on
   the `node`, take its `decorator` array, and drop the symbol unless `decorator_filter` is a
   substring of one of those decorators.

## Tests

| Where | Proves |
|---|---|
| `test_archetype_resolver.py` | `plugins: ['spring-security']` bubbles up from project hierarchies |
| integration suite, polyglot `list_symbols` under `tests/` | filtering isolates `@PreAuthorize`-style mock blocks |
