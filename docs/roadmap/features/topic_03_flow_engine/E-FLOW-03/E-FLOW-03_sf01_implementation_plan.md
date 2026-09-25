# E-FLOW-03 SF-01 — Polish & Close

**Status**: APPROVED · **FRs owned**: FR-6 · **Depends on**: none · Design:
[E-FLOW-03_design.md](E-FLOW-03_design.md) §Sub-features → SF-01

## Goal

The registry, adapters, factory and config already work. SF-01 makes the feature shippable: optional
dependency groups in `pyproject.toml`, accurate `context.yaml` metadata, an E2E test over the full
stack, and updated docs.

Scope is configuration and documentation only; fully backward compatible. Phase 5 consistency
check: no unresolved decisions, no contradictions. Open questions: none.

**Since moved** (checked 2026-09-25): no file exists at `tests/e2e/capabilities/test_provider_e2e.py`,
`docs/user_guides/quickstart.md` or `docs/architecture/architecture_reference.md`; the nearest
provider E2E is `tests/e2e/capabilities/infrastructure/test_provider_cli_e2e.py`.

## Changes

1. **`pyproject.toml`** [MODIFY] — add `[project.optional-dependencies]`, and `"respx>=0.21"` to
   `[dependency-groups] dev` (HTTP client mocking in the E2E test):
   ```toml
   openai = ["openai>=1.5"]
   anthropic = ["anthropic>=0.25"]
   mistral = ["mistralai>=1.0"]
   qwen = ["openai>=1.5"]
   all-llm = ["openai>=1.5", "anthropic>=0.25", "mistralai>=1.0"]
   ```
2. **`src/specweaver/infrastructure/llm/context.yaml`** [MODIFY] — `description` states multiple
   providers, not just Gemini. `exposes` lists all adapters: `GeminiAdapter`, `OpenAIAdapter`,
   `AnthropicAdapter`, `MistralAdapter`, `QwenAdapter`, `get_adapter_class`,
   `get_merged_default_costs`. `async_ready` → `true`.
3. **`src/specweaver/infrastructure/llm/adapters/context.yaml`** [MODIFY] — `async_ready` → `true`;
   fix `description` if it mentions only Gemini.
4. **Adapters** (openai.py, anthropic.py, mistral.py, qwen.py) [MODIFY] — in the lazy
   `_get_client()`, wrap `import <package>` in `try/except ImportError` and raise a user-friendly
   `LLMAdapterError` (e.g., "The 'anthropic' package is not installed. Run
   `pip install specweaver[anthropic]`") at instantiation, not a raw traceback deep in execution.
5. **`README.md`** [MODIFY] — LLM section names OpenAI, Anthropic, Mistral and Qwen, with a matrix of
   how to install each (`pip install specweaver[<provider>]`) and its API key environment variable
   (`OPENAI_API_KEY`, etc.).
6. **`docs/user_guides/quickstart.md`** [MODIFY] — how to configure each provider, with its required
   environment variables.
7. **`docs/architecture/architecture_reference.md`** [MODIFY] — LLM adapter section reflects the
   multi-provider registry.

## Tests

| Test | Proves |
|---|---|
| `tests/e2e/capabilities/test_provider_e2e.py` [NEW] — parameterized over **all** providers (`openai`, `anthropic`, `mistral`, `qwen`, `gemini`); mocks the HTTP layer (`respx` for `httpx`-based clients, `unittest.mock` for provider SDK clients) and simulates full pipeline runs | `LLMSettings.provider` decides the adapter the `factory` builds, and telemetry is collected |
| `tests/unit/infrastructure/llm/adapters/test_registry.py` [NEW/MODIFY] — calls `get_merged_default_costs()` | the registry aggregates `default_costs` from all loaded adapters without dropping data or crashing |
| unit — missing package, via `monkeypatch.setitem(sys.modules, "<package>", None)` | the `ImportError` path raises `LLMAdapterError`, even when the dependency is installed |

Verification:

1. Check `pyproject.toml` with `pip install -e .[all-llm]`.
2. `pytest tests/e2e/capabilities/test_provider_e2e.py`.
3. `tach check` passes.
4. Read the updated markdown docs.
