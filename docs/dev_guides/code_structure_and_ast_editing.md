# Developer Guide: Code Structure & AST Surgical Editing

This guide details SpecWeaver's native mechanisms for parsing, reading, and mutating source code seamlessly using Abstract Syntax Trees (AST). Built on top of Tree-sitter, this polyglot feature eliminates the fragile nature of line-number replacement and LLM regex patching.

---

## 1. The Core Problem: Context Bloat & "Lost in the Middle"

When autonomous agents process massive files (e.g., a 2,000-line `GodClass.java`), they traditionally rely on `cat` or `read_file`. This presents two catastrophic issues:
1. **Context Window Bloat**: Absorbing millions of tokens costs money and degrades inference speed.
2. **Prompt Forgetting (Lost in the Middle)**: Passing a massive string to fix a tiny bug causes the LLM to hallucinate during generation, often inadvertently reverting undocumented decorators or forgetting the overall architecture.

SpecWeaver's solution relies on the `CodeStructureTool`, delegating structural parsing cleanly into our `Flow Engine`. By slicing out "AST Skeletons", we can feed the Agent exact code maps, preventing token waste while permitting localized, surgical injections.

---

## 2. The 9 Agentic Action Intents

SpecWeaver formally injects nine `ToolDefinitions` into the Agent's runtime prompt via the `CodeStructureTool`. These decouple reading logic into two distinct branches: **Investigation** (Read) and **Surgical Mutation** (Write).

### A. Investigation (Read) Intents

*   **`read_file_structure`**
    *   **Goal**: Find out what a massive file does without reading its inner logic.
    *   **Behavior**: Slices out the execution body of every class and function natively, leaving only framework decorators, import lists, signatures, and docstrings.
    
*   **`list_symbols`**
    *   **Goal**: Return a flattened array of all targetable symbols.
    *   **Behavior**: Optionally uses `visibility` or `decorator_filter` parameters (such as `'public'` or `'RestController'`) to return exact topological matches without dumping their bodies. **Note:** Returns symbols strictly in Dot-Notation (e.g., `['Database', 'Database.connect']`) to prevent scope ambiguity.
    
*   **`read_symbol`**
    *   **Goal**: Pinpoint a precise code block inside a large file.
    *   **Behavior**: Extracts the full logic block of a specified symbol (including its decorators, signature, and `{...}` block).

*   **`read_symbol_body`**
    *   **Goal**: Inspect isolated iteration loops without distraction.
    *   **Behavior**: Returns *only* the internal `{ ... }` curly brace execution block of a symbol, completely omitting its decorators and original signature.

*   **`read_unrolled_symbol`**
    *   **Goal**: Expose implicit compiler-plugin magic to the LLM.
    *   **Behavior**: Intercepts the source code block and mechanically prefixes it with a commented explanation translating its macros/annotations directly into runtime behaviors using our `SchemaEvaluator` (e.g. unrolling Rust procedural macros or Java Spring Boot annotations).

### B. Surgical Mutation (Write) Intents

When it comes time to edit files, Agents are strictly guided to prefer semantic injection over raw string modification.

*   **`replace_symbol_body`** *(The Safest Editor)*
    *   **Goal**: Update a function's iteration logic without damaging Spring/Django decorators.
    *   **Behavior**: Overwrites *only* the inner `{...}` or indented `def:` body block. The original AST signatures and decorators are permanently locked, protecting them from LLM syntax hallucinations.
    
*   **`replace_symbol`**
    *   **Goal**: Update the entire target wrapper.
    *   **Behavior**: Obliterates the AST boundary (decorators, signature, AND body) and injects the new token stream directly into the gap.

*   **`add_symbol`**
    *   **Goal**: Cleanly attach a new function.
    *   **Behavior**: Injects a fresh AST symbol snippet into a specific `target_parent` (like an interface or class), or appends it natively to the bottom of the module hierarchy if omitted.

*   **`delete_symbol`**
    *   **Goal**: Rip out architectural rot organically.
    *   **Behavior**: Finds the target class or function and completely erases its byte bounds from the physical file, removing stray blank lines securely.

