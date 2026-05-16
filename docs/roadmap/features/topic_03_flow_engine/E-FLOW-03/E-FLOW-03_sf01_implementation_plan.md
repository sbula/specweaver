# Implementation Plan: Polish & Close [SF-01: Polish & Close]
- **Feature ID**: E-FLOW-03
- **Sub-Feature**: SF-01 — Polish & Close
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/E-FLOW-03/E-FLOW-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/E-FLOW-03/E-FLOW-03_sf01_implementation_plan.md
- **Status**: APPROVED

## Goal Description

E-FLOW-03 is architecturally complete (all adapters, registry, factory, config are implemented). This sub-feature finishes the remaining polish items to make it shippable. It adds optional dependency groups to `pyproject.toml`, updates stale metadata in `context.yaml` files, adds an E2E test verifying the full stack, and updates the documentation.

## User Review Required (HITL Phase 4 & 5)

> [!WARNING]
> Please review the architectural alignments and provide final **Consistency Check** approval to proceed with SF-01.
> 
> **Phase 5 Consistency Check (Evidence-Backed):**
> 1. **Any unresolved decisions?** No.
> 2. **Architecture and future compatibility:** This is fully backwards compatible and aligned. It simply polishes existing working components.
> 3. **Internal consistency check:** No contradictions exist. 
> 
> **Agent Handoff Risk Evaluation:** Zero risk. Scope is purely configuration and documentation.

## Proposed Changes

---

### Configuration Updates

#### [MODIFY] [pyproject.toml](file:///c:/development/pitbula/specweaver/pyproject.toml)
- **Action**: Add `[project.optional-dependencies]` section. Also add `"respx>=0.21"` to the `[dependency-groups] dev` section to support HTTP client mocking in E2E tests.
- **Content**:
  ```toml
  openai = ["openai>=1.5"]
  anthropic = ["anthropic>=0.25"]
  mistral = ["mistralai>=1.0"]
  qwen = ["openai>=1.5"]
  all-llm = ["openai>=1.5", "anthropic>=0.25", "mistralai>=1.0"]
  ```

#### [MODIFY] [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/context.yaml)
- **Action**: Update `description` to state that it supports multiple providers, not just Gemini. Update `exposes` to list all adapters: `GeminiAdapter`, `OpenAIAdapter`, `AnthropicAdapter`, `MistralAdapter`, `QwenAdapter`, `get_adapter_class`, `get_merged_default_costs`. Change `async_ready` to `true`.

#### [MODIFY] [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/adapters/context.yaml)
- **Action**: Change `async_ready` to `true`. Update `description` if it mentions only Gemini.

---

### E2E Testing

#### [NEW] [test_provider_e2e.py](file:///c:/development/pitbula/specweaver/tests/e2e/capabilities/test_provider_e2e.py)
- **Action**: Create an E2E test parameterized for **all** supported providers (`openai`, `anthropic`, `mistral`, `qwen`, `gemini`). It must mock the HTTP layer (using `respx` for `httpx`-based clients or `unittest.mock` for provider SDK clients) to simulate full pipeline runs for each provider.
- **Purpose**: Prove that `LLMSettings.provider` successfully dictates the adapter used by the `factory`, which then collects telemetry properly.

---

### Core Framework Updates

#### [NEW/MODIFY] [test_registry.py](file:///c:/development/pitbula/specweaver/tests/unit/infrastructure/llm/adapters/test_registry.py)
- **Action**: Add a unit test that calls `get_merged_default_costs()`.
- **Purpose**: Ensure that the dynamic registry correctly aggregates `default_costs` from all loaded adapters without dropping data or crashing.

#### [MODIFY] Adapters (openai.py, anthropic.py, mistral.py, qwen.py)
- **Action**: Inside the lazy `_get_client()` methods, wrap the `import <package>` statements with a `try/except ImportError`.
- **Purpose**: Catch missing dependencies at instantiation instead of a raw traceback deep in execution, raising a user-friendly `LLMAdapterError` (e.g., "The 'anthropic' package is not installed. Run `pip install specweaver[anthropic]`").
- **Verification**: Add a unit test verifying this exception triggers gracefully when the package is absent. Use `monkeypatch.setitem(sys.modules, "<package>", None)` to guarantee the `ImportError` path is tested even if dependencies are installed.

---

### Documentation Updates

#### [MODIFY] [README.md](file:///c:/development/pitbula/specweaver/README.md)
- **Action**: Update the LLM section to mention support for OpenAI, Anthropic, Mistral, and Qwen. Include a matrix detailing how to install each (`pip install specweaver[<provider>]`) and the corresponding API key environment variable required for each (`OPENAI_API_KEY`, etc.).

#### [MODIFY] [quickstart.md](file:///c:/development/pitbula/specweaver/docs/user_guides/quickstart.md)
- **Action**: Add explicit instructions on configuring different providers, listing the required environment variables for each provider.

#### [MODIFY] [architecture_reference.md](file:///c:/development/pitbula/specweaver/docs/architecture/architecture_reference.md)
- **Action**: Update the LLM adapter section to reflect the multi-provider registry.

---

## Open Questions

None.

## Verification Plan

### Automated Tests
1. File inspection of `pyproject.toml` using `pip install -e .[all-llm]`.
2. Run new E2E test `pytest tests/e2e/capabilities/test_provider_e2e.py`.
3. `tach check` passes.

### Manual Verification
1. Visually inspect updated markdown documentation.
