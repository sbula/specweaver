# TECH-01b: BaseTool Metaclass Registry Refactoring

## 1. Description
During the execution of **TECH-01 (Monolith Purge)**, we migrated `core/loom` into the `sandbox/` domain-driven hexagonal architecture. However, we discovered a deep architectural constraint preventing true isolation of the domains: the `BaseTool` metaclass automatically registers all subclasses globally upon import.

This prevents the Validation layer from dynamically importing specific tools for dependency tracking or schema analysis without accidentally triggering the registration of all other tools that happen to be imported in the same execution context. This forced us to compromise on `context.yaml` boundaries, specifically granting exceptions (like `forbids: "!sandbox.qa_runner"`) to bypass strict DI constraints.

## 2. Business Value
*   **Security:** Removing global state prevents accidental tool exposure or cross-domain contamination in the LLM router.
*   **Maintainability:** Allows true Dependency Injection for the tool registry, enabling easier unit testing without cross-contamination.
*   **Architecture:** Enables strict 100% enforcement of `context.yaml` `forbids` rules without requiring exceptions for validation layers.

## 3. Proposed Solution
1. Remove the automatic `__init_subclass__` metaclass registration in `BaseTool`.
2. Implement an explicit `ToolRegistry` dependency that must be injected into the dispatcher or flow engines.
3. Update all domains (`git`, `filesystem`, `qa_runner`, `mcp`, `protocol`, `web`, `code_structure`) to explicitly register their facades via a factory or module-level exported list (e.g., `get_domain_tools()`).
4. Remove the `!sandbox.*` boundary exceptions in `context.yaml` files.

## 4. Risks & Dependencies
*   **Dependencies:** Must be completed before any multi-agent/multi-tenant features, as global tool registration will cause cross-tenant tool bleeding.
*   **Risks:** Modifying `BaseTool` will break every single tool in the ecosystem. Requires a full AST refactoring script and a massive test suite update.
