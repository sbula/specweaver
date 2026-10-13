# Code Structure & AST Editing

Use when: you add or change an agent code-reading/editing intent, a language parser, or the context
skeletons fed to prompts.

Agents read and edit code through tree-sitter ASTs, not line numbers or regex patches.
`CodeStructureTool` exposes it to the agent; the flow engine does the parsing.

## Why

An agent reading a 2,000-line `GodClass.java` with `cat` or `read_file` gets:

1. **Context bloat** — huge token cost, slower inference.
2. **Lost in the middle** — asked to fix a small bug inside a huge string, the model drifts: it drops
   decorators or forgets the architecture.

AST skeletons give the agent a map of the code and let it edit one symbol at a time.

## The 9 intents

`CodeStructureTool` puts nine `ToolDefinitions` into the agent's prompt, in two groups.

### Read

| Intent | Returns |
|---|---|
| `read_file_structure` | The file with every class/function body removed: decorators, imports, signatures, docstrings remain |
| `list_symbols` | A flat list of targetable symbols, in dot-notation (e.g. `['Database', 'Database.connect']`) |
| `read_symbol` | One symbol in full: decorators, signature, `{...}` block |
| `read_symbol_body` | Only the code inside the body, at column 0 — no braces, decorators or signature |
| `read_unrolled_symbol` | The symbol, prefixed with a comment explaining what its macros/annotations do at runtime (via `SchemaEvaluator`, e.g. Rust procedural macros, Spring Boot annotations) |

`list_symbols` filters:

- `decorator_filter` — only symbols carrying that annotation.
- `visibility` — any of `public` · `protected` · `internal` · `private` · `unknown`; returns **only**
  those levels, as a comma-separated list (`"public, internal"`). Python: `_name` is internal,
  `__name` private, a dunder public. Purpose: **information hiding** — build against a module's interface so its internals
  can change. It is not a security boundary.

### Write

Prefer the narrowest edit.

| Intent | Does |
|---|---|
| `replace_symbol_body` *(safest)* | Replaces only the code inside the body, at the symbol's own indentation; braces, signature and decorators stay. An unchanged `read_symbol_body` writes back byte for byte |
| `replace_symbol` | Replaces decorators, signature and body |
| `add_symbol` | Inserts a new symbol into `target_parent` (class, interface), or at the end of the module if omitted |
| `delete_symbol` | Removes the class or function's byte range, and stray blank lines |

## Rule: dot-notation symbols

A symbol is named by its scope path in all languages: `Class.Method`. A bare `Method` that only one
class has resolves to it; one that several classes share (`run`, `execute`) is refused, naming each.
`list_symbols` returns full paths, so an agent copies the exact string.

## Rule: a write never breaks a file

A write whose result does not parse, where the file parsed before, is refused and nothing is
written. Every write answers with the file and what it did.

## Rule: capabilities are filtered per language

Not every language supports every operation (Markdown has no imports; Rust body replacement can break
lifetimes). Each parser overrides `supported_intents()` and `supported_parameters()`. When an agent
mounts the tool for a file type, unsupported intents and parameters are removed from the schema it
sees — it cannot call what the parser cannot do.

## How an edit flows

1. **LLM output (untrusted)**: a JSON intent, e.g.
   `replace_symbol_body("src/Backend.ts", "calculateHash", "...")`.
2. **`CodeStructureTool` check**: the request is checked against the role's `FolderGrant` — the
   **path**, and only the path (`interfaces/tool.py`, `_check_grant`, which calls the shared
   `sandbox.security.grant_mode_for`). Paths are relative to the project root. Writes go through
   `FileExecutor`, so `context.yaml`, `.env`, `.git` and `.specweaver` are refused, and a refused
   write comes back as a failure. `visibility` is a relevance
   filter chosen by the caller and passed straight to the parser. Anyone who can read the file can
   read its private symbols; the index is not a permission system (corrected 2026-08-26).
3. **Parsers by injection**: `CodeStructureAtom` never instantiates tree-sitter bindings itself.
   `specweaver.workspace.ast.parsers` implementations come from `RunContext` (CLI, engine pipeline)
   and are passed down.
4. **Mutation**: the atom patches the source at the AST node's byte offsets and writes the file
   (with auto-indent — `special_patterns_and_adaptations.md` §10).

A new mutation intent must follow the same path. All tree-sitter querying stays in
`workspace/ast/parsers/`, with parsers injected all the way down to the atom.

## Rules for tool code

- **No string replacement**: models miscount spaces and indentation. Use tree-sitter byte offsets.
- **Reads never write**: `read_file_structure` must not mutate anything or log warnings to the
  console.
- **Parse failure is not a crash**: if tree-sitter cannot index a file, tell the LLM to use
  `read_file` instead.

## Context skeletonization

Prompt building must not parse files (latency bound NFR-1). Importing `CodeStructureAtom` or
tree-sitter bindings in `PromptBuilder` is an architecture violation.

Instead the **ContextAssembler** (`core/flow/handlers/context_assembler.py`) builds skeletons in the
flow handlers layer: `evaluate_and_fetch_skeleton_context()` runs via `asyncio.to_thread` during the
L3 bootstrap and returns a path → skeleton mapping, which is passed into the `PromptBuilder` kwargs.
No C-binding blocking in the event loop, no cross-layer cycles.
