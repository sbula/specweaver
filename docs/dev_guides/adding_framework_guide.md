# Adding Framework-Specific Validation Rules (Archetypes)

Use when: you add framework-specific checks, e.g. a Spring Boot controller must carry
`@RestController`, or React Router `loader` functions must be separated.

SpecWeaver uses "Archetype-Based Rule Sets". The `assurance/validation` layer only compares
dictionaries (no C-bindings, no I/O), so a framework rule gets its data from **CodeStructure Atoms**
through **Dependency Injected Payloads**, never by parsing itself.

## 1. Declare the archetype

An archetype is a structural footprint (e.g. `spring-boot`, `fastapi`, `react-router`). Users set it
in `context.yaml`:

```yaml
version: "1.0"
archetype: "spring-boot"
consumes: ["database/"]
```

The Orchestrator (`flow/`) resolves it via `ArchetypeResolver` and runs the matching validation
pipeline extension (e.g. `validation_code_spring-boot.yaml`).

## 2. Add a schema evaluator (macro unrolling)

LLMs misread abstract macros and annotations like `@RestController`. The **LSP-Bypass Engine**
unrolls them from YAML instead of starting a compiler.

Every new archetype **must** ship a flat YAML in
`src/specweaver/workflows/evaluators/frameworks/<archetype>.yaml`. Example,
`src/specweaver/workflows/evaluators/frameworks/spring-boot.yaml`:

```yaml
metadata:
  # This mathematically ensures if an LLM hallucinates a node.js syntax into Java, it automatically drops the evaluation
  supported_languages: ["java", "kotlin"] 

evaluate:
  annotations:
    RestController:
      type: "class"
      unroll: "Provides HTTP JSON Response APIs routing automatically without explicit ResponseBody bindings."
    GetMapping:
      type: "method"
      unroll: "HTTP GET Request Boundary endpoint bound to >>{0}<<"
```

Note (2026-09-25): the shipped `spring-boot.yaml` uses a flat `decorators:` map
(e.g. `RestController: "@Controller\n@ResponseBody"`). Copy the shipped file's shape.

Evaluation is recursive with depth protection (Max Depth 5). Agents calling
`CodeStructureTool.read_unrolled_symbol` get the runtime behavior deterministically in about 5
milliseconds instead of 5,000 milliseconds.

## 3. Compose plugins (Feature 3.30a)

A component often combines a framework (`spring-boot`) with orthogonal plugins (`spring-security`,
`flyway`). Declare them as a `plugins` array instead of one archetype per combination:

```yaml
version: "1.0"
archetype: "spring-boot"
plugins: ["spring-security"]
consumes: ["database/"]
```

Plugin schemas merge into the primary evaluator schema as supersets. A plugin can also hide tool
intents from agents, with no code change:

```yaml
# frameworks/spring-security.yaml
intents:
  hide: ["list_symbols", "edit_file"]
```

Agents are then limited to read-only structural queries, without tool limits hardcoded in the
orchestrator's Python classes.

## 4. Write the rule

**Do not** parse the framework AST inside the rule. `ValidateCodeHandler`:

1. discovers the `archetype` (`spring-boot`);
2. calls **CodeStructureAtom** inside the sandbox to turn the syntax tree into a plain dictionary
   (`dict[str, Any]`);
3. injects it into `step.params["ast_payload"]` for the current pipeline.

### 4a. Simple markers: use C12, no Python

`C12ArchetypeCodeBoundsRule`
(`src/specweaver/assurance/validation/rules/code/c12_archetype_code_bounds.py`) reads
`self.context.get("framework_markers")` for arrays of symbols. Bind it in the pipeline extender,
`.specweaver/pipelines/frameworks/java/validation_code_spring-boot.yaml` (or your project-local
pipelines config):

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

Note (2026-09-25): the shipped extender
`src/specweaver/workflows/pipelines/frameworks/java/validation_code_spring-boot.yaml` uses an `add:`
list with `rule: C12` and `position: end`. Copy the shipped file's shape.

The orchestrator computes the AST and binds the `ast_payload` markers into
`C12ArchetypeCodeBoundsRule.context`.

### 4b. Proprietary/Advanced rules: subclass `Rule`

When `C12`'s inclusion/exclusion `PARAM_MAP` is not enough, subclass `Rule` and read `self.context`:

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

## Why this split

Syntax-tree extraction lives in the sandbox (`Loom` in older docs); `assurance` only compares
dictionaries. Native C-bindings (like TreeSitter compiling Node.js/Rust) therefore cannot crash the
Python validation processes, and the architectural `forbid` boundaries hold.
