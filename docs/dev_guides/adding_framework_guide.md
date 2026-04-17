# Developer Guide: Adding Framework-Specific Validation Rules (Archetypes)

SpecWeaver leverages "Archetype-Based Rule Sets" to enforce framework-specific constraints (e.g., verifying a Spring Boot controller has the `@RestController` annotation, or ensuring React Router `loader` functions are separated).

Because SpecWeaver supports multi-language monorepos, and because its `assurance/validation` layer operates purely mathematically (no C-bindings or I/O allowed), adding a new Framework Rule follows a strict pattern using **CodeStructure Atoms** and **Dependency Injected Payloads**.

---

## 1. Defining the Archetype

An Archetype defines a specific structural footprint (e.g., `spring-boot`, `fastapi`, `react-router`).
When building a new component, users define the archetype in their `context.yaml`:

```yaml
version: "1.0"
archetype: "spring-boot"
consumes: ["database/"]
```

The Orchestrator (`flow/`) parses this string via `ArchetypeResolver` and automatically triggers the correct Validation Pipeline extension (e.g., `validation_code_spring-boot.yaml`).

## 2. Rule Execution & Dependency Injection

You **must not** attempt to parse the framework AST inside the custom validation rule. The Engine will do it for you mathematically.

When a pipeline executes, the `ValidateCodeHandler`:
1. Discovers the `archetype` (`spring-boot`).
2. Calls the **CodeStructureAtom** securely inside the Loom sandbox to extract the OS string syntax tree into an agnostic Dictionary (`dict[str, Any]`).
3. Takes that dictionary and injects it into `step.params["ast_payload"]` for the current pipeline.

### Step 3a: Bind the Native Rule in the YAML Pipeline Extender
Because SpecWeaver natively bundles `C12ArchetypeCodeBoundsRule` (`src/specweaver/assurance/validation/rules/code/c12_archetype_code_bounds.py`), you do NOT need to write Python code to check simple structural metadata requirements!

The `C12ArchetypeCodeBoundsRule` natively evaluates `self.context.get("framework_markers")` looking for arrays of symbols.

Inside `.specweaver/pipelines/frameworks/java/validation_code_spring-boot.yaml` (or your project-local pipelines config):

```yaml
version: "1.0"
extends: validation_code_default
steps:
  - id: analyze_framework_bounds
    type: rule
    rule_id: C12
    params:
      required_markers: ["RestController", "GetMapping"]
      forbidden_markers: ["Entity"]
```

When the orchestrator triggers this pipeline, it automatically calculates the Native AST and binds the `ast_payload` markers dictionary explicitly into `C12ArchetypeCodeBoundsRule.context` for purely mathematical dictionary evaluation!

### Step 3b: Creating Proprietary/Advanced Rules
If `C12`'s simple inclusion/exclusion `PARAM_MAP` logic isn't complex enough for your proprietary framework, you can subclass `Rule` and read directly from `self.context`:

```python
from specweaver.assurance.validation.models import Rule, RuleResult, Finding, Severity

class MyEnterpriseRule(Rule):
    @property
    def rule_id(self) -> str: return "E01"

    def check(self, target_text: str) -> RuleResult:
        # 1. Read the parsed AST directly from the mathematical context property
        markers = self.context.get("framework_markers") or {}
        
        # 2. Perform advanced proprietary structural validation mapping
        findings = []
        for symbol, block in markers.items():
            if block.get("extends") == "LegacyBaseController":
                findings.append(Finding(message="LegacyBaseController forbidden.", severity=Severity.ERROR))
                
        if findings:
            return self._fail("Proprietary framework boundaries breached.", findings)
        return self._pass("Valid enterprise bounds.")
```

---

## 4. Why this matters? (Domain Driven Design)

By isolating the **extraction of syntax trees** in the `Loom` layer, and keeping the `assurance` layer **purely mathematical dictionary comparisons**, SpecWeaver completely prevents native C-bindings (like TreeSitter compiling Node.js/Rust) from crashing the static Python validation processes. It enforces absolute security and scalability, maintaining SpecWeaver's core architectural `forbid` boundaries natively.
