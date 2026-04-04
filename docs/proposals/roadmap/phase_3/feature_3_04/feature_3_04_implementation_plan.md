# Feature 3.4: Custom Rule Paths — Implementation Plan

> **Date**: 2026-03-19
> **Status**: Proposal — awaiting approval
> **Scope**: Refactor rules into registry-based composable architecture (Phase A), then add custom rules + validation pipeline YAMLs (Phase B)
> **Source doc**: [phase_3_feature_expansion.md](../phase_3_feature_expansion.md)

---

## 1. Problem Statement

Today, all 19 validation rules (S01-S11, C01-C08) are **hardcoded** via direct imports in [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/runner.py#L94-L118). Users cannot:
- Add domain-specific custom rules without modifying SpecWeaver source
- Choose which rules to run per project
- Configure rule thresholds at the pipeline level
- Share validation rule sets across teams

Domain profiles (Feature 3.3) introduced per-project threshold calibration, but thresholds are stored in a separate DB layer. The long-term model is a **single source of truth**: validation pipeline YAMLs that define both which rules run and their configuration.

---

## 2. Analysis

### Current rule loading

```
get_spec_rules() → hardcoded imports → [S01, S02, ..., S11]
get_code_rules() → hardcoded imports → [C01, C02, ..., C08]
         ↓
ValidateSpecHandler / ValidateCodeHandler calls these functions
         ↓
run_rules(rules, text, path) → [RuleResult, ...]
```

### Two pipeline levels

The existing pipeline system operates at two levels:

```
Orchestration pipeline (PipelineDefinition / PipelineStep)
  draft → validate → review → generate → ...
                ↓
  ValidateSpecHandler internally runs all rules
                ↓
Validation sub-pipeline (NEW — ValidationPipeline / ValidationStep)
  S01 → S02 → S06 → S05 → S08 → D01 → ...
```

- **Orchestration level**: `PipelineStep` requires `action: StepAction` + `target: StepTarget`, dispatched via `StepHandlerRegistry`. This level stays unchanged.
- **Validation level**: A sub-pipeline **internal to the handler**. Each step is a rule-atom: its action is always "check", its target is the spec/code being validated. This level gets a new, simpler model.

### Rule as atom

Rules ARE validation atoms — their action is always "check" on a target (file/folder). The `Rule` ABC is already the right interface. A `RuleAtom` adapter bridges `Rule.check()` to `Atom.run()` so rule-atoms are composable like any other atom.

| | Rule ABC | Atom ABC |
|-|----------|----------|
| **File** | [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/models.py#L58-L128) | [base.py](file:///c:/development/pitbula/specweaver/src/specweaver/loom/atoms/base.py#L41-L65) |
| **Method** | `check(text, path) → RuleResult` | `run(context) → AtomResult` |
| **Config** | Constructor kwargs (thresholds) | `context` dict |

### Existing `step.params` infrastructure

[PipelineStep.params](file:///c:/development/pitbula/specweaver/src/specweaver/flow/models.py#L138) already carries `dict[str, Any]`. Handlers read it today. The validation sub-pipeline uses the same pattern — each rule step carries its own `params`.

---

## 3. Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Two phases**: A (registry refactoring) then B (custom rules + pipelines) | Phase A is risk-free internal refactoring. Phase B adds functionality on a solid foundation. |
| 2 | **Profiles → pipeline YAMLs** | Single source of truth. Profile = named validation pipeline YAML with thresholds baked in. |
| 3 | **Pipeline inheritance**: `extends` / `override` / `remove` / `add` | Avoids copy-pasting 11 rules to change one threshold. |
| 4 | **`after` / `before` placement** on `add` | Ordering matters (cheap rules first). `add` without placement appends at end. |
| 5 | **Load once, reuse** | Pipeline YAML parsed at startup, cached for the run. Invalidated on file change. |
| 6 | **`D\d{2,3}` prefix** for custom rule IDs | Prevents collision with built-in `S*`/`C*` rules. |
| 7 | **`try/except` per rule load** | Broken custom rule ≠ broken validation run. Log, skip, continue. |
| 8 | **Common + local pipelines** | SpecWeaver ships defaults; projects override in `.specweaver/pipelines/`. |
| 9 | **Pass `step.params` to atoms** | Generic improvement: all atoms get step-level config, not just rules. |
| 10 | **Sub-pipeline, not orchestration steps** | Validation pipeline is internal to `ValidateSpecHandler`. Own model (`ValidationStep` / `ValidationPipeline`), not `PipelineStep`. Keeps orchestration layer unchanged. |

---

## 4. Proposed Changes — Phase A (3.4a)

> **Goal**: Registry-based rule loading. Same public API, all tests keep working.

---

### 4.1 Rule Registry

#### [NEW] `src/specweaver/validation/registry.py`

```python
"""Rule registry — maps rule IDs to Rule classes.

Central registry for all validation rules (built-in and custom).
Rules register themselves; the runner queries the registry instead
of using hardcoded imports.
"""

class RuleRegistry:
    """Maps rule_id → Rule class + metadata."""

    def register(self, rule_id: str, rule_class: type[Rule],
                 category: Literal["spec", "code"]) -> None:
        """Register a rule class. Raises on duplicate ID.
        Custom rules must use D-prefix; S*/C* reserved for built-ins."""

    def get(self, rule_id: str) -> type[Rule] | None:
        """Get a rule class by ID."""

    def list_spec(self) -> list[tuple[str, type[Rule]]]:
        """All registered spec rules, sorted by ID."""

    def list_code(self) -> list[tuple[str, type[Rule]]]:
        """All registered code rules, sorted by ID."""

    def list_all(self) -> list[tuple[str, type[Rule], str]]:
        """All rules: (id, class, category)."""

# Module-level singleton
_registry = RuleRegistry()

def get_registry() -> RuleRegistry:
    """Get the global rule registry."""
    return _registry
```

---

### 4.2 Runner Refactoring

#### [MODIFY] `src/specweaver/validation/runner.py`

Replace hardcoded imports with registry queries:

```diff
 def get_spec_rules(*, include_llm=False, settings=None,
                    run_all=False, kind=None) -> list[Rule]:
-    from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule
-    from specweaver.validation.rules.spec.s02_single_setup import SingleSetupRule
-    # ... 9 more imports
-
-    rule_classes = [("S01", OneSentenceRule), ("S02", SingleSetupRule), ...]
+    from specweaver.validation.registry import get_registry
+    rule_classes = get_registry().list_spec()

     # Rest of the function unchanged — _build_rule_kwargs, is_enabled,
     # kind presets, etc. all work the same way.
```

Same change for `get_code_rules()`.

---

### 4.3 Built-In Rule Registration

#### [MODIFY] `src/specweaver/validation/rules/spec/__init__.py` and `code/__init__.py`

Register built-in rules at import time:

```python
# validation/rules/spec/__init__.py
from specweaver.validation.registry import get_registry

from .s01_one_sentence import OneSentenceRule
from .s02_single_setup import SingleSetupRule
# ... all 11

_reg = get_registry()
_reg.register("S01", OneSentenceRule, "spec")
_reg.register("S02", SingleSetupRule, "spec")
# ... all 11
```

Runner's `get_spec_rules()` triggers the import of this `__init__.py` to ensure rules are registered before querying.

---

## 5. Proposed Changes — Phase B (3.4b)

> **Goal**: Custom rules, validation sub-pipeline YAMLs, inheritance, per-project selection.

---

### 5.1 Validation Sub-Pipeline Model

#### [NEW] `src/specweaver/validation/pipeline.py`

A simpler model than `PipelineStep` — specific to validation rule composition:

```python
"""Validation pipeline models — defines which rules run and their config.

This is a sub-pipeline internal to validation handlers. It does NOT use
the orchestration PipelineStep/PipelineDefinition models. Each step is
a rule-atom: action is always 'check', target is the spec/code.
"""

class ValidationStep(BaseModel):
    """A single rule in the validation sub-pipeline."""
    name: str                                # e.g. "s01_one_sentence"
    rule: str                                # rule_id, e.g. "S01" or "D01"
    params: dict[str, Any] = Field(default_factory=dict)  # thresholds, config
    path: str | None = None                  # custom rule path (D-prefix only)

class ValidationPipeline(BaseModel):
    """A named set of rules with ordering and configuration."""
    name: str
    description: str = ""
    version: str = "1.0"
    steps: list[ValidationStep]

    # Inheritance fields (resolved before use)
    extends: str | None = None
    override: dict[str, dict] | None = None  # step_name → {params: {...}}
    remove: list[str] | None = None          # step_names to drop
    add: list[dict] | None = None            # new steps with optional after/before
```

---

### 5.2 Custom Rule Loader

#### [NEW] `src/specweaver/validation/loader.py`

```python
"""Dynamic rule loader — discovers custom Rule subclasses from external paths.

Uses importlib to load .py files from registered directories,
finds Rule subclasses, validates D-prefix, and registers them.
"""

def load_rules_from_directory(directory: Path) -> list[str]:
    """Scan directory for .py files, load Rule subclasses, register them.

    Returns list of loaded rule_ids.
    Wraps each file load in try/except — broken file skips, doesn't crash.
    Validates D-prefix on all discovered rule_ids.
    """

def load_rules_from_paths(paths: list[Path]) -> list[str]:
    """Load from multiple directories."""
```

---

### 5.3 RuleAtom Adapter

#### [NEW] `src/specweaver/loom/atoms/rule_atom.py`

```python
"""RuleAtom — adapts a validation Rule to the Atom interface.

Bridges Rule.check(text, path) → Atom.run(context) so rules
are composable like any other atom in the sub-pipeline.
"""

class RuleAtom(Atom):
    def __init__(self, rule: Rule) -> None:
        self._rule = rule

    def run(self, context: dict[str, Any]) -> AtomResult:
        result = self._rule.check(
            context["spec_text"], context.get("spec_path"),
        )
        return AtomResult(
            status=AtomStatus.SUCCESS if result.status != Status.FAIL
                   else AtomStatus.FAILED,
            message=f"{result.rule_id}: {result.message}",
            exports={"rule_result": result},
        )
```

---

### 5.4 Validation Sub-Pipeline Executor

#### [NEW] `src/specweaver/validation/executor.py`

Runs the sub-pipeline: loads YAML, resolves inheritance, instantiates rules from registry, executes in order:

```python
"""Validation sub-pipeline executor.

Loads a ValidationPipeline YAML, resolves inheritance, looks up rules
from the registry, passes step.params as constructor kwargs, and runs
each rule-atom in order. Returns aggregated [RuleResult] list.
"""

def load_validation_pipeline(category: str, project_path: Path | None) -> ValidationPipeline:
    """Load and resolve a validation pipeline.

    Resolution order:
    1. Project-local .specweaver/pipelines/validation_{category}.yaml
    2. Common default pipelines/validation_{category}_default.yaml

    Resolves extends/override/remove/add into flat step list.
    Caches result for reuse within a single run.
    """

def execute_validation_pipeline(
    pipeline: ValidationPipeline,
    spec_text: str,
    spec_path: Path | None = None,
    settings: ValidationSettings | None = None,
) -> list[RuleResult]:
    """Execute a validation pipeline against spec content.

    For each step:
    1. Look up rule class from registry via step.rule
    2. Instantiate with step.params as kwargs
    3. Wrap in try/except (broken rule = skip, logged)
    4. Collect RuleResult
    """
```

---

### 5.5 Validation Pipeline YAMLs

#### [NEW] `src/specweaver/pipelines/validation_spec_default.yaml`

```yaml
name: validation_spec_default
description: >
  Default spec validation — all 11 built-in rules.
  Ordered cheap-to-expensive for fail-fast behavior.
version: "1.0"

steps:
  - name: s01_one_sentence
    rule: S01
    params: { warn_conjunctions: 1, fail_conjunctions: 2, max_h2: 8 }
  - name: s02_single_setup
    rule: S02
  - name: s06_concrete_example
    rule: S06
  - name: s09_error_path
    rule: S09
  - name: s10_done_definition
    rule: S10
  - name: s04_dependency_dir
    rule: S04
  - name: s05_day_test
    rule: S05
    params: { warn_threshold: 30, fail_threshold: 60 }
  - name: s08_ambiguity
    rule: S08
    params: { warn_threshold: 3, fail_threshold: 8 }
  - name: s11_terminology
    rule: S11
  - name: s03_stranger
    rule: S03
    params: { warn_threshold: 5, fail_threshold: 8 }
  - name: s07_test_first
    rule: S07
```

#### [NEW] `src/specweaver/pipelines/validation_code_default.yaml`

Same pattern for C01-C08.

#### [NEW] Profile pipelines — one per domain

```yaml
# pipelines/validation_spec_library.yaml
extends: validation_spec_default
override:
  s05_day_test:
    params: { warn_threshold: 20, fail_threshold: 40 }
  s08_ambiguity:
    params: { warn_threshold: 2, fail_threshold: 5 }
  s11_terminology:
    params: { warn_threshold: 2, fail_threshold: 4 }
```

5 profile pipelines: `library`, `web-app`, `data-pipeline`, `microservice`, `ml-model`.

#### Inheritance example with `add` and `after`/`before`:

```yaml
extends: validation_spec_default
override:
  s05_day_test:
    params: { warn_threshold: 80 }
remove: [s04_dependency_dir]
add:
  - name: d01_schema_check
    rule: D01
    path: ./rules/d01_schema_check.py
    after: s03_stranger
    params: { strict_mode: true }
```

---

### 5.6 Handler Integration

#### [MODIFY] `src/specweaver/flow/handlers.py` — `ValidateSpecHandler`

The orchestration handler delegates to the validation sub-pipeline executor:

```diff
 class ValidateSpecHandler:
-    def _run_validation(self, spec_path, settings, *, kind_str=None):
-        from specweaver.validation.runner import get_spec_rules, run_rules
-        rules = get_spec_rules(include_llm=False, settings=settings, kind=kind)
-        content = spec_path.read_text(encoding="utf-8")
-        return run_rules(rules, content)
+    def _run_validation(self, spec_path, settings, *, kind_str=None):
+        from specweaver.validation.executor import (
+            execute_validation_pipeline, load_validation_pipeline,
+        )
+        pipeline = load_validation_pipeline("spec", project_path)
+        content = spec_path.read_text(encoding="utf-8")
+        return execute_validation_pipeline(pipeline, content, spec_path, settings)
```

The handler continues to return `StepResult` with aggregated results to the orchestration pipeline. **Orchestration pipeline model unchanged.**

---

### 5.6 CLI Additions

#### [MODIFY] `src/specweaver/cli.py`

```
sw config add-rule-path <path>       # Register a custom rule directory
sw config remove-rule-path <path>    # Unregister
sw config rule-paths                 # List registered paths
sw check --list-rules                # Show all registered rules + config source
sw check --pipeline <name>           # Override validation pipeline
```

**`--list-rules` output:**
```
Spec rules (pipeline: validation_spec_default):
  S01  One-Sentence Test       built-in  warn=1   fail=2
  S05  Day Test                built-in  warn=30  fail=60
  D01  Schema Check            custom    strict_mode=true
  ...

Code rules (pipeline: validation_code_default):
  C01  Syntax Valid             built-in
  C04  Coverage                 built-in  fail=70
  ...
```

---

### 5.7 Project Pipeline Discovery

#### [MODIFY] `src/specweaver/config/settings.py` or new module

Pipeline resolution order:
1. CLI `--pipeline <name>` flag (highest priority)
2. Project-local `.specweaver/pipelines/validation_spec.yaml`
3. Common default `src/specweaver/pipelines/validation_spec_default.yaml`

---

## 6. Verification Plan

### Phase A Tests

| Test File | Tests | Covers |
|-----------|-------|--------|
| `tests/unit/validation/test_registry.py` [NEW] | ~15 | `register()`, `get()`, `list_spec()`, `list_code()`, `list_all()`, duplicate ID rejection, D-prefix enforcement, S/C rejection for custom rules |
| `tests/unit/validation/qa_runner.py` [EXTEND] | ~5 | Verify `get_spec_rules()` / `get_code_rules()` still return same rules via registry |
| `tests/integration/test_registry_integration.py` [NEW] | ~5 | All 19 built-in rules registered, categories correct, can instantiate each |

**Phase A expected: ~25 new tests**

### Phase B Tests

| Test File | Tests | Covers |
|-----------|-------|--------|
| `tests/unit/validation/test_pipeline_model.py` [NEW] | ~10 | `ValidationStep`, `ValidationPipeline` model parsing, inheritance fields |
| `tests/unit/validation/test_executor.py` [NEW] | ~12 | `execute_validation_pipeline()`, rule lookup, params passing, broken rule skip, caching |
| `tests/unit/validation/test_loader.py` [NEW] | ~12 | Load from directory, broken file skips, D-prefix validation, empty dir, non-Rule class ignored |
| `tests/unit/validation/test_inheritance.py` [NEW] | ~15 | extends, override, remove, add, after/before placement, missing base error, invalid step name |
| `tests/unit/loom/test_rule_atom.py` [NEW] | ~8 | Pass/fail/warn/skip mapping, context extraction, exports |
| `tests/integration/test_validation_pipeline.py` [NEW] | ~10 | Default pipeline loads all rules, profile pipeline matches thresholds, custom pipeline with D-rule |
| `tests/e2e/test_lifecycle.py` [EXTEND] | ~8 | `sw config add-rule-path`, `--list-rules`, `--pipeline`, custom rule in E2E flow |

**Phase B expected: ~75 new tests**

### Regression

```bash
uv run pytest tests/ -x -q          # All existing tests must pass
uv run ruff check src/ tests/       # Zero new lint issues
```

---

## 7. Documentation Updates

| Document | Update |
|----------|--------|
| `README.md` | Add Custom Rules + Validation Pipelines to Features list |
| `docs/quickstart.md` | Add "Custom validation rules" and "Pipeline configuration" sections |
| `docs/developer_guide.html` | Add §8 Validation Pipelines, update architecture diagram, test counts |
| `docs/proposals/specweaver_roadmap.md` | Mark 3.4 as ✅ when complete |
| `docs/proposals/roadmap/phase_3_feature_expansion.md` | Update 3.4 entry |

---

## 8. Scope Estimate

| Component | Phase | Effort |
|-----------|-------|--------|
| `validation/registry.py` (new) | A | Small |
| `validation/runner.py` (refactor) | A | Small |
| `rules/spec/__init__.py` + `rules/code/__init__.py` | A | Small |
| Tests Phase A (~25) | A | Medium |
| `validation/pipeline.py` — sub-pipeline model (new) | B | Small |
| `validation/executor.py` — sub-pipeline executor (new) | B | Medium |
| `validation/loader.py` — custom rule loader (new) | B | Medium |
| `loom/atoms/rule_atom.py` — adapter (new) | B | Small |
| Validation pipeline YAMLs (7 files) | B | Small |
| Inheritance resolution (in executor) | B | Medium |
| Handler integration | B | Small |
| CLI additions | B | Small |
| Tests Phase B (~75) | B | Medium-Large |
| Documentation | B | Small |

**Phase A total: ~1 session** (registry + runner refactoring + tests)
**Phase B total: ~2-3 sessions** (sub-pipeline model + executor + loader + pipelines + CLI + tests + docs)
