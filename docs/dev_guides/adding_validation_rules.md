# Adding Validation Rules

Use when: you add a rule to SpecWeaver's static validation pipeline (the **12-Test Battery**, which
stops agent drift before LLM tokens are spent).

## Categories

| Category | Module | Targets | Example |
|---|---|---|---|
| **Spec Rules** | `validation/rules/spec/` | human- or LLM-written specifications | single-sentence setups; blocking 'weasel words' ("should probably do this") |
| **Code Rules** | `validation/rules/code/` | the generated codebase | drift detection, test coverage thresholds |

## Steps

1. Write the rule as a pure, stateless class: no side-effects, no I/O (no filesystem), no APIs.

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

2. Register it in `validation/rules/<category>/register.py`
   (`_reg.register("S01", OneSentenceRule, "spec")` style).
3. Add the rule ID to the sub-pipeline YAML, `pipelines/*.yaml` under `workflows/` (e.g.
   `validation_spec_default.yaml`). Rule selection is declarative; never hardcode it in Python.

## Rules

- **Specs**: text checks use Regex and simple NLP chunking. Architectural spec checks (e.g. S12
  `S12ArchetypeSpecBoundsRule`) get Markdown parsed via tree-sitter by `CodeStructureAtom`, injected
  as `self.context["structure"]`.
- **Code**: never Regex-parse Python/TypeScript. Use AST or injected structures. The Flow Engine
  Orchestrator runs Tree-Sitter (`CodeStructureAtom`) or Schema Parsing (`ProtocolAtom`) in the
  sandbox layer and injects the results into `self.context`.
- Traceability (`C09TraceabilityRule`: `<Spec FR>` mapped to `@trace(FR)` in source tests) uses the
  injected `analyzer_factory` (`self.context.get("analyzer_factory")`) for polyglot AST queries: no
  string regexes, no dependency cycles.
- More DI patterns: `adding_framework_guide.md` (`C12ArchetypeCodeBoundsRule`),
  `protocol_analyzers.md` (`C13ContractDriftRule`).

## Code validation context hydration (C03/C04/C05)

Rules that need sandbox execution (tests, coverage, architecture) **must NOT import sandbox
modules**. The `validation` layer has `archetype: pure-logic` and `forbids: specweaver/sandbox/*`.

1. The `core.flow` orchestrator runs `QARunnerAtom` for each active code rule.
2. Results are serialized to plain dicts and merged into the rule's `self.context`.
3. The rule reads them by the agreed keys.

### Context key contract

| Key | Populated By | Consumed By | Shape |
|-----|-------------|-------------|-------|
| `qa_tests_result` | `hydrate_code_validation_context()` | C03 `TestsPassRule` | `{"status": str, "message": str, "exports": {"passed": int, "failed": int, "errors": int}}` |
| `qa_coverage_result` | `hydrate_code_validation_context()` | C04 `CoverageRule` | `{"status": str, "message": str, "exports": {"coverage_pct": float}}` |
| `qa_architecture_result` | `hydrate_code_validation_context()` | C05 `ImportDirectionRule` | `{"status": str, "message": str, "exports": {"violation_count": int, "violations": list}}` |

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

### Entry points

All three route through `execute_validation_flow()` in `core.flow.handlers.validation_hydrator`,
which does hydration + pipeline execution:

- **Flow handler**: `ValidateCodeHandler._run_validation()` → `execute_validation_flow()`
- **CLI**: `sw validation check --level code` → `execute_validation_flow()`
- **API**: `POST /api/v1/validation/check` → `execute_validation_flow()`
