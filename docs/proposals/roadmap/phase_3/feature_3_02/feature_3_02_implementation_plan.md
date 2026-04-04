# Feature 3.2: Constitution as First-Class Artifact — Implementation Plan

> **Date**: 2026-03-18 (v3 — all open questions resolved)
> **Status**: Proposal — awaiting final approval
> **Scope**: Constitution loading, injection into all LLM prompts, scaffold generation, CLI support
> **Out of scope**: Constitution enforcement (automated compliance checking — deferred to later)
> **Blueprint references**: [ORIGINS.md](../../../ORIGINS.md) § Spec Kit, § DMZ — study [`SOUL.md`](https://github.com/TheMorpheus407/the-dmz/blob/main/SOUL.md) and [`templates/constitution.md`](https://github.com/github/spec-kit/tree/main/templates)

---

## 1. Problem Statement

Currently, SpecWeaver's LLM prompts have no project-level context injection. When drafting, reviewing, or implementing:
- The LLM doesn't know the project's tech stack, architecture principles, or security invariants
- Different sessions may produce inconsistent code (one uses SQLite, another PostgreSQL)
- Non-negotiable constraints (deployment isolation, test coverage ≥ 70%) must be re-stated manually

`constitution_template.md` already exists in `docs/architecture/` with an 8-section template, but it's only documentation — nothing in the codebase reads or uses it.

## 2. Design Principles

### 2.1 Simple Layer Cake

Constitution is a **passive document** — a markdown file that gets loaded and injected into prompts. This feature does NOT:
- Parse the constitution into structured data
- Enforce constitution constraints algorithmically
- Validate that generated code complies with the constitution

It DOES:
- Load the constitution from a well-known path
- Inject it into every LLM prompt via `PromptBuilder`
- Scaffold a starter constitution during `sw init`
- Provide a CLI command to view/validate the constitution

> [!IMPORTANT]
> Enforcement (automatically checking that generated code follows the constitution) is a separate, future feature. This feature establishes the **plumbing** — get it in front of the LLM first.

### 2.2 Constitution Contract

| Property | Value |
|---|---|
| **File name** | `CONSTITUTION.md` (project root or service directory) |
| **Max size** | ≤ 5 KB default (configurable via project settings) |
| **Mutability** | Read-only for agents. Only HITL may modify. |
| **Format** | Markdown, following the template in `constitution_template.md` |
| **Prompt priority** | 0 (never truncated — same as instructions and reminders) |
| **Resolution** | Walk up from spec path → nearest `CONSTITUTION.md` wins (like `.gitignore`) |

### 2.3 Rendering Position in Prompt

```
<instructions>         ← existing (priority 0)
...
</instructions>

<constitution>         ← NEW (priority 0) — after instructions, before topology
The following are non-negotiable project constraints.
All generated output MUST comply with these rules.
If any instruction conflicts with the constitution, the constitution wins.

[constitution content]
</constitution>

<topology>             ← existing
...
```

Constitution goes after instructions (which say *what to do*) and before topology (which describes *the architecture*). This gives the LLM the project constraints before it sees the code structure.

---

## 3. Key Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | File lives at **project root** as `CONSTITUTION.md` | Visible, conventional (like `README.md`). Not hidden in `.specweaver/`. |
| 2 | Priority 0 (**never truncated**) | Constitution is ≤ 5KB. It's the most important context — cheaper to always include than to risk inconsistency. |
| 3 | **Graceful degradation** — no constitution = no error | Constitution is optional. Commands work without it (with a one-time CLI hint: "Tip: create a CONSTITUTION.md for better results"). |
| 4 | **No structured parsing** | The LLM reads it as markdown. We don't parse sections into a data model. Keeps it simple and template-flexible. |
| 5 | **Slimmed-down scaffold template** | Section headings + TODO placeholders (~1.5KB). Full guidance stays in `constitution_template.md` as reference. Same approach as `component_spec.md`. |
| 6 | **New `<constitution>` XML tag** with fixed preamble | Tag includes a non-negotiable preamble ("these constraints MUST be followed") so handlers don't need to re-state it. |
| 7 | **Direct injection in handlers** (no centralized helper) | Handlers call `find_constitution()` + `builder.add_constitution()` directly. See [architectural fit analysis](../../../../.gemini/antigravity/brain/5cf13f72-6d15-443a-b9c0-0a686e1d6a90/constitution_architectural_fit.md). |
| 8 | **Handler passes content string** to modules | Modules (Reviewer, Drafter, Generator) receive `constitution: str \| None` — they don't discover files. Matches topology pattern. |
| 9 | **Size: error on `check`, warning on load** | `sw constitution check` fails if over limit (CI gate). Runtime loading warns but proceeds. Limit configurable via project settings. |
| 10 | **Nearest constitution wins** (walk-up resolution) | In monorepos, service-level `CONSTITUTION.md` overrides root. No merging — child overrides parent entirely. Same pattern as `.gitignore`. |
| 11 | **`sw constitution show` lists all** | Without `--path`: shows all constitutions found in the project tree. With `--path`: shows specific one. |

---

## 4. Proposed Changes

### 4.1 Constitution Loader

#### [NEW] `src/specweaver/project/constitution.py`

```python
"""Constitution loader — find and read CONSTITUTION.md."""

CONSTITUTION_FILENAME = "CONSTITUTION.md"
DEFAULT_MAX_CONSTITUTION_SIZE = 5120  # 5 KB

class ConstitutionInfo:
    """Result of loading a constitution."""
    content: str       # raw markdown content
    path: Path         # absolute path to the file
    size: int          # file size in bytes
    is_override: bool  # True if not the root constitution

def find_constitution(
    project_path: Path,
    spec_path: Path | None = None,
    *,
    max_size: int = DEFAULT_MAX_CONSTITUTION_SIZE,
) -> ConstitutionInfo | None:
    """Find and load the nearest CONSTITUTION.md.

    Resolution order (walk-up from spec_path or project_path):
    1. spec_path's directory -> walk up to project_path
    2. Nearest CONSTITUTION.md wins (service overrides root)
    3. Returns None if no constitution exists.

    Size handling:
    - <= max_size: loaded normally
    - > max_size: loaded with WARNING logged (graceful)
    """

def find_all_constitutions(project_path: Path) -> list[ConstitutionInfo]:
    """Find all CONSTITUTION.md files in the project tree.

    Used by `sw constitution show` (no --path flag) to list
    root + all service-level constitutions.
    """

def check_constitution(
    path: Path,
    *,
    max_size: int = DEFAULT_MAX_CONSTITUTION_SIZE,
) -> list[str]:
    """Validate a constitution file. Returns list of errors.

    Raises errors (not warnings) for size violations.
    Used by `sw constitution check` as a CI gate.
    """

def generate_constitution(project_path: Path, project_name: str) -> Path:
    """Generate a starter CONSTITUTION.md from built-in template.

    Idempotent: does not overwrite existing file.
    Returns path to the (existing or new) file.
    """
```

Responsibility:
- Walk-up file resolution (nearest `CONSTITUTION.md` wins)
- Size validation (warning on load, error on check)
- Listing all constitutions in a project tree
- Template generation for `sw init`

---

### 4.2 PromptBuilder Extension

#### [MODIFY] `src/specweaver/llm/prompt_builder.py`

Add a new `add_constitution()` method and `<constitution>` rendering:

```python
_CONSTITUTION_PREAMBLE = (
    "The following are non-negotiable project constraints.\n"
    "All generated output MUST comply with these rules.\n"
    "If any instruction conflicts with the constitution, "
    "the constitution wins."
)

def add_constitution(self, text: str) -> PromptBuilder:
    """Add constitution text (priority 0 — never truncated).

    Constitution is rendered after instructions and before topology,
    inside <constitution> tags with a fixed preamble.
    """
    full_text = f"{_CONSTITUTION_PREAMBLE}\n\n{text.strip()}"
    self._blocks.append(
        _ContentBlock(
            text=full_text,
            priority=0,
            kind="constitution",
            tokens=self._count(full_text),
        ),
    )
    return self
```

In `_render()`, add between instructions and topology:

```python
# Constitution (after instructions, before topology)
constitutions = [b for b in blocks if b.kind == "constitution"]
if constitutions:
    text = "\n\n".join(b.text for b in constitutions)
    parts.append(f"<constitution>\n{text}\n</constitution>")
```

---

### 4.3 Handler Integration (Direct Injection)

All handlers that build LLM prompts load and inject the constitution **directly** — no centralized helper. This matches the existing pattern for topology injection.

> [!NOTE]
> **Why no centralized `enrich_builder()` helper?** It would create hidden coupling — every caller would implicitly depend on constitution + topology loading. Instead, each handler explicitly decides what to inject, keeping the pattern consistent with how `add_topology()` is already used. See Tension 1 in the [architectural fit analysis](../../../../.gemini/antigravity/brain/5cf13f72-6d15-443a-b9c0-0a686e1d6a90/constitution_architectural_fit.md).

Pattern for each handler:

```python
from specweaver.project.constitution import find_constitution

# Handler loads constitution, passes content to module
constitution = find_constitution(project_path, spec_path)
content = constitution.content if constitution else None

# Module receives content string (not path)
result = await reviewer.review_spec(
    spec_path,
    constitution=content,
    topology_contexts=topology_contexts,
)
```

#### [MODIFY] `src/specweaver/drafting/drafter.py`

Add `constitution: str | None = None` param to `_generate_section()`. Calls `builder.add_constitution(constitution)` when provided.

#### [MODIFY] `src/specweaver/drafting/feature_drafter.py`

Same pattern — `constitution: str | None` param, inject into builder.

#### [MODIFY] `src/specweaver/review/reviewer.py`

Both `review_spec()` and `review_code()` gain `constitution: str | None = None` param. Inject into builder when provided.

#### [MODIFY] `src/specweaver/implementation/generator.py`

Both `generate_code()` and `generate_tests()` gain `constitution: str | None = None` param. Inject into builder when provided.

#### [MODIFY] `src/specweaver/flow/handlers.py`

All handlers that build prompts (`DraftHandler`, `DraftFeatureHandler`, `ReviewSpecHandler`, `ReviewCodeHandler`, `ImplementHandler`) load constitution via `find_constitution(context.project_path, context.spec_path)` and pass `constitution.content` to the module. Project path and spec path are already available in `RunContext`.

---

### 4.4 Scaffold Integration

#### [MODIFY] `src/specweaver/project/scaffold.py`

Add constitution generation to `scaffold_project()`:

```python
# 5. CONSTITUTION.md (starter template, only if not present)
constitution_file = project_path / "CONSTITUTION.md"
if not constitution_file.exists():
    generate_constitution(project_path, project_name)
    created.append("CONSTITUTION.md")
```

Add `constitution_file: Path` to `ScaffoldResult`.

---

### 4.5 CLI Integration

#### [MODIFY] `src/specweaver/cli.py`

Add `sw constitution` command group:

```
sw constitution show              # List ALL constitutions in project tree
                                  # (root + service-level overrides)
sw constitution show --path svc/   # Show specific constitution (walk-up)
sw constitution check             # Validate all constitutions (CI gate)
sw constitution check --path svc/  # Validate specific one
sw constitution init              # Generate starter at project root
sw constitution init --path svc/   # Generate starter at service level
```

Example output for `sw constitution show`:
```
Constitutions found in trading-platform/:

  CONSTITUTION.md               3.2 KB  (root)
  billing-svc/CONSTITUTION.md   1.8 KB  (override)
  auth-svc/CONSTITUTION.md      2.1 KB  (override)

  analytics-svc/                (none — inherits root)
```

---

### 4.6 Per-Project Config (DB Migration)

#### [MODIFY] `src/specweaver/config/database.py`

Add schema v4 migration — same pattern as v3 (`log_level`):

```python
_SCHEMA_V4 = """\
ALTER TABLE projects ADD COLUMN constitution_max_size INTEGER NOT NULL DEFAULT 5120;
"""
```

Add `get_constitution_max_size()` / `set_constitution_max_size()` methods (same pattern as `get_log_level()` / `set_log_level()`).

#### [MODIFY] `src/specweaver/cli.py`

Add `sw update --constitution-max-size <bytes>` option to existing `sw update` command.

---

## 5. Template Content

The starter `CONSTITUTION.md` generated by `sw init` uses **section headings + TODO placeholders** (~1.5 KB). The full guidance notes remain in `docs/architecture/constitution_template.md` as a reference.

The template includes:
1. **Identity** — project name, purpose, domain
2. **Tech Stack** — technologies table
3. **Architecture Principles** — non-negotiable rules
4. **Coding Standards** — naming, error handling, docs
5. **Security Invariants** — security rules
6. **Prohibited Actions** — what agents must never do
7. **Key Documents Index** — navigation table
8. **Agent Instructions** — read order, conflict resolution

---

## 6. Verification Plan

### Regression

```bash
uv run pytest tests/ -x -q
```

All 1886+ tests must pass with zero regressions.

### New Tests

| Test File | Covers |
|---|---|
| `tests/unit/project/test_constitution.py` | `find_constitution()`: found, not found, walk-up resolution, service override, size warning on load. `find_all_constitutions()`: finds root + overrides. `check_constitution()`: size error. `generate_constitution()`: creates file, idempotent. |
| `tests/unit/llm/test_prompt_builder.py` (extend) | `add_constitution()`: renders in correct position (after instructions, before topology), priority 0, never truncated, preamble present. |
| `tests/unit/project/test_scaffold.py` (extend) | Scaffold now creates `CONSTITUTION.md`, idempotent. `ScaffoldResult.constitution_file`. |
| `tests/unit/cli/test_cli.py` (extend) | `sw constitution show` (all + `--path`), `sw constitution check` (pass + fail), `sw constitution init`. |
| `tests/unit/drafting/test_drafter.py` (extend) | Constitution content appears in built prompt when provided, absent when None. |
| `tests/unit/review/test_reviewer.py` (extend) | Constitution injected into review prompts when provided. |
| `tests/unit/implementation/test_generator.py` (extend) | Constitution injected into generation prompts when provided. |
| `tests/unit/flow/test_handlers.py` (extend) | Handlers load constitution from project path, pass to module. Walk-up resolution. |
| `tests/unit/config/test_database.py` (extend) | Schema v4 migration, `get/set_constitution_max_size()`. |
| `tests/integration/test_constitution_integration.py` | End-to-end: `sw init` creates constitution → `sw constitution show` lists it → prompts include `<constitution>` tag with preamble. |

### Expected test count increase: ~40-60 new tests.

### Manual Verification

1. `sw init my-app --path .` → now also creates `CONSTITUTION.md`
2. `sw constitution show` → lists all constitutions in project tree
3. `sw constitution check` → validates size and format
4. `sw draft greet_service` → prompt includes `<constitution>` section with preamble
5. `sw review spec some_spec.md` → prompt includes `<constitution>` section
6. `sw update --constitution-max-size 8192` → persists in DB

---

## 7. Documentation Updates

After implementation, update the following docs:

| Document | Update |
|---|---|
| `README.md` | Add constitution to feature list, mention `sw constitution` commands |
| `docs/quickstart.md` | Add step: "Create your constitution" after `sw init` |
| `docs/architecture/methodology_index.md` | Reference constitution as L0 artifact |
| `docs/architecture/lifecycle_layers.md` | Update L1 input to reference `CONSTITUTION.md` (currently says "SOUL.md / Constitution equivalent") |
| `CONTRIBUTING.md` | Mention constitution in "Getting Started" section |
| `docs/developer_guide.html` | Add constitution section if applicable |
