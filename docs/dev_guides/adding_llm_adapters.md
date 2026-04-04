# Developer Guide: Integrating a New LLM Provider

SpecWeaver natively adopts a multi-provider adapter approach for routing Large Language Model interactions. Because the LLM landscape mutates rapidly, we built an auto-discovery registry that eliminates internal hardcoding and decouples business logic from cost-tracking algorithms.

This guide explains how to add zero-friction support for a new provider (e.g., Cohere, AI21).

---

## 1. The Adapter ABC

Every provider interface must inherit from the core `LLMAdapter` abstract class located natively in `llm/adapters/base.py`. 

Your adapter defines its own internal SDK endpoints, request/response models, and context-window chunking. 

**Location:** `src/specweaver/llm/adapters/<provider_name>.py`

### Required Concrete Overrides:
1. `generate(prompt: str) -> str`: Standard chat completions without system injection or tools.
2. `generate_with_tools(messages, config, dispatcher)`: Must map the provider's native function-calling formats (e.g., translating a JSON schema into Cohere's tool schema) and correctly pipe native payload callbacks to the `loom/dispatcher.py`.
3. `provider_name`: A unique static string strictly identifying this class.

---

## 2. The Auto-Discovery Registry

To prevent central routing swamps, SpecWeaver heavily utilizes module dynamic scanning. 

Within `src/specweaver/llm/adapters/__init__.py`, the module actively scans all internal subclass structures the moment it spins up. As long as your adapter declares `provider_name = "cohere"` and is placed within the `adapters/` folder, the environment will dynamically support it.

_You do not need to manually append your adapter to a master array._

---

## 3. Telemetry Transparency 

Cost routing, token counting, and database lineage tracking are **not** the responsibility of your Adapter. A frequent mistake when expanding LLMs is trying to intercept payload counts inside the generation execution.

**How it works seamlessly:**
1. The `LLMFactory` (`llm/factory.py`) receives a request to spin up an LLM (e.g., "cohere").
2. It instantiates your native `CohereAdapter`.
3. It securely proxies your entire class wrapped inside the `TelemetryCollector` decorator.
4. Your adapter operates flawlessly while the Proxy transparently records payload sizes, computes standard model costs against the `llm_cost_overrides` database, and intercepts streaming chunks contextually.

**Summary:** Write the pure adapter pipeline. The factory will provide the telemetry metrics for free.
