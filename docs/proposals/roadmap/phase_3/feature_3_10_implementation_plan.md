# Feature 3.10 — Agentic Research Tools for Planning & Review

Give the Planner and Reviewer agents the ability to **research** during their work — search the project's file system and the web — so they can make better-informed decisions, verify architecture fit, and discover best practices.

> **Core mechanism**: LLM function calling via provider-agnostic abstraction. The LLM decides what to search, calls tools, reads results, and uses them in its output. No new CLI commands. No user-facing configuration.
> **Depends on**: Feature 3.6 (Plan phase)

---

## Motivation

Today, the Planner and Reviewer operate blind — they see only the spec, constitution, standards, and topology summary that are pre-assembled into the prompt. They cannot:

- Look up existing patterns in the codebase ("Is there already a handler for this?")
- Check if a module structure follows the project's conventions
- Read reference implementations or blueprints mentioned in ORIGINS.md
- Search the web for best practices or library documentation
- Verify that a proposed solution fits the existing architecture

Real architects and reviewers constantly research while working. SpecWeaver's agents should too.

---

## Design Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | **Tool mechanism** | LLM function calling via provider-agnostic abstraction | LLM decides what to search and when. No pre-collection guesswork. Multi-turn agentic loop. SpecWeaver defines tools as `ToolDefinition` models; each adapter converts to its provider's format (Gemini `FunctionDeclaration`, OpenAI `tools`, etc.). |
| 2 | **LLM adapter change** | Add `ToolDefinition` + `ToolCall` models to `models.py`. Default `generate_with_tools()` on base adapter (falls back to `generate()` for adapters that don't support tools). Each adapter overrides with provider-specific implementation. | Strict abstraction — zero provider-specific types in shared models. Adapters that don't support tools yet still work (tools silently disabled). |
| 3 | **Tool boundary enforcement** | Hard boundary = `RunContext.project_path` at feature level. At component level: boundary = service/module root (from decomposition context) + read-only access to neighboring API contracts. | Dynamic, follows the decomposition lifecycle. |
| 4 | **No new CLI** | Tools are internal to agent loops. Users don't configure or invoke them. | User asked for zero CLI additions. Configuration is implicit from project registration. |
| 5 | **Tool count** | 6 tools: 4 filesystem + 2 web | Minimal set that covers real research needs. |
| 6 | **Web search API** | Google Custom Search initially. Interface allows swapping. | Same Google ecosystem as Gemini. Alternative: DuckDuckGo, Brave Search, SerpAPI. |
| 7 | **Max tool iterations** | Configurable, default 5 rounds of tool calls per agent invocation | Prevents runaway loops. After N rounds, agent must produce output with what it has. |
| 8 | **Agentic loop location** | New method on adapter: `generate_with_tools()`. Callers (Planner, Reviewer) opt-in by passing tools. | Keeps the loop in one place. Non-tool callers continue using `generate()` unchanged. |
| 9 | **Loop nesting** | Tool loop (inside adapter) runs to completion first, producing final text. Planner's JSON retry loop is *outside* — it validates the text and retries if needed. Loops don't mix. | Clear separation. Worst case 3 × 5 = 15 LLM calls, but in practice tool use resolves in 1–2 rounds and retries are rare. Log warning when total calls exceed 5. |

---

## Sub-phase 3.10a: Dynamic Workspace Boundaries

**Goal**: SpecWeaver knows where an agent works and enforces file access boundaries that change based on pipeline phase.

### Boundary Model

```
Feature-level agent (planning/review of the feature spec)
├── Sees: entire project root
└── Hard boundary: project_path (from sw init)

Component-level agent (planning/review of a microservice component)
├── Sees: microservice folder + API contracts of other services  
└── Hard boundary: microservice root + published API surfaces
```

### What Needs to Exist

#### [NEW] `src/specweaver/research/boundaries.py`

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

> [!NOTE]
> **How does the component-level boundary get determined?**
> When Feature 3.1 (decomposition) decomposes a feature into sub-features per microservice, it stores the assignment in the DB: "sub-feature X belongs to microservice Y, hard boundaries = `services/auth/`". The `RunContext` is populated from this DB entry when spawning component pipelines. `WorkspaceBoundary.from_run_context()` reads `workspace_roots` (set by decomposition) and `api_contract_paths` (neighboring APIs).
>
> API contract discovery uses `context.yaml` `exposes` sections from neighboring modules. For brownfield projects without `context.yaml`, convention-based discovery (`openapi.yaml`, `*_api.py`, `*_pb2.py`) is used as fallback. This will be refactored once hybrid RAG is implemented.
>
> If neither `workspace_roots` nor a nearby `context.yaml` exist, the boundary defaults to `project_path` (feature-level).

#### [MODIFY] `src/specweaver/flow/_base.py` — RunContext

Add optional field for module-level boundary context:

```diff
 class RunContext(BaseModel):
     ...
     plan: str | None = None
+    workspace_roots: list[str] | None = None  # Override boundary roots (set by decomposition)
+    api_contract_paths: list[str] | None = None  # Neighboring API surfaces (read-only)
```

---

## Sub-phase 3.10b: Research Tools + Agentic Loop

**Goal**: Give Planner and Reviewer 6 research tools via LLM function calling (provider-agnostic). Convert their single-shot LLM calls into tool-assisted calls. The tools are **not** agents — they are simple utility functions that the agent (Planner/Reviewer) invokes via the LLM's function calling mechanism.

### Tool Definitions

#### File System Tools (boundary-enforced)

| Tool | Parameters | Returns |
|------|-----------|---------|
| `grep` | `pattern: str`, `path: str` (relative, default: `.`), `context_lines: int` (default: 3), `case_sensitive: bool` (default: false), `max_results: int` (default: 20) | Match list: `{file, line_number, content, context_before, context_after}` |
| `find_files` | `pattern: str` (glob), `path: str` (relative, default: `.`), `type: str` (`file`\|`directory`\|`any`), `max_results: int` (default: 30) | File list: `{path, type, size_bytes}` |
| `read_file` | `path: str` (relative), `start_line: int` (optional), `end_line: int` (optional) | `{path, content, total_lines}` — capped at 200 lines per call. Tool description instructs LLM: "To read more, call again with different `start_line`/`end_line`." |
| `list_directory` | `path: str` (relative, default: `.`), `depth: int` (default: 2), `max_entries: int` (default: 50) | Tree: `{path, type, children}` |

All paths are **relative to the workspace root**. The tool implementation resolves them via `WorkspaceBoundary.validate_path()` before any filesystem access.

#### Web Tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `web_search` | `query: str`, `max_results: int` (default: 5) | Result list: `{title, snippet, url}` |
| `read_url` | `url: str`, `max_chars: int` (default: 10000) | `{url, content}` — HTML stripped, truncated to max_chars |

> [!IMPORTANT]
> Web tools are **optional**. They only activate when search credentials are configured (`SEARCH_API_KEY` + `SEARCH_ENGINE_ID` env vars for Google Custom Search). When missing, the LLM simply doesn't have web tools available — no error, just fewer capabilities. Alternative backends (Brave Search, SerpAPI) can be swapped via the same interface.

### Architecture

#### [NEW] `src/specweaver/research/` module

```
research/
├── __init__.py
├── context.yaml          # Module manifest
├── boundaries.py         # WorkspaceBoundary (from 3.10a)
├── tools.py              # Tool implementations (6 functions)
├── definitions.py        # ToolDefinition instances (provider-agnostic)
└── executor.py           # Tool dispatch: (name, args) → result
```

#### [NEW] `src/specweaver/research/tools.py`

6 standalone functions, each taking validated inputs and returning dicts:

```python
def grep(root: Path, pattern: str, path: str = ".", ...) -> list[dict]: ...
def find_files(root: Path, pattern: str, path: str = ".", ...) -> list[dict]: ...
def read_file(root: Path, path: str, ...) -> dict: ...
def list_directory(root: Path, path: str = ".", ...) -> dict: ...
def web_search(query: str, max_results: int = 5, ...) -> list[dict]: ...
def read_url(url: str, max_chars: int = 10000) -> dict: ...
```

File tools use `subprocess` to call `rg` (ripgrep) for grep and `fd` for find when available, falling back to Python stdlib (`pathlib.glob`, line-by-line read). All tool calls enforce a **10s timeout**. On timeout or file-count limits (1000 files for Python fallback), results include `"truncated": true` and `"warning": "..."` explaining the limitation. First fallback logs a recommendation to install ripgrep.

#### [NEW] `src/specweaver/research/definitions.py`

SpecWeaver `ToolDefinition` instances for all 6 tools. Provider-agnostic — each adapter converts these to its own format (e.g., Gemini `FunctionDeclaration`, OpenAI tool schema).

#### [NEW] `src/specweaver/research/executor.py`

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

### LLM Layer Changes (Provider-Agnostic Abstraction)

#### [MODIFY] `src/specweaver/llm/models.py`

Add provider-agnostic tool models:

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

Update `GenerationConfig`:

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

Update `LLMResponse`:

```diff
 class LLMResponse(BaseModel):
     text: str
     model: str
     usage: TokenUsage = Field(default_factory=TokenUsage)
     finish_reason: str = "stop"
+    tool_calls: list[ToolCall] = Field(default_factory=list)  # Non-empty if LLM wants to call tools
```

#### [MODIFY] `src/specweaver/llm/adapters/base.py`

**Non-abstract** default implementation — adapters that don't support tools yet fall back gracefully:

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

#### [MODIFY] `src/specweaver/llm/adapters/gemini.py`

Override `generate_with_tools()` — converts SpecWeaver models to Gemini types **inside the adapter only**:

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
> **Abstraction boundary**: All Gemini-specific types (`types.FunctionDeclaration`, `types.Part.from_function_response`, `response.function_calls`) are confined to `gemini.py`. The `research/` module, `Planner`, `Reviewer`, and all shared models use only SpecWeaver's `ToolDefinition`, `ToolCall`, and `ToolExecutor`. Future adapters (OpenAI, Anthropic, etc.) implement the same conversion pattern inside their own adapter file.

### Planner & Reviewer Changes

#### [MODIFY] `src/specweaver/planning/planner.py`

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

When `tool_executor` is provided:
- Add research tools to `GenerationConfig.tools`
- Update system prompt to explain available tools and when to use them
- Call `generate_with_tools()` instead of `generate()`
- The LLM's final text output is still JSON → same validation/retry logic

When `tool_executor` is None: behavior is unchanged (backward compatible).

#### [MODIFY] `src/specweaver/review/reviewer.py`

Same pattern — when `tool_executor` is available, the reviewer can research before making its verdict:

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

#### [MODIFY] `src/specweaver/flow/_generation.py` (PlanSpecHandler)

Thread the `ToolExecutor` from `RunContext` through to `Planner`:

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

#### [MODIFY] `src/specweaver/flow/_review.py` (ReviewSpecHandler, ReviewCodeHandler)

Same pattern — build `ToolExecutor` from `RunContext`, pass to `Reviewer`.

> [!NOTE]
> **Bug fix (existing)**: Both `ReviewSpecHandler` and `ReviewCodeHandler` currently do not pass `standards=context.standards` to the Reviewer. This will be fixed as part of 3.10 while modifying these handlers (one-line addition per handler).

---

## Scope Boundaries

**IN scope:**
- 6 research tools (4 filesystem + 2 web)
- `WorkspaceBoundary` with dynamic boundary resolution
- Agentic loop via `generate_with_tools()` on the LLM adapter
- Planner and Reviewer gain tool-use capability
- Web tools gated by env var (no API key = no web tools)

**OUT of scope:**
- New CLI commands
- User-facing configuration of tools
- File writing/modification tools (agents are read-only researchers)
- Git history search (future tool addition)
- Code AST analysis (already covered by standards module)
- API contract generation for greenfield (covered by Feature 3.20b)

---

## Verification Plan

### Automated Tests

**Unit tests (`tests/unit/research/`):**
- `WorkspaceBoundary` path validation (within boundary, escape attempt, relative resolution, api_paths)
- `WorkspaceBoundary.from_run_context()` at feature-level and component-level
- Each tool function in isolation (grep, find_files, read_file, list_directory against test fixtures)
- `web_search` and `read_url` with mocked HTTP
- `ToolExecutor` dispatch (valid tool name, invalid tool name, boundary violation)
- `grep` with ripgrep available and fallback to Python
- `find_files` with fd available and fallback to pathlib.glob
- Tool result size limits (max_results, max_chars, line caps)
- Timeout enforcement on tool execution

**Unit tests (`tests/unit/llm/`):**
- `GenerationConfig` with tools field
- `generate_with_tools()` with mocked LLM responses (no tool calls, single tool call, multiple rounds, max rounds reached)
- Tool call → response → tool call → response chain

**Unit tests (`tests/unit/planning/`, `tests/unit/review/`):**
- Planner with tool_executor=None (backward compat, no behavior change)
- Planner with tool_executor (verify `generate_with_tools` is called)
- Reviewer with tool_executor=None (backward compat)
- Reviewer with tool_executor (verify `generate_with_tools` is called)
- Updated system prompts include tool usage instructions

**Integration tests (`tests/integration/research/`):**
- End-to-end: Planner with real tool executor + mocked LLM that makes tool calls → verify tools are executed → final plan produced
- Boundary enforcement in pipeline context: feature-level vs component-level boundaries

**Commands:**
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

### Manual Verification

1. Run `sw plan` on a spec in a project with multiple modules → verify the Planner searches the codebase during planning (visible in debug logs)
2. Verify file tool calls are bounded to project root (debug logs show resolved paths)
3. Without `SEARCH_API_KEY` → verify web tools are not offered to the LLM
4. With `SEARCH_API_KEY` → verify web search results appear in debug logs

---

## Documentation Updates

| Doc | What to add |
|-----|-------------|
| `README.md` | Features bullet: "Agentic research — Planner and Reviewer search your codebase and the web" |
| `docs/proposals/roadmap/phase_3_feature_expansion.md` | Update Feature 3.10 row: new description, mark sub-phases |
| `docs/test_coverage_matrix.md` | New section: Research Tools |
