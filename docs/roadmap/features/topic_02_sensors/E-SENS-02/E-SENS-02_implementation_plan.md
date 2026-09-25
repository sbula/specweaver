# E-SENS-02 — Agentic Research Tools for Planning & Review

**Status**: ✅ complete (topic file) · **Legacy**: Feature 3.10 · **Depends on**: Feature 3.6 (Plan
phase) · **Sub-phases**: 3.10a boundaries, 3.10b tools + loop

## What it does

The Planner and Reviewer can research while they work: search the project's file system and the
web, read results, and use them in their output. Before this they saw only the pre-assembled spec,
constitution, standards and topology summary.

What they can now do: look up existing patterns ("Is there already a handler for this?"), check a
module structure against project conventions, read reference implementations or blueprints named in
ORIGINS.md, search the web for best practices or library docs, verify a solution fits the
architecture.

Mechanism: LLM function calling through a provider-agnostic abstraction. The LLM decides what to
search, calls tools, reads results. No new CLI commands. No user-facing configuration.

## Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | **Tool mechanism** | LLM function calling, provider-agnostic | LLM decides what to search and when; no pre-collection guesswork; multi-turn loop. See note 1. |
| 2 | **LLM adapter change** | `ToolDefinition` + `ToolCall` in `models.py`; default `generate_with_tools()` on the base adapter (note 2) | No provider types in shared models; tool-less adapters still work |
| 3 | **Tool boundary enforcement** | Feature level: `RunContext.project_path`. Component level: service/module root + read-only neighbour API contracts | Dynamic; follows decomposition |
| 4 | **No new CLI** | Tools are internal to agent loops. Users don't configure or invoke them. | User asked for zero CLI additions. Configuration is implicit from project registration. |
| 5 | **Tool count** | 6 tools: 4 filesystem + 2 web | Minimal set that covers real research needs. |
| 6 | **Web search API** | Google Custom Search first; the interface allows swapping. | Same Google ecosystem as Gemini. Alternatives: DuckDuckGo, Brave Search, SerpAPI. |
| 7 | **Max tool iterations** | Configurable, default 5 rounds of tool calls per agent invocation | Prevents runaway loops. After N rounds the agent must answer with what it has. |
| 8 | **Agentic loop location** | New adapter method `generate_with_tools()`. Callers (Planner, Reviewer) opt in by passing tools. | One place for the loop. Non-tool callers keep using `generate()`. |
| 9 | **Loop nesting** | Tool loop (in the adapter) finishes first, yields text; the Planner's JSON retry loop is *outside* it | Loops don't mix. Worst case 3 × 5 = 15 LLM calls (note 9) |

- Note 1: SpecWeaver defines tools as `ToolDefinition` models; each adapter converts them to its provider's
  format (Gemini `FunctionDeclaration`, OpenAI `tools`, etc.).
- Note 2: the base default falls back to `generate()` for adapters that don't support tools (tools
  silently disabled). Each adapter overrides with a provider-specific implementation.
- Note 9: in practice tool use resolves in 1–2 rounds and retries are rare. Log a warning when total calls
  exceed 5.

## Scope

- **In:** 6 research tools (4 filesystem + 2 web) · `WorkspaceBoundary` with dynamic boundary
  resolution · agentic loop via `generate_with_tools()` on the LLM adapter · Planner and Reviewer
  gain tool use · web tools gated by env var (no API key = no web tools).
- **Out:** new CLI commands · user-facing tool configuration · file writing/modification tools
  (agents are read-only researchers) · Git history search (future tool) · code AST analysis (the
  standards module covers it) · API contract generation for greenfield (Feature 3.20b).

## 3.10a — Dynamic workspace boundaries

SpecWeaver knows where an agent works and enforces file access boundaries that change with the
pipeline phase.

```
Feature-level agent (planning/review of the feature spec)
├── Sees: entire project root
└── Hard boundary: project_path (from sw init)

Component-level agent (planning/review of a microservice component)
├── Sees: microservice folder + API contracts of other services  
└── Hard boundary: microservice root + published API surfaces
```

**[NEW] `src/specweaver/research/boundaries.py`**

