# Developer Guide: Adding New Validation Rules

SpecWeaver guarantees software specification quality using a native **12-Test Battery**. This battery automatically halts agentic workflow drift before LLM tokens are wasted.

This guide explains how to add new rules to SpecWeaver's static pipeline.

---

## 1. Rule Categories

Rules are partitioned logically into internal modules:
- **Spec Rules** (`validation/rules/spec/`): Target human or LLM-authored text specifications. Example: Enforcing single-sentence setups or blocking ambigous 'weasel words' (e.g., "should probably do this").
- **Code Rules** (`validation/rules/code/`): Target the generated codebase to ensure compliance. Example: Drift detection, test coverage thresholds.

---

## 2. Constructing a Rule

Rules are implemented as **Pure Functions** or stateless class handlers. They absolutely do NOT possess side-effects, I/O logic (no filesystems), or APIs.

### Example Schema (Spec Rule)
```python
from typing import Any
from pathlib import Path
from specweaver.assurance.validation.models import Rule, RuleResult, Finding, Severity

class NoWeaselWordsRule(Rule):
    @property
    def rule_id(self) -> str:
        return "S_WEASEL"
        
    @property
    def name(self) -> str:
        return "No Weasel Words"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        weasels = ["maybe", "probably", "should"]
        findings = []
        
        for word in weasels:
            if word in spec_text.lower():
                findings.append(Finding(message=f"Ambiguous word: {word}", severity=Severity.ERROR))
                
        if findings:
            return self._fail(f"Found {len(findings)} weasel words", findings)
        return self._pass("Spec validates unambiguously")
```

---

## 3. Integrating with the Pipeline

SpecWeaver utilizes declarative Sub-Pipelines for rule selection. 

Once your rule is written, you do not hardcode it into an array execution tree. Instead:
1. Navigate into `pipelines/*.yaml` (e.g., `validation_spec_new_feature.yaml`).
2. Add your rule ID explicitly into the sequence.
3. Bind your Python function path to the YAML string inside `validation/runner.py`.

---

## 4. Methodologies: Regex vs AST

- **Specs**: Standard text-based boundaries rely on Regex and simplistic NLP chunking schemas. However, advanced architectural spec validation (such as S12 `S12ArchetypeSpecBoundsRule`) natively uses the AST-driven `CodeStructureAtom` to parse Markdown via tree-sitter, injecting `self.context["structure"]` mapping cleanly.
- **Code**: Always rely natively on AST or Dependency Injected structures. Do not parse Python/TypeScript code with Regex. For advanced analysis, Validation Rules must strictly rely on the Flow Engine Orchestrator to execute Tree-Sitter (`CodeStructureAtom`) or Schema Parsing (`ProtocolAtom`) safely inside the Loom abstraction layer, and inject the results into the rule via `self.context` inside the Rule object. See `adding_framework_guide.md` for detailed Archetype DI patterns utilizing `C12ArchetypeCodeBoundsRule` and `protocol_analyzers.md` for `C13ContractDriftRule`. Furthermore, traceability (e.g. `C09TraceabilityRule` which enforces `<Spec FR>` mapped to `@trace(FR)` inside source tests) utilizes the injected `analyzer_factory` (via `self.context.get("analyzer_factory")`) to perform universal polyglot AST queries securely without writing string regexes or triggering dependency cycle violations.

---

## 5. Code Validation Context Hydration (C03/C04/C05)

Code validation rules that depend on sandbox execution (running tests, collecting coverage,
checking architecture) **must NOT import sandbox modules directly**. The `validation` layer
has `archetype: pure-logic` and `forbids: specweaver/sandbox/*`.

Instead, use the **context hydration pattern**:

1. The `core.flow` orchestrator pre-executes the `QARunnerAtom` for each active code rule.
2. Results are serialized to plain dicts and merged into the rule's `self.context`.
3. Rules read results from `self.context` using agreed keys.

### Context Key Contract

| Key | Populated By | Consumed By | Shape |
|-----|-------------|-------------|-------|
| `qa_tests_result` | `hydrate_code_validation_context()` | C03 `TestsPassRule` | `{"status": str, "message": str, "exports": {"passed": int, "failed": int, "errors": int}}` |
| `qa_coverage_result` | `hydrate_code_validation_context()` | C04 `CoverageRule` | `{"status": str, "message": str, "exports": {"coverage_pct": float}}` |
| `qa_architecture_result` | `hydrate_code_validation_context()` | C05 `ImportDirectionRule` | `{"status": str, "message": str, "exports": {"violation_count": int, "violations": list}}` |

### Example: Reading Hydrated Context in a Rule

```python
class TestsPassRule(Rule):
    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        result = self.context.get("qa_tests_result")
        if result is None:
            return self._skip("No test execution result available")

        if result["status"] != "SUCCESS":
            return self._fail(f"Tests failed: {result['message']}")

        exports = result.get("exports", {})
        failed = exports.get("failed", 0)
        if failed > 0:
            return self._fail(f"{failed} test(s) failed")
        return self._pass("All tests passed")
```

### Entry Points

All three entry points route through `execute_validation_flow()`:

- **Flow handler**: `ValidateCodeHandler._run_validation()` → `execute_validation_flow()`
- **CLI**: `sw validation check --level code` → `execute_validation_flow()`
- **API**: `POST /api/v1/validation/check` → `execute_validation_flow()`

The `execute_validation_flow()` function in `core.flow.handlers.validation_hydrator` handles
hydration + pipeline execution as a single entry point.
