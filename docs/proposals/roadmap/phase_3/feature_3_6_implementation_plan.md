# Feature 3.6 — Explicit Plan Phase (Spec → Plan → Tasks)

Insert a structured **Plan** artifact between spec validation/review and code generation. The Plan captures architecture decisions, tech stack choices, file layout, constraint reasoning, and (optionally) UI mockups — before code generation begins.

> **Inspired by**: [Spec Kit](https://github.com/github/spec-kit) (`/specify → /plan → /tasks` workflow)
> **Optional enrichment**: [Google Stitch](https://stitch.withgoogle.com/) for web/UI mockup generation
> **Lifecycle position**: bridges L2 (Architecture) → L4 (Implementation) in [lifecycle_layers.md](../../architecture/lifecycle_layers.md)

> [!IMPORTANT]
> **Prerequisite**: Before starting 3.6, complete a separate cleanup task to extract hardcoded model defaults (`gemini-2.5-flash`) from 6 locations into the hierarchical LLM config system. See [Decision #13](#13-llm-model-selection).

---

## Motivation

Today, `generate_code` receives only the spec + constitution + standards. Architecture decisions (folder structure, which libraries to use, how to split modules) are implicit — the LLM guesses. This leads to:

- Inconsistent file layouts across generated modules
- Tech stack choices that conflict with project conventions
- No reviewable record of *why* the LLM chose a particular approach
- No opportunity for human review of architecture before code is written

The Plan phase inserts an explicit, reviewable artifact that becomes the blueprint for code generation — the LLM's "architectural thinking" becomes a first-class, auditable document.

---

## Core Concept: Plan Artifact

A **Plan** is a structured YAML document attached to a spec, capturing:

| Section | Purpose | Source |
|---------|---------|--------|
| **Architecture** | Module layout, dependency direction, archetype | LLM + topology context |
| **Tech Stack** | Libraries, frameworks, runtime constraints | LLM + constitution + standards |
| **File Layout** | Concrete files to create/modify with paths | LLM + project structure |
| **Constraints** | Non-functional requirements, boundaries | Extracted from spec § Boundaries |
| **Test Expectations** | Lightweight scenario hints (precursor to 3.17) | LLM from spec Contract/Policy |
| **UI Mockups** _(optional, 3.6b)_ | Stitch-generated interactive prototypes | Google Stitch MCP |

The Plan is stored as **YAML** (machine-first, agent-consumable). Markdown rendering is **optional** — generated only on explicit HITL request via `sw plan render <spec>`.

---

## Design Decisions

| # | Decision | Choice | Audit # |
|---|----------|--------|---------|
| 1 | **Generator interface** | Add `plan: str \| None = None` kwarg to `generate_code()`/`generate_tests()`. Same pattern as `constitution`/`standards`. | Q1 |
| 2 | **RunContext population** | Runner mutates `context.plan_path` after plan step completes (post-step hook in `runner.py`). | Q2 |
| 3 | **JSON validation** | Reflection retry inside `Planner`: LLM output → parse → validate against `PlanArtifact` schema → on failure, re-prompt with error feedback. Max 3 retries. | Q3 |
| 4 | **Storage format** | Primary: `{spec_stem}_plan.yaml` (structured YAML). Secondary: `{spec_stem}_plan.md` rendered on request only. No DB table in 3.6a (deferred). | Q6, Q17 |
| 5 | **File location** | Configurable via `plan_output_dir` DB setting. Default: next to the spec file (same directory). | Q5 |
| 6 | **New module** | `specweaver/planning/` — orchestrator. Consumes `llm`, `config`, `context` (for topology). | Q2, Q11 |
| 7 | **New StepAction** | `PLAN = "plan"` added to `StepAction`. Valid combination: `(PLAN, SPEC)`. | — |
| 8 | **Pipeline insertion** | `plan_spec` step between `review_spec` and `generate_code` in `new_feature.yaml`. **Always runs.** | Q7 |
| 9 | **HITL gate** | Confidence-gated: `confidence ≥ threshold` → auto-approve. `confidence < threshold` → force HITL review. Threshold configurable per project via DB. | Q7, Q19 |
| 10 | **Plan naming** | `{spec_stem}_plan.yaml` (not `_spec` stripping — plan is its own artifact type). | Q10 |
| 11 | **Staleness detection** | SHA-256 hash of spec content stored in plan's `spec_hash` field. On pipeline run: compare hash → mismatch triggers regeneration. | Q8 |
| 12 | **Plan-to-code injection** | Selective section injection: only `file_layout` + `architecture` + `tasks` + `test_expectations`. Skip `reasoning`, `constraints`, `tech_stack`, `mockups`. Both at priority 1 with standards — plan is kept compact. | Q12, Q31 |
| 13 | **LLM model selection** | Hierarchical config: CLI flag → project-role → global-role → system default. New `"plan"` role in `_DEFAULT_PROFILES`. **No hardcoded model names.** Prerequisite cleanup task removes all 6 hardcoded `gemini-2.5-flash` references. | Q13 |
| 14 | **Plan prompt context** | Spec (role=target) + constitution + standards + topology + project tree (2-level). No existing plans, no decomposition results. | Q14 |
| 15 | **Gate loop behavior** | On HITL rejection: re-prompt LLM with rejection reason + existing plan as feedback. Max 3 iterations. | Q27 |
| 16 | **Archetype validation** | Free-form string with warning for unknown archetypes (not a hard error). Known set: `adapter`, `orchestrator`, `pure-logic`, `leaf`, `data`. | Q29 |
| 17 | **File count warning** | Color-coded in CLI: green ≤5, yellow 6–15, red >15. Thresholds configurable via DB. | Q24 |
| 18 | **CLI command** | `sw plan <spec>` (matches `sw draft`, `sw review`, `sw check` pattern). | Q26 |
| 19 | **Reasoning** | Stored in YAML only. Omitted from rendered Markdown. Available via `sw plan show --verbose`. | Q18 |
| 20 | **Divergence handling** | Hash check: plan YAML stores spec_hash. On load, compare against current spec. Mismatch → warning. | Q25 |
| 21 | **Test fixtures** | Factory pattern (`make_plan(**overrides)`) + hand-crafted YAML edge cases. | Q32 |

---

## Sub-Phases

### Phase 3.6a: Core Planning Module + Pipeline Integration

**Goal**: End-to-end plan generation working in the `new_feature` pipeline. LLM generates a structured Plan artifact from spec + constitution + standards + topology.

| Component | Module | What |
|-----------|--------|------|
| `planning/models.py` | `planning/` | `PlanArtifact`, `ArchitectureSection`, `FileChange`, `TestExpectation` Pydantic models. |
| `planning/planner.py` | `planning/` | `Planner` class: spec + context → LLM call → validate → `PlanArtifact`. Includes `_validate_and_retry()` reflection loop (max 3). |
| `planning/renderer.py` | `planning/` | `render_plan_markdown(plan: PlanArtifact) → str` — on-demand Markdown rendering. |
| `planning/context.yaml` | `planning/` | Module manifest (archetype: orchestrator, consumes: llm, config, context). |
| `planning/__init__.py` | `planning/` | Module init, public exports. |
| `flow/models.py` | `flow/` | Add `PLAN = "plan"` to `StepAction`, add `(PLAN, SPEC)` to `VALID_STEP_COMBINATIONS`. |
| `flow/handlers.py` | `flow/` | New `PlanSpecHandler`: LLM plan generation → validate → save YAML → StepResult. Add `plan_path: Path \| None = None` to `RunContext`. Register `(PLAN, SPEC)` in `StepHandlerRegistry`. |
| `flow/runner.py` | `flow/` | Post-step hook: after `PLAN` step completes, set `context.plan_path` from `StepResult.output["plan_path"]`. |
| `pipelines/new_feature.yaml` | `pipelines/` | Insert `plan_spec` step between `review_spec` and `generate_code`, with confidence-gated HITL. |
| `implementation/generator.py` | `implementation/` | Add `plan: str \| None = None` kwarg to `generate_code()` and `generate_tests()`. Call `builder.add_plan(plan)` when provided. |
| `llm/prompt_builder.py` | `llm/` | New `add_plan()` method → `_ContentBlock(kind="plan", priority=1)`. Render `<plan>` block after standards, before topology. |
| `cli/plan.py` | `cli/` | New `sw plan <spec>` command: standalone plan generation with Rich output. `sw plan show`, `sw plan clear`, `sw plan render`. |
| `cli/_helpers.py` | `cli/` | `_load_plan_content(project_path, spec_path)` — reads YAML, extracts `file_layout` + `architecture` + `tasks` + `test_expectations` only. |
| `context.yaml` (root) | root | Add `planning` to exposes list. |

**Tests**: ~80-100 unit + integration tests.
**Deliverable**: `sw plan my_spec.md` generates a structured Plan YAML, `sw run new_feature` includes plan step with confidence-gated HITL, code generation uses Plan as context.

---

### Phase 3.6b: Google Stitch Integration _(optional)_

**Goal**: For specs describing web/UI components, auto-generate interactive mockups via Google Stitch MCP server and attach preview URLs to the Plan artifact.

| Component | Module | What |
|-----------|--------|------|
| `planning/stitch.py` | `planning/` | `StitchClient` wrapper: MCP server connection. `generate_mockup(ui_description: str) → MockupResult`. Pluggable interface (MCP first, direct API fallback). |
| `planning/ui_extractor.py` | `planning/` | `extract_ui_requirements(spec_content: str) → UIRequirements \| None` — parses spec Protocol/Contract for UI flows. Returns `None` for non-UI specs. |
| `planning/models.py` | `planning/` | `MockupReference(screen_name, description, preview_url)`. |
| Stitch config | `config/` | `STITCH_API_KEY` environment variable. `stitch_mode` DB setting: `auto\|prompt\|off` (default: `off`). |

> [!IMPORTANT]
> Stitch integration is **conditional**: only fires when spec has UI sections AND `STITCH_API_KEY` env var is set AND `stitch_mode != off`. Non-UI specs skip entirely. Missing SDK = graceful skip with log warning. **No new package dependencies** — MCP communication uses existing infrastructure.

**Tests**: ~20-30 tests (mocked MCP calls, UI extraction from spec samples).

---

## Proposed Changes (Detailed)

### New Module: `planning/`

> **New module**: `specweaver/planning/` — self-contained orchestrator for plan generation.
> Consumes `specweaver/llm`, `specweaver/config`, `specweaver/context`. Forbidden: `specweaver/loom/*`.

#### [NEW] [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/planning/context.yaml)

```yaml
name: planning
level: module
purpose: >
  LLM-assisted implementation planning from approved specs.
  Generates structured Plan artifacts (YAML) with architecture decisions,
  tech stack choices, file layout, and constraint reasoning.

archetype: orchestrator

consumes:
  - specweaver/llm
  - specweaver/config
  - specweaver/context

forbids:
  - specweaver/loom/*

exposes:
  - Planner
  - PlanArtifact
  - render_plan_markdown

operational:
  async_ready: true
  concurrency_model: none
```

#### [NEW] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/planning/models.py)

```python
KNOWN_ARCHETYPES = {"adapter", "orchestrator", "pure-logic", "leaf", "data"}

class FileChange(BaseModel):
    """A single file to create or modify."""
    path: str                                        # e.g. "src/auth/login.py"
    action: Literal["create", "modify", "delete"]
    purpose: str
    dependencies: list[str] = []

class ArchitectureSection(BaseModel):
    """Architecture decisions for the Plan."""
    module_layout: str
    dependency_direction: str
    archetype: str  # free-form, warn if not in KNOWN_ARCHETYPES
    patterns: list[str] = []

class TechStackChoice(BaseModel):
    """A technology choice with rationale."""
    category: str
    choice: str
    rationale: str
    alternatives_considered: list[str] = []

class ConstraintNote(BaseModel):
    """A constraint extracted from the spec."""
    source: str
    constraint: str
    impact: str

class ImplementationTask(BaseModel):
    """An ordered implementation step."""
    name: str
    description: str
    files: list[str]
    dependencies: list[str] = []

class TestExpectation(BaseModel):
    """Lightweight test scenario hint (precursor to full 3.17 scenarios)."""
    name: str                    # "happy_path_login"
    description: str             # "Valid credentials → returns token"
    function_under_test: str     # "authenticate()"
    input_summary: str           # "valid email + password"
    expected_behavior: str       # "returns JWT token"
    category: Literal["happy", "error", "boundary"] = "happy"

class MockupReference(BaseModel):
    """Reference to a UI mockup (populated by Stitch in 3.6b)."""
    screen_name: str
    description: str
    preview_url: str             # Stitch preview URL

class PlanArtifact(BaseModel):
    """Complete implementation plan for a spec."""
    # === MANDATORY ===
    spec_path: str
    spec_name: str
    spec_hash: str               # SHA-256 for staleness detection
    file_layout: list[FileChange]
    timestamp: str               # ISO-8601

    # === OPTIONAL ===
    architecture: ArchitectureSection | None = None
    tech_stack: list[TechStackChoice] = []
    constraints: list[ConstraintNote] = []
    tasks: list[ImplementationTask] = []
    test_expectations: list[TestExpectation] = []
    mockups: list[MockupReference] = []
    reasoning: str = ""          # LLM chain-of-thought (YAML only, omit from Markdown)
    confidence: int = 0          # 0-100
```

#### [NEW] [planner.py](file:///c:/development/pitbula/specweaver/src/specweaver/planning/planner.py)

```python
class Planner:
    """Generate structured implementation plans from approved specs.

    Uses PromptBuilder to assemble context (spec + constitution + standards +
    topology + project tree) and requests a structured PlanArtifact from the LLM.
    Includes reflection retry for JSON validation failures.
    """
    def __init__(self, llm: LLMAdapter) -> None: ...

    async def generate_plan(
        self,
        spec_path: Path,
        project_path: Path,
        *,
        topology_contexts: list[TopologyContext] | None = None,
        constitution: str | None = None,
        standards: str | None = None,
        existing_plan: PlanArtifact | None = None,  # for re-planning with feedback
        feedback: str | None = None,                 # HITL rejection reason
    ) -> PlanArtifact: ...

    def _build_prompt(self, spec_content: str, ...) -> str: ...

    def _validate_and_retry(
        self, raw_text: str, *, max_retries: int = 3
    ) -> PlanArtifact:
        """Parse LLM output as JSON, validate against PlanArtifact schema.
        On failure, re-prompt with error feedback (reflection pattern).
        """
```

Prompt structure:
```
<instructions>
  Planning instructions + PlanArtifact JSON schema
</instructions>
<constitution>...</constitution>
<standards>...</standards>
<plan>...</plan>              ← only on re-planning with feedback
<topology>...</topology>
<file path="spec.md" role="target">...</file>
<context label="project_tree">
  2-level project directory tree
</context>
```

#### [NEW] [renderer.py](file:///c:/development/pitbula/specweaver/src/specweaver/planning/renderer.py)

```python
def render_plan_markdown(plan: PlanArtifact) -> str:
    """Render a PlanArtifact as human-readable Markdown (on-demand only).

    Sections: Architecture, Tech Stack, File Layout, Constraints,
    Implementation Tasks, Test Expectations, UI Mockups (if any).
    Reasoning is OMITTED (available via sw plan show --verbose).
    """
```

---

### Flow Engine Changes

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/models.py)

```diff
 class StepAction(enum.StrEnum):
     DRAFT = "draft"
     VALIDATE = "validate"
     REVIEW = "review"
     GENERATE = "generate"
     LINT_FIX = "lint_fix"
     DECOMPOSE = "decompose"
+    PLAN = "plan"
```

```diff
 VALID_STEP_COMBINATIONS: frozenset[tuple[StepAction, StepTarget]] = frozenset(
     {
         ...existing entries...
+        (StepAction.PLAN, StepTarget.SPEC),
     }
 )
```

#### [MODIFY] [handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/handlers.py)

Add `plan_path` to `RunContext`:

```diff
 class RunContext(BaseModel):
     ...
     constitution: str | None = None
     standards: str | None = None
+    plan_path: Path | None = None
```

New `PlanSpecHandler`:

```python
class PlanSpecHandler:
    """Handler for plan+spec — LLM-based implementation planning.

    On first run: generates plan YAML from spec + context.
    On loop (HITL rejection): re-generates with feedback.
    Skips if plan exists and spec hash matches (not stale).
    """
    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        # 1. Check for existing plan + staleness (spec_hash)
        # 2. If stale or force: regenerate with feedback
        # 3. If fresh: skip
        # 4. If new: generate from scratch via Planner
        # 5. Save YAML to disk
        # 6. Return StepResult with plan_path + confidence
```

Register in `StepHandlerRegistry`:

```diff
+    (StepAction.PLAN, StepTarget.SPEC): PlanSpecHandler(),
```

#### [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/runner.py)

Post-step hook — propagate plan_path to RunContext:

```python
# After step execution, update context for downstream steps
if step.action == StepAction.PLAN and result.status == StepStatus.PASSED:
    plan_path = result.output.get("plan_path")
    if plan_path:
        context.plan_path = Path(plan_path)
```

---

### Pipeline Changes

#### [MODIFY] [new_feature.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/pipelines/new_feature.yaml)

```diff
   - name: review_spec
     action: review
     target: spec
     ...

+  - name: plan_spec
+    action: plan
+    target: spec
+    description: "Generate implementation plan from approved spec"
+    gate:
+      type: hitl
+      condition: completed
+      on_fail: loop_back
+      loop_target: plan_spec
+      max_retries: 3

   - name: generate_code
     action: generate
     target: code
     ...
```

The gate fires after plan generation. Behavior depends on confidence:
- `confidence ≥ threshold` → auto-approve (skip HITL)
- `confidence < threshold` → HITL reviews plan
- On rejection: re-prompt LLM with rejection reason + existing plan (Option C loop)

---

### Implementation Module Changes

#### [MODIFY] [generator.py](file:///c:/development/pitbula/specweaver/src/specweaver/implementation/generator.py)

Add `plan` kwarg to both methods:

```diff
 async def generate_code(
     self,
     spec_path: Path,
     output_path: Path,
     *,
     topology_contexts: list[TopologyContext] | None = None,
     constitution: str | None = None,
     standards: str | None = None,
+    plan: str | None = None,
 ) -> Path:
```

Inside the method:
```python
if plan:
    builder.add_plan(plan)
    logger.debug("generate_code: plan injected (%d chars)", len(plan))
```

Same change for `generate_tests()`.

---

### PromptBuilder Enhancement

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/prompt_builder.py)

New `add_plan()` method:

```python
def add_plan(self, text: str) -> PromptBuilder:
    """Add plan context (priority 1 — truncatable).

    Plans are rendered after standards, before topology,
    inside ``<plan>`` tags.
    """
    self._blocks.append(
        _ContentBlock(
            text=text.strip(),
            priority=1,
            kind="plan",
            tokens=self._count(text),
        ),
    )
    return self
```

Rendering order in `_render()`: instructions → constitution → standards → **plan** → topology → files → context → reminders.

---

### CLI

#### [NEW] [plan.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/plan.py)

```python
plan_app = typer.Typer(name="plan", help="Generate and manage implementation plans.")

@plan_app.command()  # default command: sw plan <spec>
def plan_generate(spec: str, project: str = ..., force: bool = False):
    """Generate an implementation plan from a spec."""
    # 1. Load spec, constitution, standards, topology
    # 2. Call Planner.generate_plan()
    # 3. Save YAML to configured location
    # 4. Display Rich summary with color-coded file count

@plan_app.command("show")
def plan_show(spec: str, project: str = ..., verbose: bool = False):
    """Display the plan for a spec. Use --verbose to include reasoning."""

@plan_app.command("render")
def plan_render(spec: str, project: str = ...):
    """Render plan as Markdown (for HITL review)."""

@plan_app.command("clear")
def plan_clear(spec: str = None, project: str = ...):
    """Clear plan(s) from disk."""
```

File count warning in Rich output:
- `≤ 5 files` → `[green]Simple[/green]`
- `6–15 files` → `[yellow]Moderate[/yellow]`
- `> 15 files` → `[red]Consider splitting[/red]`

Thresholds configurable via DB: `plan_file_warning_yellow` (default: 6), `plan_file_warning_red` (default: 16).

#### [MODIFY] [_helpers.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/_helpers.py)

```python
def _load_plan_content(project_path: Path, spec_path: Path) -> str | None:
    """Load plan YAML, extract only agent-relevant sections for prompt injection.

    Includes: file_layout, architecture, tasks, test_expectations
    Excludes: reasoning, constraints, tech_stack, mockups, confidence
    """
    plan_path = _resolve_plan_path(project_path, spec_path)
    if plan_path is None or not plan_path.is_file():
        return None
    # Parse YAML, extract relevant sections, serialize as compact YAML
```

---

### System-Level Context

#### [MODIFY] [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/context.yaml)

```diff
 exposes:
   ...
   - flow
   - pipelines
+  - planning
```

---

## Architecture Validation

| Module | Archetype | Boundary Respected? |
|--------|-----------|---------------------|
| `planning/` | orchestrator, consumes llm + config + context | ✅ Same pattern as `drafting/` (which also consumes `context`) |
| `flow/` | orchestrator | ✅ New handler follows existing protocol. Runner change is minimal (post-step hook). |
| `implementation/` | adapter, consumes llm + config | ✅ New `plan` kwarg follows `constitution`/`standards` pattern |
| `llm/` | adapter | ✅ New `add_plan()` follows `add_constitution()`/`add_standards()` pattern |
| `cli/` | orchestrator | ✅ New `plan_app` Typer group follows `standards_app` pattern |
| `pipelines/` | data | ✅ YAML-only change, new step uses new action+target |

---

## Resolved Decisions (from audit)

All 32 audit questions have been resolved. Key resolutions:

| Category | Resolution |
|----------|------------|
| **Storage** | YAML primary, Markdown on demand. No DB in 3.6a. File location configurable (default: next to spec). |
| **Pipeline** | Plan always runs. HITL confidence-gated. On rejection: re-prompt with feedback (max 3 iterations). |
| **LLM** | Hierarchical model config. New `"plan"` role. No hardcoded defaults. Reflection retry for JSON validation. |
| **Token budget** | Selective section injection (file_layout + architecture + tasks + test_expectations). Both plan and standards at priority 1. |
| **Staleness** | SHA-256 spec hash stored in plan. Mismatch → regeneration. |
| **HITL UX** | V1: generate → display → accept/reject with feedback loop. V2 (future): interactive editing. |
| **Stitch** | MCP server, preview URL links, env var for API key. |
| **3.6c** | Removed — DECOMPOSE action doesn't exist. Task decomposition deferred to roadmap (3.13/3.18). |

---

## New Dependencies

| Package | Phase | Why |
|---------|-------|-----|
| _(none for 3.6a)_ | 3.6a | All existing deps sufficient |

---

## Verification Plan

**Total: ~100-130 tests across 2 sub-phases.**

| Sub-phase | Unit | Integration | Edge |
|-----------|------|-------------|------|
| 3.6a | ~50 | ~20 | ~10 |
| 3.6b | ~15 | ~10 | ~5 |

### Automated Tests

**Unit tests (`tests/unit/planning/`):**
- `PlanArtifact` model validation (mandatory fields, optional fields, defaults)
- `FileChange`, `ArchitectureSection`, `TestExpectation` model validation
- Archetype warning for unknown values (not error)
- `render_plan_markdown()` output (all sections, empty optionals, verbose mode)
- `Planner._build_prompt()` includes all context types
- `Planner._validate_and_retry()` — valid JSON, invalid JSON, retry exhaustion
- `PlanSpecHandler` skip logic (plan exists + hash matches → skip, hash mismatch → regenerate, force → regenerate)
- `PlanSpecHandler` feedback loop (rejection reason → re-prompt)
- `PlanSpecHandler` LLM error handling
- `StepAction.PLAN` in `VALID_STEP_COMBINATIONS`
- `StepHandlerRegistry` returns `PlanSpecHandler` for `(PLAN, SPEC)`
- `_load_plan_content()` — selective section extraction, file missing, file present
- `add_plan()` on `PromptBuilder` — block creation, rendering position, priority
- Generator `plan` kwarg — with plan, without plan, plan + standards
- File count warning thresholds
- Spec hash computation and comparison

**Fixture strategy:**
- `tests/fixtures/planning.py`: `make_plan(**overrides)` factory returning valid `PlanArtifact`
- `tests/fixtures/plans/`: 3-4 hand-crafted YAML plan files for integration tests

**Integration tests (`tests/integration/`):**
- `sw plan my_spec.md` CLI command (end-to-end with mocked LLM)
- `sw plan show` / `sw plan clear` / `sw plan render` CLI round-trip
- Pipeline execution: `new_feature.yaml` with plan step (mocked LLM, verify step order)
- Plan injection into `GenerateCodeHandler` prompt (verify `<plan>` block)
- Runner post-step hook: verify `context.plan_path` is set after plan step
- Staleness detection: modify spec → plan regeneration triggered
- Confidence-gated HITL: high confidence → auto-approve, low → force HITL

**Commands:**
```bash
uv run pytest tests/unit/planning/ -x -q
uv run pytest tests/integration/planning/ -x -q
uv run pytest --tb=short -q          # full regression
uv run ruff check src/ tests/
uv run mypy src/
```

### Manual Verification

1. `sw plan specs/example_spec.md` → verify YAML saved, Rich summary with color-coded file count
2. `sw plan show specs/example_spec.md` → verify plan display
3. `sw plan render specs/example_spec.md` → verify Markdown generation
4. `sw run new_feature example_spec` → verify pipeline includes plan step, confidence gate works
5. Edit spec after plan → re-run → verify staleness detection triggers regeneration
6. Reject plan in HITL → verify re-prompt with feedback

---

## Documentation Updates

| Doc | What to add |
|-----|-------------|
| `README.md` | Features bullet for "Implementation Planning", CLI table for `sw plan`, project structure for `planning/` |
| `docs/quickstart.md` | New section: "Generate an Implementation Plan" |
| `docs/test_coverage_matrix.md` | New rows for planning tests |
| `docs/proposals/roadmap/phase_3_feature_expansion.md` | Mark 3.6a done when complete |
| `docs/architecture/lifecycle_layers.md` | Annotate Plan as L2→L4 bridge artifact |
| `docs/architecture/context_yaml_spec.md` | Add `planning/` module |
| `docs/architecture/methodology_index.md` | Reference planning phase |
| `developer_guide.html` | Planning section |

---

## File Map Summary

### New Files

| File | Module | Purpose |
|------|--------|---------|
| `planning/__init__.py` | planning | Module init |
| `planning/context.yaml` | planning | Module manifest |
| `planning/models.py` | planning | PlanArtifact + supporting models |
| `planning/planner.py` | planning | Planner service (LLM plan generation + validation retry) |
| `planning/renderer.py` | planning | On-demand Markdown rendering |
| `planning/stitch.py` _(3.6b)_ | planning | Stitch MCP client |
| `planning/ui_extractor.py` _(3.6b)_ | planning | UI requirement extraction |
| `cli/plan.py` | cli | CLI commands |
| `tests/unit/planning/` | tests | Unit tests |
| `tests/integration/planning/` | tests | Integration tests |
| `tests/fixtures/planning.py` | tests | Plan factory fixture |
| `tests/fixtures/plans/` | tests | Hand-crafted YAML plan fixtures |

### Modified Files

| File | Change |
|------|--------|
| `flow/models.py` | Add `PLAN` to `StepAction`, add valid combination |
| `flow/handlers.py` | Add `PlanSpecHandler`, `plan_path` on `RunContext`, update registry |
| `flow/runner.py` | Post-step hook: propagate `plan_path` to `RunContext` |
| `pipelines/new_feature.yaml` | Insert `plan_spec` step with confidence-gated HITL |
| `implementation/generator.py` | Add `plan: str \| None` to `generate_code()` and `generate_tests()` |
| `llm/prompt_builder.py` | Add `add_plan()` method + `<plan>` rendering block |
| `cli/_helpers.py` | `_load_plan_content()` with selective section extraction |
| `context.yaml` (root) | Add `planning` to exposes list |