```python
class WorkspaceBoundary:
    """Defines and enforces which paths an agent can access.
    
    Args:
        roots: One or more allowed root directories.
        api_paths: Read-only paths for neighboring API contracts
                   (visible but not searchable in depth).
    """
    def __init__(
        self,
        roots: list[Path],
        api_paths: list[Path] | None = None,
    ) -> None: ...

    def validate_path(self, requested: Path) -> Path:
        """Resolve and validate a path is within boundaries.
        
        Returns the resolved absolute path.
        Raises WorkspaceBoundaryError if path escapes boundaries.
        """

    def resolve_relative(self, relative: str) -> Path:
        """Resolve a relative path against the primary root."""

    @classmethod
    def from_run_context(cls, context: RunContext) -> WorkspaceBoundary:
        """Build boundary from pipeline context.
        
        - Feature-level: boundary = project_path
        - Component-level: boundary = component's module root 
          (from decomposition output / context.yaml)
          + API contract paths of neighboring modules
        """
```

How the component-level boundary is determined: when Feature 3.1 (decomposition) splits a feature
into sub-features per microservice, it stores the assignment in the DB ("sub-feature X belongs to
microservice Y, hard boundaries = `services/auth/`"). The `RunContext` for component pipelines is
populated from that entry. `WorkspaceBoundary.from_run_context()` reads `workspace_roots` (set by
decomposition) and `api_contract_paths` (neighbouring APIs).

- API contract discovery uses the `context.yaml` `exposes` sections of neighbouring modules.
- Brownfield fallback without `context.yaml`: convention-based discovery (`openapi.yaml`,
  `*_api.py`, `*_pb2.py`). To be refactored once hybrid RAG exists.
- Neither `workspace_roots` nor a nearby `context.yaml` → boundary = `project_path` (feature-level).

**[MODIFY] `src/specweaver/flow/_base.py` — RunContext** — optional module-level boundary fields:

```diff
 class RunContext(BaseModel):
     ...
     plan: str | None = None
+    workspace_roots: list[str] | None = None  # Override boundary roots (set by decomposition)
+    api_contract_paths: list[str] | None = None  # Neighboring API surfaces (read-only)
```

## 3.10b — Research tools + agentic loop

Planner and Reviewer get 6 research tools via LLM function calling. Their single-shot LLM calls
become tool-assisted calls. The tools are **not** agents — they are utility functions the agent
invokes through the LLM's function calling.

### Tools

File system tools (boundary-enforced):

| Tool | Parameters | Returns |
|------|-----------|---------|
| `grep` | `pattern: str`, `path: str` (relative, default: `.`), `context_lines: int` (default: 3), `case_sensitive: bool` (default: false), `max_results: int` (default: 20) | Match list: `{file, line_number, content, context_before, context_after}` |
| `find_files` | `pattern: str` (glob), `path: str` (relative, default: `.`), `type: str` (`file`\|`directory`\|`any`), `max_results: int` (default: 30) | File list: `{path, type, size_bytes}` |
| `read_file` | `path: str` (relative), `start_line: int` (optional), `end_line: int` (optional) | `{path, content, total_lines}` — capped at 200 lines per call (see below) |
| `list_directory` | `path: str` (relative, default: `.`), `depth: int` (default: 2), `max_entries: int` (default: 50) | Tree: `{path, type, children}` |

- All paths are **relative to the workspace root**, resolved through
  `WorkspaceBoundary.validate_path()` before any filesystem access.
- `read_file`'s tool description tells the LLM: "To read more, call again with different
  `start_line`/`end_line`."

Web tools:

| Tool | Parameters | Returns |
|------|-----------|---------|
| `web_search` | `query: str`, `max_results: int` (default: 5) | Result list: `{title, snippet, url}` |
| `read_url` | `url: str`, `max_chars: int` (default: 10000) | `{url, content}` — HTML stripped, truncated to max_chars |

> [!IMPORTANT]
> Web tools are **optional**. They activate only when search credentials are configured
> (`SEARCH_API_KEY` + `SEARCH_ENGINE_ID` env vars for Google Custom Search). Missing → the LLM
> doesn't get web tools; no error. Alternative backends (Brave Search, SerpAPI) swap in via the
> same interface.

### Module — [NEW] `src/specweaver/research/`

```
research/
├── __init__.py
├── context.yaml          # Module manifest
├── boundaries.py         # WorkspaceBoundary (from 3.10a)
├── tools.py              # Tool implementations (6 functions)
├── definitions.py        # ToolDefinition instances (provider-agnostic)
└── executor.py           # Tool dispatch: (name, args) → result
```

**[NEW] `src/specweaver/research/tools.py`** — 6 standalone functions; validated inputs in, dicts out:

```python
def grep(root: Path, pattern: str, path: str = ".", ...) -> list[dict]: ...
def find_files(root: Path, pattern: str, path: str = ".", ...) -> list[dict]: ...
def read_file(root: Path, path: str, ...) -> dict: ...
def list_directory(root: Path, path: str = ".", ...) -> dict: ...
def web_search(query: str, max_results: int = 5, ...) -> list[dict]: ...
def read_url(url: str, max_chars: int = 10000) -> dict: ...
```

- File tools call `rg` (ripgrep) for grep and `fd` for find via `subprocess` when available, else
  Python stdlib (`pathlib.glob`, line-by-line read). The first fallback logs a recommendation to
  install ripgrep.
- Every tool call has a **10s timeout**. On timeout or file-count limit (1000 files for the Python
  fallback) results carry `"truncated": true` and a `"warning": "..."` explaining the limit.

**[NEW] `src/specweaver/research/definitions.py`** — SpecWeaver `ToolDefinition` instances for all 6 tools. Provider-agnostic;
each adapter converts them (e.g. Gemini `FunctionDeclaration`, OpenAI tool schema).

**[NEW] `src/specweaver/research/executor.py`** — tool dispatch for Planner/Reviewer calls:

```python
class ToolExecutor:
    """Dispatches tool calls from the LLM to tool implementations.
    
    Provider-agnostic: accepts (name, args) pairs, not provider-specific types.
    Each adapter extracts (name, args) from its provider's response format.
    
    Args:
        boundary: WorkspaceBoundary for path validation.
        web_enabled: Whether web tools are available.
    """
    def __init__(self, boundary: WorkspaceBoundary, *, web_enabled: bool = False) -> None: ...

    async def execute(self, name: str, args: dict) -> dict:
        """Execute a single tool call by name with arguments."""

    def available_tools(self) -> list[ToolDefinition]:
        """Return tool definitions for tools available in this executor.
        (Excludes web tools if web_enabled=False.)
        """
```

### LLM layer (provider-agnostic)

**[MODIFY] `src/specweaver/llm/models.py`** — tool models:

```python
class ToolParameter(BaseModel):
    """A single parameter in a tool definition."""
    name: str
    type: Literal["string", "integer", "boolean", "number"]
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None  # valid values

class ToolDefinition(BaseModel):
    """Provider-agnostic tool definition.
    
    Each adapter converts this to its provider's format:
    - Gemini → types.FunctionDeclaration
    - OpenAI → {"type": "function", "function": {...}}
    - Anthropic → {"name": ..., "input_schema": {...}}
    """
    name: str
    description: str
    parameters: list[ToolParameter] = []

class ToolCall(BaseModel):
    """A tool invocation extracted from an LLM response.
    
    Provider-agnostic: each adapter converts its provider's
    response format into this model.
    """
    name: str
    args: dict[str, Any]
    call_id: str = ""  # Provider-specific correlation ID
```

`GenerationConfig`:

```diff
 class GenerationConfig(BaseModel):
     model: str
     temperature: float = Field(default=0.7, ge=0.0, le=2.0)
     max_output_tokens: int = Field(default=4096, gt=0)
     response_format: Literal["text", "json"] = "text"
     system_instruction: str | None = None
-    # Future: top_p, stop_sequences, tools, seed
+    tools: list[ToolDefinition] | None = None  # Provider-agnostic tool definitions
+    max_tool_rounds: int = 5  # Max agentic loop iterations
+    # Future: top_p, stop_sequences, seed
```

`LLMResponse`:

```diff
 class LLMResponse(BaseModel):
     text: str
     model: str
     usage: TokenUsage = Field(default_factory=TokenUsage)
     finish_reason: str = "stop"
+    tool_calls: list[ToolCall] = Field(default_factory=list)  # Non-empty if LLM wants to call tools
```

**[MODIFY] `src/specweaver/llm/adapters/base.py`** — a **non-abstract** default, so adapters without
tool support fall back:

```python
class LLMAdapter(ABC):
    # ... existing abstract methods ...

    async def generate_with_tools(
        self,
        messages: list[Message],
        config: GenerationConfig,
        tool_executor: Any,  # ToolExecutor from research module
    ) -> LLMResponse:
        """Agentic generation loop with tool use.
        
        Default implementation: ignores tools, calls generate() directly.
        Adapters that support function calling override this.
        
        Returns:
            LLMResponse with cumulative token usage across all rounds.
        """
        # Default: no tool support, just generate
        logger.warning(
            "%s does not support tool use — falling back to generate()",
            self.provider_name,
        )
        return await self.generate(messages, config)
```

**[MODIFY] `src/specweaver/llm/adapters/gemini.py`** — overrides `generate_with_tools()`; converts
SpecWeaver models to Gemini types **inside the adapter only**:

```python
def _to_gemini_tools(self, tools: list[ToolDefinition]) -> list[types.Tool]:
    """Convert SpecWeaver ToolDefinitions to Gemini FunctionDeclarations."""
    declarations = []
    for tool in tools:
        params = {p.name: {"type": p.type, "description": p.description} for p in tool.parameters}
        declarations.append(types.FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters={"type": "object", "properties": params},
        ))
    return [types.Tool(function_declarations=declarations)]

def _extract_tool_calls(self, response) -> list[ToolCall]:
    """Convert Gemini function_calls to SpecWeaver ToolCall models."""
    if not response.function_calls:
        return []
    return [ToolCall(name=fc.name, args=dict(fc.args)) for fc in response.function_calls]

async def generate_with_tools(
    self, messages, config, tool_executor,
) -> LLMResponse:
    gemini_tools = self._to_gemini_tools(config.tools)
    gen_config = types.GenerateContentConfig(
        tools=gemini_tools,
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        system_instruction=system_instruction,
    )
    
    cumulative_usage = TokenUsage()  # Track across all rounds
    
    for round in range(config.max_tool_rounds):
        response = await client.aio.models.generate_content(...)
        cumulative_usage += self._extract_usage(response)  # Accumulate
        
        tool_calls = self._extract_tool_calls(response)  # Gemini → SpecWeaver
        if tool_calls:
            tool_results = []
            for tc in tool_calls:
                result = await tool_executor.execute(tc.name, tc.args)  # Provider-agnostic call
                tool_results.append((tc, result))
            
            # Append in Gemini-specific format (only here, inside the adapter)
            contents.append(response.candidates[0].content)
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=tc.name, response=r)
                       for tc, r in tool_results],
            ))
        else:
            resp = self._parse_response(response, config.model)
            resp.usage = cumulative_usage  # Return total, not just last round
            return resp
    
    # Max rounds reached
    resp = self._parse_response(response, config.model)
    resp.usage = cumulative_usage
    return resp
```

> [!IMPORTANT]
> **Abstraction boundary**: all Gemini-specific types (`types.FunctionDeclaration`,
> `types.Part.from_function_response`, `response.function_calls`) stay in `gemini.py`. The
> `research/` module, `Planner`, `Reviewer` and all shared models use only SpecWeaver's
> `ToolDefinition`, `ToolCall` and `ToolExecutor`. Other adapters (OpenAI, Anthropic, etc.)
> implement the same conversion inside their own adapter file.

### Planner & Reviewer

**[MODIFY] `src/specweaver/planning/planner.py`**:

```diff
 class Planner:
     async def generate_plan(
         self,
         spec_content: str,
         spec_path: str,
         spec_name: str,
         *,
         constitution: str | None = None,
         standards: str | None = None,
+        tool_executor: Any | None = None,  # ToolExecutor for research
     ) -> PlanArtifact:
```

With a `tool_executor`: add the research tools to `GenerationConfig.tools`, tell the system prompt
which tools exist and when to use them, and call `generate_with_tools()` instead of `generate()`.
The final text is still JSON → same validation/retry logic. With `tool_executor` None: unchanged
(backward compatible).

**[MODIFY] `src/specweaver/review/reviewer.py`** — same pattern; the reviewer can research before
its verdict:

```diff
 class Reviewer:
     async def review_spec(
         self,
         spec_path: Path,
         *,
         topology_contexts: ...,
         constitution: ...,
         standards: ...,
+        tool_executor: Any | None = None,
     ) -> ReviewResult:
```

**[MODIFY] `src/specweaver/flow/_generation.py` (PlanSpecHandler)** — threads the `ToolExecutor`
from `RunContext` to the `Planner`:

```python
# Build workspace boundary from RunContext
boundary = WorkspaceBoundary.from_run_context(context)
executor = ToolExecutor(boundary, web_enabled=bool(os.environ.get("SEARCH_API_KEY")))

# Pass to planner
plan = await planner.generate_plan(
    ...,
    tool_executor=executor,
)
```

**[MODIFY] `src/specweaver/flow/_review.py` (ReviewSpecHandler, ReviewCodeHandler)** — same pattern:
build a `ToolExecutor` from `RunContext`, pass it to the `Reviewer`. Both handlers also pass
`standards=context.standards` to the Reviewer (a one-line fix per handler; they did not before).

## Tests

| Where | Covers |
|---|---|
| `tests/unit/research/` | `WorkspaceBoundary` path validation (within boundary, escape attempt, relative resolution, api_paths) |
| | `WorkspaceBoundary.from_run_context()` at feature level and component level |
| | each tool function alone (grep, find_files, read_file, list_directory against fixtures) |
| | `web_search` and `read_url` with mocked HTTP |
| | `ToolExecutor` dispatch: valid name, invalid name, boundary violation |
| | `grep` with ripgrep and the Python fallback; `find_files` with fd and the pathlib.glob fallback |
| | result size limits (max_results, max_chars, line caps); timeout enforcement |
| `tests/unit/llm/` | `GenerationConfig` with the tools field |
| | `generate_with_tools()` with mocked responses: no tool calls, single call, multiple rounds, max rounds reached |
| | tool call → response → tool call → response chain |
| `tests/unit/planning/`, `tests/unit/review/` | Planner / Reviewer with tool_executor=None (backward compat, no behaviour change) |
| | Planner / Reviewer with tool_executor (verify `generate_with_tools` is called) |
| | updated system prompts include tool usage instructions |
| `tests/integration/research/` | Planner with a real tool executor + mocked LLM making tool calls → tools execute → plan produced |
| | boundary enforcement in pipeline context: feature-level vs component-level |

```bash
uv run pytest tests/unit/research/ -x -q
uv run pytest tests/unit/llm/ -x -q
uv run pytest tests/unit/planning/ -x -q -k "tool"
uv run pytest tests/unit/review/ -x -q -k "tool"
uv run pytest tests/integration/research/ -x -q
uv run pytest --tb=short -q         # full regression
uv run ruff check src/ tests/
uv run mypy src/
```

Manual:

1. `sw plan` on a spec in a multi-module project → the Planner searches the codebase (debug logs).
2. File tool calls stay inside the project root (debug logs show resolved paths).
3. Without `SEARCH_API_KEY` → web tools are not offered to the LLM.
4. With `SEARCH_API_KEY` → web search results appear in debug logs.

## Docs to update

| Doc | What to add |
|-----|-------------|
| `README.md` | Features bullet: "Agentic research — Planner and Reviewer search your codebase and the web" |
| `docs/roadmap/phase_3_feature_expansion.md` | Update Feature 3.10 row: new description, mark sub-phases |

## Since moved (2026-09-25)

The `research/` module no longer exists. `WorkspaceBoundary` → `src/specweaver/sandbox/security.py`;
web tools → `src/specweaver/sandbox/web/`; `ToolDefinition` → `src/specweaver/infrastructure/llm/models.py`;
`workspace_roots` / `api_contract_paths` → `GraphContext` in `core/flow/handlers/run_context.py`.
Paths above are as of the plan.
