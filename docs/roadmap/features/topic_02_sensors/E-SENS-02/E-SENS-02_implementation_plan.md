# E-SENS-02 — Agentic Research Tools: as built

**Design**: [E-SENS-02_design.md](E-SENS-02_design.md)

```
settings.toml [search] + keys.env ──▶ RoleResolver.search_key ──▶ ModelRouter.search_key
review / generation step ──▶ ToolDispatcher.create_standard_set(search_key=…) ──▶ WebTool
model ──▶ generate_with_tools ──▶ ToolDispatcher ──▶ web_search (Tavily) · read_url (public only)
```

| File (`src/specweaver/`) | Holds | FRs |
|:---|:---|:---|
| `sandbox/web/interfaces/tool.py` | `WebTool`: Tavily search; `read_url` with `_check_public` at every hop, the 2 MB cap and the redirect limit | FR-1, FR-2, FR-3 |
| `core/config/llm_settings.py` | `SearchEntry`: `[search] api_key_env`, a variable name only | FR-4 |
| `infrastructure/llm/resolve.py` · `router.py` | `search_key()`: the key from `keys.env`; `build_router` refuses a missing one before any call | FR-4 |
| `core/flow/handlers/review.py` | `_build_tool_dispatcher`: adds `web` only with a key | FR-5 |
| `sandbox/dispatcher.py` · `registry.py` | hand the key to `WebTool` | FR-5 |
