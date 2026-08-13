# TECH-002: BaseTool Registry Refactoring

> **Correction (2026-08-01)**: this is the original problem-statement proposal that motivated
> TECH-002. Section 1 below describes the metaclass auto-registration problem in the present tense,
> as if it existed in shipped code — it did not. `BaseTool` never had `__init_subclass__`
> auto-registration; TECH-001 only ever considered and rejected the idea (see `TECH-002_design.md`
> Research Findings) before TECH-002 built the explicit `ToolRegistry` from scratch. Kept as the
> historical record of the initial idea; do not read Section 1 as a description of code that ever
> ran.

## 1. Description
During the execution of **TECH-001 (Monolith Purge)**, we migrated `core/loom` into the `sandbox/`
domain-driven hexagonal architecture. During that design, a metaclass-based auto-registration
approach for `BaseTool` was considered — subclasses would automatically register themselves globally
upon import — but it was rejected before implementation (see `TECH-002_design.md` Research Findings)
because global import-time auto-registration would prevent true isolation of the domains.

This prevents the Validation layer from dynamically importing specific tools for dependency tracking
or schema analysis without accidentally triggering the registration of all other tools that happen
to be imported in the same execution context. This forced us to compromise on `context.yaml`
boundaries, specifically granting exceptions (like `forbids: "!sandbox.qa_runner"`) to bypass strict
DI constraints.

## 2. Business Value
*   **Security:** Removing global state prevents accidental tool exposure or cross-domain contamination in the LLM router.
*   **Maintainability:** Allows true Dependency Injection for the tool registry, enabling easier unit testing without cross-contamination.
*   **Architecture:** Enables strict 100% enforcement of `context.yaml` `forbids` rules without requiring exceptions for validation layers.

## 3. Proposed Solution
1. ~~Remove the automatic `__init_subclass__` metaclass registration in `BaseTool`.~~ Not applicable — never implemented, so nothing to remove.
2. Implement an explicit `ToolRegistry` dependency that must be injected into the dispatcher or flow engines.
3. Update all domains (`git`, `filesystem`, `qa_runner`, `mcp`, `protocol`, `web`, `code_structure`)
   to explicitly register their facades via a factory or module-level exported list (e.g.,
   `get_domain_tools()`).
4. Remove the `!sandbox.*` boundary exceptions in `context.yaml` files.

## 4. Risks & Dependencies
*   **Dependencies:** Must be completed before any multi-agent/multi-tenant features, as global tool registration will cause cross-tenant tool bleeding.
*   **Risks:** Modifying `BaseTool` will break every single tool in the ecosystem. Requires a full AST refactoring script and a massive test suite update.
