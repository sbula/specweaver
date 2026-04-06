# Developer Guide: Layer Isolation & Dependency Injection

This guide explains how SpecWeaver maintains strict separation between **Pure Logic** (mathematical, deterministic rules) and **Side-Effects** (I/O, Subprocesses, C-bindings) without creating circular dependencies.

A common misunderstanding when building new features is assuming that if a Pure Logic layer (like `validation/` or `standards/`) needs to read a file or parse an AST, it should import an OS or `tree-sitter` module directly. **This is an architectural violation.**

---

## 1. The Loom Sandbox is for the Engine, Not Just the Agent

`Loom` is often thought of as the "LLM DMZ"—the place where we lock the agent in a sandbox using `Tools`. 

But `Loom` has a second, equally important purpose: **It is the centralized Side-Effect Sandbox for the entire SpecWeaver Engine.**

- **Pure Logic Layers** (`validation`, `graph`): Are explicitly classified as `archetype: pure-logic`. They are mathematically forbidden from importing anything that touches the disk, network, or external C-bindings. They `forbid: loom/*`.
- **Loom Atoms** (`loom/atoms/`): Are unrestricted, trusted I/O executors. They are allowed to read files, run `pytest`, and execute `tree-sitter`.

## 2. Inversion of Control (Dependency Injection)

If `validation/drift_detector.py` needs to mathematically compare an AST against a Plan, but it cannot parse the AST itself (because parsing requires I/O and C-binaries), how does it get the AST?

**Through Dependency Injection coordinated by the Flow Engine.**

The `flow` module acts as the orchestrator connecting `Loom` and `Validation`:
1. The `flow` engine calls `FileSystemAtom` (in Loom) to read the raw file string.
2. The `flow` engine passes that string to the `AstAtom` (in Loom) to execute the `tree-sitter` parser and return an `ASTNode` object.
3. The `flow` engine passes the memory-safe `ASTNode` object down into `drift_detector` (in Validation).

```text
Flow Engine (Orchestrator)
  ├── 1. Calls AstAtom.parse(file_path) ──────▶ Returns ASTNode
  └── 2. Calls drift_detector.detect(ASTNode) ─▶ Returns DriftReport
```

**Rule:** Pure logic layers must NEVER parse their own data. They must define Protocols or accept `Any` typed payloads, expecting upstream Orchestrators to inject the parsed context.

## 3. The Language Commons (`loom/commons/language/`)

Because all language-specific execution (Running Tests, Parsing AST Skeletons) requires side-effects, **all language specifics MUST live strictly inside the Loom layer.**

If you are adding a new language (e.g., Go, C++):
- Do NOT put it in `standards/languages/` just because `standards` uses it later.
- Do NOT create a top-level `src/specweaver/languages/` because it would mix Pure Logic with I/O.

All language mechanics live in `src/specweaver/loom/commons/language/<name>/`:
* `runner.py`: Handles subprocess I/O (e.g., `cargo test`).
* `ast_parser.py`: Handles external framework I/O (e.g., `.scm` queries fed into tree-sitter C-binaries).

The `Loom Atoms` and `Loom Tools` simply wrap this unified language commons, ensuring the rest of SpecWeaver remains beautifully pure and highly testable.
