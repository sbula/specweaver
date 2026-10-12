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
  framework: spring-boot
  # Which files get this archetype's code rules and annotation expansions
  supported_languages: ["java", "kotlin"]

decorators:
  RestController: "@Controller\n@ResponseBody"
  GetMapping: "@RequestMapping(method = RequestMethod.GET)"
```

A language name must be one of `LANGUAGE_SUFFIXES` in `core/flow/handlers/archetype_pipelines.py`;
an unknown one is refused.

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

**Do not** parse the framework AST inside the rule. The validate steps and `sw check` both call
`core/flow/handlers/archetype_pipelines.py`, which:

1. finds the `archetype` in the nearest `context.yaml` (`spring-boot`);
2. takes `validation_code_<archetype>` when the file is in one of the schema's
   `supported_languages` (none named: any), else `validation_code_default`;
3. has **CodeStructureAtom** read the file's structure and framework markers, and puts them in each
   step's `params["ast_payload"]`.

### 4a. Simple markers: use C12, no Python

`C12ArchetypeCodeBoundsRule`
(`src/specweaver/assurance/validation/rules/code/c12_archetype_code_bounds.py`) reads the markers
per symbol — its annotations (`decorators`) and supertypes (`extends`). A required marker matches
with or without `@`. Ship the pipeline in
`src/specweaver/workflows/pipelines/frameworks/<language>/validation_code_<archetype>.yaml`, or put a
project's own in `.specweaver/pipelines/validation_code_<archetype>.yaml`:

```yaml
name: validation_code_spring-boot
version: "1.0"
steps:
  - name: c07_no_orphan_todo
    rule: C07
  - name: c12_archetype_code_bounds
    rule: C12
    params:
      required_markers: ["@RestController"]
      forbidden_markers: ["@Entity"]
```

Do not `extends: validation_code_default` for a language other than Python: most default code
rules read Python.

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
