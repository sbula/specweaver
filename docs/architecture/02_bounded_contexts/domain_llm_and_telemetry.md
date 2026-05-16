# LLM Adapter Registry & Dispatch

## LLM Adapter Registry

The system employs a multi-provider auto-discovery registry for its underlying LLM backends (introduced in Feature 3.12a).

- **Auto-Discovery**: Any new file added to `src/specweaver/llm/adapters/` that defines an `LLMAdapter` subclass with a `provider_name` is automatically discovered at runtime by the `registry.py` module. No hardcoded imports or central dictionary registrations are needed, and the folder functions as a PEP 420 Implicit Namespace Package.
- **Supported Providers**: Natively supports `gemini`, `openai`, `anthropic`, `mistral`, and `qwen`.
- **Factory Encapsulation**: `src/specweaver/llm/factory.py` reads the project's linked database profile to instantiate the configured adapter dynamically. If no provider is explicitly set, the factory cleanly falls back to `gemini`.
- **Telemetry Transparency**: The factory automatically wraps any instantiated adapter inside a `TelemetryCollector` proxy to provide unified token usage, cost tracking, and streaming telemetry, totally invisible to the underlying adapter logic.
- **Cost Aggregation**: The registry dynamically aggregates `default_costs` mappings from all discovered adapters into a unified tier-sheet, ensuring new providers automatically inject their pricing rules without central hardcoding.

## LLM Function-Calling Dispatch

When the LLM uses native function calling (e.g., Gemini `FunctionDeclaration`), a
**dispatcher** maps `(name, args)` pairs from the LLM response to tool implementations.

```text
GeminiAdapter.generate_with_tools(messages, config, dispatcher)
    ← LLM returns: FunctionCall(name="grep", args={...})
    → dispatcher.execute("grep", args)
        → FileSystemTool.grep(...)
```

### Where the dispatcher lives

The dispatcher consumes tools — so it CANNOT live in `commons/` (which forbids
`tools/*`). It belongs at the **`sandbox/` root level** (e.g., `sandbox/dispatch.py`)
because `sandbox/` is the only layer that can consume all three sub-layers.

### Who calls the dispatcher

The dispatcher is consumed by `review/`, `planning/`, and `flow/` through the
`_build_tool_executor()` factory in `flow/_review.py`.

> [!WARNING]
> **Current violation:** `review/` and `planning/` both `forbid: sandbox/*` in
> their `context.yaml`, yet they import `ToolExecutor` from
> `sandbox/research/executor.py`. This is a boundary violation that
> needs to be resolved.

### Each tool owns its own definitions

Tool definitions (`ToolDefinition` from `llm/models.py`) should live with their
respective tools in `sandbox/{domain}/`, NOT centralized in a separate module.
