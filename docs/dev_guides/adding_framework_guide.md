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

## 3. Creating the Custom Framework Validation Rule

Your Validation Rule simply extends `Rule` and queries the injected dictionary directly.

### Step 3a: Create the Rule Python Code
Inside `src/specweaver/assurance/validation/rules/code/`, build your `C12_FrameworkSpecificBounds.py`:

```python
from typing import Any
from specweaver.assurance.validation.models import Rule, RuleResult, RuleStatus

class C12_FrameworkSpecificBounds(Rule):
    """Verifies framework-specific patterns injected from the AST."""
    
    @property
    def check_id(self) -> str:
        return "C12_FrameworkSpecificBounds"

    def check(self, target_text: str, /, params: dict[str, Any] | None = None) -> RuleResult:
        if not params or "ast_payload" not in params or "markers" not in params["ast_payload"]:
             # Graceful fallback if payload isn't injected.
             return RuleResult(status=RuleStatus.PASSED, ...)

        markers = params["ast_payload"]["markers"]
        
        # Example validation logic reading the dictionary (e.g. checking 'SpringHandler')
        # Structure is markers[symbol_name]["decorators"] and markers[symbol_name]["extends"]
        for symbol, data in markers.items():
            if "RestController" in data.get("decorators", []):
                return RuleResult(status=RuleStatus.PASSED, ...)
                
        return RuleResult(
            status=RuleStatus.FAILED,
            findings=["Missing @RestController on primary entrypoint."]
        )
```

### Step 3b: Bind the Rule in the YAML Pipeline Extender
Inside `.specweaver/pipelines/validation/validation_code_spring-boot.yaml`:

```yaml
version: "1.0"
extends: validation_code_default
steps:
  - id: analyze_framework_bounds
    type: custom
    rule_id: C12_FrameworkSpecificBounds
    params:
      # ast_payload will be dynamically injected here by the orchestrator at runtime.
      strict_mode: true 
```

---

## 4. Why this matters? (Domain Driven Design)

By isolating the **extraction of syntax trees** in the `Loom` layer, and keeping the `assurance` layer **purely mathematical dictionary comparisons**, SpecWeaver completely prevents native C-bindings (like TreeSitter compiling Node.js/Rust) from crashing the static Python validation processes. It enforces absolute security and scalability, maintaining SpecWeaver's core architectural `forbid` boundaries natively.
