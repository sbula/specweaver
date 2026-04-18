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
- **Code**: Always rely natively on AST or Dependency Injected structures. Do not parse Python/TypeScript code with Regex. For advanced analysis, Validation Rules must strictly rely on the Flow Engine Orchestrator to execute Tree-Sitter (`CodeStructureAtom`) or Schema Parsing (`ProtocolAtom`) safely inside the Loom abstraction layer, and inject the results into the rule via `self.context` inside the Rule object. See `adding_framework_guide.md` for detailed Archetype DI patterns utilizing `C12ArchetypeCodeBoundsRule` and `protocol_analyzers.md` for `C13ContractDriftRule`.
