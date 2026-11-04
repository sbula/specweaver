# Layer Isolation and Dependency Injection

Use when: a pure-logic layer (like `validation/` or `standards/`) seems to need a file read, an AST
parse, or a subprocess.

SpecWeaver separates **Pure Logic** (deterministic rules) from **Side-Effects** (I/O, Subprocesses,
C-bindings) without circular dependencies. A pure-logic layer importing an OS or `tree-sitter`
module directly **is an architectural violation**.

## The sandbox serves the engine too

The sandbox (`Loom` in older docs) is not only the "LLM DMZ" where agents are confined through
`Tools`. It is also **the Side-Effect Sandbox for the whole SpecWeaver Engine.**

| Layer | Archetype | May |
|---|---|---|
| Pure logic (`validation`; `graph` in older docs, whose `context.yaml` now allows `specweaver.sandbox`) | `archetype: pure-logic`, `forbid: sandbox/*` | Nothing that touches disk, network or external C-bindings |
| Loom Atoms (`sandbox/`) | trusted I/O executors | Read files, run `pytest`, execute `tree-sitter` |

## Inversion of Control

`validation/drift_detector.py` compares an AST against a Plan but cannot parse the AST (I/O and
C-binaries). The `flow` engine, which connects the sandbox and validation, injects it:

1. `flow` calls `FileSystemAtom` (sandbox) to read the raw file string.
2. `flow` passes the string to the `AstAtom` (sandbox), which runs the `tree-sitter` parser and
   returns an `ASTNode` object.
3. `flow` passes the memory-safe `ASTNode` into `drift_detector` (`Validation`).

```text
Flow Engine (Orchestrator)
  ├── 1. Calls AstAtom.parse(file_path) ──────▶ Returns ASTNode
  └── 2. Calls drift_detector.detect(ASTNode) ─▶ Returns DriftReport
```

Note (2026-09-25): today the parsing atom is `CodeStructureAtom` and the entry point is
`detect_drift`.

**Rule:** pure-logic layers NEVER parse their own data. They define Protocols or accept `Any` typed
payloads and expect upstream Orchestrators to inject the parsed context.

## The flow engine knows no handler

`core/flow` is three tach modules. `handlers` uses `engine`; `engine` never imports `handlers`.
What both need lives in `core/flow/run_state`: `RunContext`, `log_step_failure`, `target_dal`,
`scenario_store`, `registered`. `run_state` imports neither of the other two.

The engine reaches a handler only through what its caller hands it:

- `PipelineRunner(..., registry=StepHandlerRegistry())`: every caller passes the registry. The
  engine types it as `HandlerLookup` (`engine/handler_port.py`), a port it owns.
- The draft steps get their drafters from the run: `build_run` sets `context.model.drafters` to
  `WorkflowDrafters` (`interfaces/run_setup/drafters.py`). The handlers import no drafting code.

A new handler that needs a workflow gets it the same way: the builder injects it, the handler reads
it from the context.

## A handler is a shell

A handler gathers inputs from the run, calls a workflow with plain values (the model adapter, its
config, text, paths), and writes the result back. The workflow never sees `RunContext` and never
imports `core/flow`. Examples: `repair_lint` (`workflows/implementation`), `arbitrate`
(`workflows/arbitration`), `explain_drift` (`assurance/validation/orchestration`).

No handler calls a model adapter's `generate` or `generate_with_tools` itself, and none hides its
complexity behind a `noqa`; `tests/unit/core/flow/handlers/test_no_handler_calls_a_model.py`
checks both.

## Where language code goes

Execution and structural analysis live in separate layers. For a new language (e.g. Go, C++):

- Do NOT put it in `standards/languages/` just because `standards` uses it later.
- Do NOT create a top-level `src/specweaver/languages/`: it would mix Pure Logic with I/O.

| Layer | Holds | Why there |
|---|---|---|
| Language Commons (`sandbox/language/`) | `runner.py`: subprocess test I/O (e.g. `cargo test`, `pytest`) | execution is a side-effect |
| Workspace Parsers (`workspace/ast/parsers/`) | `codestructure.py`: framework syntax parsing (e.g. `.scm` queries fed into tree-sitter C-binaries) | pure-logic rules and Context Engines consume ASTs but cannot parse safely |

`Loom Atoms` and validation controllers reach these layers through Dependency Injection factories.

## PromptBuilder context injection

`PromptBuilder` (src/specweaver/infrastructure/llm/prompt_builder.py) may not resolve file system
hierarchies or invoke Atoms. The Engine layer injects parsed context (e.g. target mentions,
skeletonization). Example: the **ContextAssembler** pre-condenses CodeStructureAtom skeletons and
passes them as `PromptBuilder(skeleton_files=...)`.
