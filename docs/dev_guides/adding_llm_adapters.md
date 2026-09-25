# Adding an LLM Provider

Use when: you add a new LLM provider (e.g. Cohere, AI21) to SpecWeaver.

Each provider is an adapter found by an auto-discovery registry: no hardcoded provider list, and no
cost tracking inside business logic.

Since moved (2026-09-25): `llm/` is now `src/specweaver/infrastructure/llm/`; discovery lives in
`adapters/registry.py`; the dispatcher is `sandbox/dispatcher.py` (formerly `loom/dispatcher.py`).

## Steps

1. **Write the adapter** at `src/specweaver/llm/adapters/<provider_name>.py`, inheriting the
   `LLMAdapter` abstract class from `llm/adapters/base.py`. It owns its SDK endpoints,
   request/response models, and context-window chunking.
2. **Implement the overrides:**
   1. `generate(prompt: str) -> str`: plain chat completions, no system injection, no tools.
   2. `generate_with_tools(messages, config, dispatcher)`: map the provider's native function-calling
      format (e.g. a JSON schema into Cohere's tool schema) and pipe native payload callbacks to the
      `loom/dispatcher.py`.
   3. `provider_name`: a unique static string identifying the class.
3. **Nothing to register.** The package scans its modules and subclasses at start-up
   (`src/specweaver/llm/adapters/__init__.py`). An adapter with `provider_name = "cohere"` inside
   `adapters/` is supported. _Do not append it to a master array._

## Rules

- **No telemetry in the adapter.** Cost routing, token counting and database lineage are not its
  job; do not intercept payload counts inside generation.

How telemetry is added:

1. The `LLMFactory` (`llm/factory.py`) is asked for an LLM (e.g. "cohere").
2. It instantiates your `CohereAdapter`.
3. It wraps the instance in the `TelemetryCollector` proxy.
4. The proxy records payload sizes, computes model costs against the `llm_cost_overrides` database,
   and intercepts streaming chunks.