---

## 3. Strict Dot-Notation Symbol Resolution

A core architectural principle of SpecWeaver's polyglot ecosystem is the mandatory use of **Dot-Notation** for symbol resolution across all languages (Python, Java, Kotlin, C++, Rust, Go, JavaScript, TypeScript, Markdown, etc.). 

When an agent requests a symbol mutation or extraction, it MUST supply the fully qualified scope path (e.g., `Class.Method` instead of just `Method`). 

**Why?**
1. **Ambiguity Prevention**: Classes and trait implementations often share common method names like `run`, `execute`, or `start`. Passing just `"run"` causes the parser to either crash or accidentally replace the first matched implementation it finds in the file.
2. **Predictable Extraction**: The `list_symbols` command guarantees it returns the fully-qualified dot-notation paths. Agents should always run `list_symbols` first, copy the exact string returned (e.g., `"Engine.run"`), and pass it verbatim into the mutation/extraction intent.

---

## 4. Dynamic Capability Filtering

Not all programming languages support every AST operation due to parser constraints or language syntax definitions (e.g., Markdown doesn't have "imports" and Rust might not safely support generic body replacing without breaking lifetimes). 

SpecWeaver implements **Dynamic Capability Filtering**. Each language parser explicitly overrides `supported_intents()` and `supported_parameters()` to communicate its limitations natively to the `CodeStructureTool`. 

When an Agent mounts a tool for a specific file type, the Tool Definition Schema is dynamically pruned in the LLM's prompt. If a parser does not support `replace_symbol_body`, the LLM will simply never see that option in its tool schema for that specific file. This prevents hallucinated tool calls and improves pipeline stability.

---

## 5. How It Works Under The Hood

If you are expanding the engine's functionality, here is the operational flow logic of the AST tool layer:

1. **Untrusted LLM Output**: The Agent emits a JSON intent (e.g., `replace_symbol_body("src/Backend.ts", "calculateHash", "...")`).
2. **`CodeStructureTool` Validation**: The Tool bounds-checks the request against the Role `FolderGrant` and target `visibility`.
4. **Tree-Sitter Orchestration (Dependency Injection)**: To maintain architectural purity, `CodeStructureAtom` does *not* directly instantiate polyglot C-binaries. Instead, standard `specweaver.workspace.parsers` interfaces are retrieved from `RunContext` (in tools like the CLI and Engine pipeline) and explicitly passed down the injection boundary.
5. **Physical Mutation**: Using the byte offsets provided by the AST Nodes executed via the injected polyglot wrappers, the Atom surgically patches the original string and persists the mutation safely to the disk.

If you ever wish to add a new AST mutation intent, it must follow this 5-step validation hierarchy, with all C-based binary querying confined strictly to `workspace/parsers/` and explicit DI chaining mapped all the way down into the Atom orchestrator boundaries.

---

## 6. Best Practices for Tool Development

- **Never rely on String Replacement:** LLM Agents fail to count spaces and indentations. Always prefer native byte offsets supplied by `tree-sitter`.
- **Enforce Separation of Reads and Writes:** Do not allow `read_file_structure` to mutate bounds or log warnings to the console. Pure function responses ensure maximum context integrity.
- **Fail Gracefully on Parse Errors:** If Tree-sitter fails to index a file due to severe syntax drift, gracefully fall back to instructing the LLM to use `read_file` instead of crashing the pipeline stack.


## Context Skeletonization

Due to architectural latency bounds (NFR-1) and isolation layers, extracting AST skeletons from background and dependency files during prompt hydration is prohibited. Attempting to statically import \CodeStructureAtom\ or tree-sitter bindings within \PromptBuilder\ constitutes an architectural violation.

Instead, the **ContextAssembler** pre-fetches AST skeleton string states asynchronously during the L3 bootstrap using \evaluate_and_fetch_skeleton_context()\ inside the Flow Handlers layer. The resulting dictionary mapping is directly injected into the \PromptBuilder\ kwargs during downstream Workflow initiation, enabling token-aware context without C-binding blocking or cross-layer cyclic dependencies.
