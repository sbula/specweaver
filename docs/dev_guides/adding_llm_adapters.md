# Adding an LLM Provider

Use when: you add a new LLM provider (e.g. Cohere, AI21) to SpecWeaver.

Each provider is an adapter found by an auto-discovery registry: no hardcoded provider list, and no
cost tracking inside business logic.

Paths: `src/specweaver/infrastructure/llm/`; discovery lives in `adapters/registry.py`.

## Steps

1. **Write the adapter** at `src/specweaver/infrastructure/llm/adapters/<provider_name>.py`,
   inheriting `LLMAdapter` from `adapters/base.py`. It owns its SDK endpoints,
   request/response models, and context-window chunking.
2. **Implement the overrides:**
   1. `async generate(messages, config) -> LLMResponse`: plain chat completion, no tools.
   2. `generate_with_tools(messages, config, dispatcher)`: map the provider's native function-calling
      format (e.g. a JSON schema into Cohere's tool schema) and pipe native payload callbacks to the
      `sandbox/dispatcher.py`. Loop over `tool_rounds(config)` (`infrastructure/llm/models.py`),
      which refuses a config with no round limit; if the model is still calling tools when the
      rounds run out, raise `ToolRoundsExceededError.reached(...)`. Never return a placeholder text
      or the last half-finished response as the answer. Call `on_tool_round` before every request
      (the spend brake checks each round there), and attach the usage so far to any exception
      leaving the loop (`exc.usage = cumulative_usage`), so a failed loop is counted exactly.
   3. `provider_name`: a unique static string identifying the class; it is also the server `kind`
      a settings file names.
   4. `default_base_url`: the provider's official address, written out, so no SDK environment
      variable can redirect a call; `None` for a server the user must name.
   5. No key variable. The key comes from the server entry's `api_key_env`; an adapter never reads
      the environment itself.
3. **Send only the sampling values that are set.** `GenerationConfig.temperature`, `top_p` and
   `top_k` are `None` unless a role or the catalogue sets them; many current models refuse any value
   but their default.
4. **Nothing to register.** The package scans its modules and subclasses at start-up. An adapter
   with `provider_name = "cohere"` inside `adapters/` is supported. _Do not append it to a master
   array._
5. **No prices in the adapter.** Prices live in the model catalogue
   (`infrastructure/llm/catalogue_data/models.toml`, a short list kept by hand) and in
   the user's `[models."<id>"]` corrections.

## Rules

- **No telemetry in the adapter.** Cost routing, token counting and database lineage are not its
  job; do not intercept payload counts inside generation.
- **Every tool round is checked before it is sent.** `generate_with_tools` takes a
  `before_request(round_num, prompt_chars)` hook and calls it before each request, with the size of
  everything the round sends (system prompt, tool schemas, messages). The collector checks the
  spend brake there; skipping the call lets a long tool loop spend unchecked.
- **Name errors by status code.** Map a provider error to `AuthenticationError`, `RateLimitError`,
  `ModelNotFoundError` or `GenerationError` by its HTTP status, never by words in the message.
- **Adapters are built in one place.** `RoleResolver` (`infrastructure/llm/resolve.py`) builds each
  from its server entry (`servers.py`), wraps it in the server's parallel limit and a
  `TelemetryCollector` that prices calls from the catalogue. Nothing else constructs an adapter.
