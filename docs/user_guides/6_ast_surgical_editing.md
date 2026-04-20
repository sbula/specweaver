# User Handbook 6: AST Surgical Editing & Context Management

Traditional AI coding assistants struggle with large enterprise codebases. Attempting to repair a single function in a 2,000-line `.java` or `.ts` file using basic tools like `cat` or string replacement results in two massive failures:
1. **Context Window Bloat:** Passing millions of unnecessary tokens costs massive amounts of compute.
2. **Hallucination & Prompt Forgetting:** Forcing the LLM to process thousands of lines before a tiny fix makes it lose track of the original architecture.

To solve this, **SpecWeaver uses polyglot AST (Abstract Syntax Tree) manipulation.**

## The CodeStructureTool

Instead of viewing files as raw text, SpecWeaver mounts Native Tree-Sitter boundaries across Python, Java, Kotlin, Javascript, Typescript, and Rust. Let's look at how agents surgically interact with your codebase.

### 1. Minimal Reads (Skeletal Mapping)
Instead of executing a full `read_file`, SpecWeaver agents prefer using `read_file_structure`. 
This mechanically slices the file:
- It returns the imports, class topologies, and function signatures.
- It completely hides the internal `{...}` execution paths.

You get a perfectly accurate blueprint of what the file does without paying token costs for details you aren't currently editing.

### 2. Deep Focus (`read_symbol_body`)
If an agent only needs to fix the `calculateHash()` method, it uses `read_symbol`. That extracts just the target method.
Better yet, using `read_symbol_body` extracts only the inside iteration loops, hiding external framework decorators (like Spring Boot annotations) from the agent entirely so it won't get them wrong during reproduction.

### 3. Surgical Splicing (`replace_symbol_body`)
This is SpecWeaver's primary coding advantage. 

When replacing code, the Agent cannot destroy your file with bad spacing or forgotten imports. `replace_symbol_body` locks the outer boundaries of the requested method. 
- The method signature is **frozen**.
- The decorators and macros are **frozen**.
- Only the inner body logic is replaced, mapping the bytes precisely against the AST offsets.

This ensures that the final merged logic is always syntactically clean without the typical "search-and-replace failed" loop that plagues legacy workflows.
