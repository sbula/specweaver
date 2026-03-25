# Feature 3.11: Auto Spec-Mention Detection

> **Status**: Implemented
> **Depends on**: None (3.10 dependency removed per audit #13)
> **Inspired by**: Aider's `check_for_file_mentions()` ([ORIGINS.md](../../ORIGINS.md))

## Problem

When the LLM mentions specs or files by name during review (e.g. "see `auth_service_spec.md`"
or "the implementation in `utils/helpers.py` should..."), those files are NOT automatically
included in the context for downstream pipeline steps. The user must manually manage which
files are visible.

## Goal

Scan the **final** LLM response text for file and spec references. Resolve them against
the project workspace (respecting workspace boundaries). Store resolved mentions in
`RunContext.feedback` for downstream steps and inject into `PromptBuilder` when building
the next prompt.

## Scope Constraints (v1)

> [!IMPORTANT]
> **v1 is deliberately limited.** The following are explicitly deferred:
> - Mid-loop mention injection (tool-use loop is adapter-internal — see Known Arch Bugs)
> - Planner integration (Planner uses template strings, not PromptBuilder)
> - CLI commands beyond logging

## Sub-Phases

### 3.11a — Mention Scanner (Pure Logic)

New module: `llm/mention_scanner/` (directory with `context.yaml`)

Files:
- `llm/mention_scanner/__init__.py` — re-exports
- `llm/mention_scanner/scanner.py` — `extract_mentions(text: str) → list[str]`
- `llm/mention_scanner/models.py` — `ResolvedMention` dataclass
- `llm/mention_scanner/context.yaml` — module metadata

**`extract_mentions()` — pure function, no I/O:**
- Backtick-quoted paths: `` `src/auth/handler.py` ``
- Quoted paths: `"src/auth/handler.py"`, `'utils.py'`
- Bare spec names: words ending in `_spec.md`, `_spec.yaml`
- Relative paths with `/`: `src/models/user.py`

**Filtering rules:**
- Skip URLs (`http://`, `https://`)
- Skip `__init__.py` unless full path given
- Skip content inside large fenced code blocks (>5 lines)
- Deduplicate by string value

**`ResolvedMention` dataclass** (in `models.py`):
```python
@dataclass
class ResolvedMention:
    original: str          # raw string from LLM response
    resolved_path: Path    # absolute path on disk
    kind: str              # "spec" | "code" | "test" | "config" | "other"
```

Kind determined by extension: `.md` → spec, `.py` → code (unless in `tests/` → test),
`.yaml`/`.json`/`.toml` → config, else → other.

### 3.11b — File Resolution (in Handler, NOT in Scanner)

Resolution happens **in the handler** (not in the scanner module) because it requires
disk I/O (`Path.exists()`) and workspace boundary validation.

**Resolution logic** (implemented as a private helper in `flow/_review.py` — the
flow handler has `RunContext` with `project_path` and `workspace_roots`):

```python
def _resolve_mentions(
    candidates: list[str],
    project_path: Path,
    workspace_roots: list[Path] | None = None,
) -> list[ResolvedMention]: ...
```

- For each candidate: resolve against `project_path`, then `workspace_roots`
- **Workspace boundary enforcement**: resolved files MUST be within allowed
  workspace boundaries. Files from other microservices or outside the project
  root are blocked. This prevents context leakage across security boundaries.
- Return only files that exist on disk
- Deduplicate by resolved absolute path
- Cap at **5 files** total, specs prioritized over code
- No carryover between pipeline steps (each step starts fresh)

### 3.11c — PromptBuilder Integration

**Modify:** `llm/prompt_builder.py`

New method:
```python
def add_mentioned_files(
    self,
    mentions: list[ResolvedMention],
    *,
    max_files: int = 5,
) -> PromptBuilder:
```

- Adds each file as a `_ContentBlock` with `kind="mentioned"`, `priority=4`
  (below explicit files at 2, context at 3 — first to be truncated)
- Label includes provenance: `"[auto] auth_service_spec.md"`
- Skips files already added to the builder (dedup by path)
- Enforces `max_files` cap

### 3.11d — Flow Handler Wiring (Review Handlers Only for v1)

**Modify:** `flow/_review.py`

In both `ReviewSpecHandler.execute()` and `ReviewCodeHandler.execute()`,
after the review call returns:

```python
result = await reviewer.review_spec(context.spec_path, ...)

# 3.11: Scan LLM response for file mentions
_scan_and_store_mentions(result.raw_response, context)
```

`_scan_and_store_mentions()` calls `extract_mentions()`, then `_resolve_mentions()`,
then stores in `context.feedback["mention_scanner:resolved"]`.

**Note:** Mentions are stored for downstream steps but NOT injected into the
current review (which is single-shot). Downstream steps that build prompts
can pick up `context.feedback["mention_scanner:resolved"]` and call
`builder.add_mentioned_files(resolved)`.

### 3.11e — CLI Visibility (Logging Only for v1)

- When `--verbose` / `DEBUG` logging is active, log auto-detected mentions
- No CLI command changes for v1

**Backlog:** Add mention summary to `sw review` output in a future polish pass.

## File Changes Summary

| Action | File | What |
|--------|------|------|
| NEW | `llm/mention_scanner/__init__.py` | Re-exports |
| NEW | `llm/mention_scanner/scanner.py` | `extract_mentions()` — pure logic |
| NEW | `llm/mention_scanner/models.py` | `ResolvedMention` dataclass |
| NEW | `llm/mention_scanner/context.yaml` | Module metadata (archetype: pure-logic) |
| MODIFY | `llm/prompt_builder.py` | `add_mentioned_files()` method |
| MODIFY | `flow/_review.py` | `_scan_and_store_mentions()`, `_resolve_mentions()`, handler wiring |
| MODIFY | `tests/unit/flow/test_handlers_edge_cases.py` | Added `raw_response` to mock |
| NEW | `tests/unit/llm/mention_scanner/__init__.py` | Test package |
| NEW | `tests/unit/llm/mention_scanner/test_scanner.py` | Extraction tests |
| NEW | `tests/unit/llm/mention_scanner/test_models.py` | Model tests |

## Architecture

- `llm/mention_scanner/` — archetype: `pure-logic`, consumes: nothing, forbids: `loom/*`
- `extract_mentions()` is stateless text parsing — **no I/O**
- File resolution (I/O + boundary checks) happens in the handler layer, NOT in the scanner
- Scanner inherits `llm/context.yaml` forbids rules
- Workspace boundary enforcement prevents cross-service context leakage

## Known Architectural Bugs (to fix in near-term refactoring)

> [!WARNING]
> The following are architectural limitations that constrain this feature's v1 scope.
> They must be fixed to unlock the full value of mention detection.

| Bug | Impact on 3.11 | Fix |
|-----|----------------|-----|
| **Planner uses template strings, not PromptBuilder** | Cannot wire `add_mentioned_files()` into planner | Refactor Planner to use PromptBuilder (3.11-follow-up) |
| **Tool-use loop is adapter-internal** | Cannot inject mentions between tool rounds | Add callback hook to adapter's tool loop, or move loop to handler (3.11-follow-up) |

These are tracked in `architecture_reference.md` under Known Boundary Violations.

## Testing Strategy

- **Unit tests** for `extract_mentions()`: backtick paths, quoted paths, bare spec
  names, URL filtering, `__init__.py` filtering, dedup, large code block skip
- **Unit tests** for `ResolvedMention`: kind classification by extension and path
- **Unit tests** for `add_mentioned_files()`: priority 4 ordering, dedup, cap,
  interaction with existing blocks
- **Handler tests** for reviewer wiring: mock LLM response with mentions → verify
  `context.feedback["mention_scanner:resolved"]` populated
- **Boundary tests**: resolved files outside workspace roots are rejected

## Verification

```bash
python -m ruff check src/ tests/
python -m mypy src/
python -m pytest tests/unit/ --ignore=tests/unit/api -q
```
