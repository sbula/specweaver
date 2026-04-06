# Developer Guide: Adding New Validation Rules

SpecWeaver guarantees software specification quality using a native **10-Test Battery**. This battery automatically halts agentic workflow drift before LLM tokens are wasted.

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
from specweaver.validation.models import RuleResult, Finding

def check_no_weasel_words(spec_content: str) -> RuleResult:
    # 1. Evaluate logic
    weasels = ["maybe", "probably", "should"]
    findings = []
    
    for word in weasels:
        if word in spec_content.lower():
            findings.append(Finding(line=0, issue=f"Ambiguous word: {word}"))
            
    # 2. Return standard struct
    return RuleResult(
        rule_id="S_WEASEL",
        passed=len(findings) == 0,
        findings=findings
    )
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

- **Specs**: Text-based boundaries rely on Regex and simplistic NLP chunking schemas.
- **Code**: Always rely natively on AST. Do not parse Python/TypeScript code with Regex. For advanced analysis, utilize Tree-Sitter (e.g., the `validation/drift_detector.py` or `validation/rules/code/c09_traceability.py`) to scrape pure method signatures and abstract comments structurally out of source-code blocks without parsing fragile syntax.
