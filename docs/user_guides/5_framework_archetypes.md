# User Handbook 5: Framework Archetypes & Context Injection

Use when: your code uses a framework (Spring Boot, FastAPI, Rust macros ...) whose generated
behavior the agent cannot see in the source.

A **framework** plus **plugins** tell SpecWeaver which framework rules apply to a module. Without
them, agents see only raw source and guess at what the framework generates.

## 1. Declare them in `context.yaml`

Each module has a `context.yaml` at its folder boundary. Declare the framework and plugins there;
`archetype` stays the layer role (`adapter`, `pure-logic`, ...):

```yaml
context:
  name: "My Backend Domain"
  archetype: adapter
  framework: spring-boot
  plugins:
    - spring-security
    - jpa-hibernate
```

The nearest `framework`, `archetype` and `plugins` at or above a file apply to it. An `archetype`
that names a framework still works and logs a warning to move it to `framework:`. Without either,
the framework the build file declares applies (for code generation and checks). A framework is a
name with an evaluator schema; see handbook 1, **Frameworks**.

## 2. Expand annotations and macros (Macro Evaluator)

LLMs read raw tokens. They miss logic that Java annotations or Rust procedural macros
(`#[derive(Debug)]`) generate at compile time.

Declaring `spring-boot` makes the Tree-sitter AST extractor unroll those annotations. The expanded
definitions go into the generation prompt.

## 3. Hide tools with `intents.hide`

Use it to keep agents away from a tool, e.g. running shell commands or editing a Kubernetes manifest
or `.gitignore`.

Your archetype and plugins select the evaluator config. Any tool named in its `intents.hide` list
is removed from the tool schemas before the LLM sees them (**Dynamic Tool Gating**).

```yaml
# Inside your plugin config dynamically:
intents:
  hide:
    - run_shell_command
    - configure_aws
```

The LLM cannot call a hidden tool. No `python` wrapper is needed.

## 4. Contract drift check (Features 3.31+)

**Rule C13 — Contract Drift Analysis** runs in the validation pipeline.

- Input: an OpenAPI or gRPC definition (`protocol_schema`) and the code's AST (`ast_payload`),
  read after generation.
- Check: every `ProtocolEndpoint` needs a matching backend route (e.g. `@app.post("/users")`).
- Any endpoint without a route: the rule fails and forces an automatic rollback.
