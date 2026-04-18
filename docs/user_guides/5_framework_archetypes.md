# User Handbook 5: Framework Archetypes & Context Injection

SpecWeaver relies on strict Architectural Bounds checks. By default, agents are completely blinded from large external frameworks resulting in hallucinations. **Archetypes** natively inform agents regarding structural realities of external tool chains.

## 1. The `context.yaml`
Every domain module in SpecWeaver is encapsulated mathematically within a `context.yaml` boundaries file located at the folder boundary.

```yaml
context:
  name: "My Backend Domain"
  archetype: spring-security
  plugins:
    - spring-boot
    - jpa-hibernate
```

## 2. Injecting Compiler Reality (Macro Evaluator)
Because LLMs evaluate raw tokens directly, they frequently fail to comprehend hidden runtime logic generated behind Java Annotations or Rust Procedural Macros `#[derive(Debug)]`.
By declaring `spring-boot`, the internal Tree-sitter AST Extractor recursively unrolls Annotations physically delivering expanded source definitions inside the LLM Generation execution payload solving massive logical omissions.

## 3. The `intents.hide` Shield
Sometimes you want Agents isolated from specific internal configurations (e.g. banning an LLM from editing a Kubernetes manifest or rewriting `.gitignore` natively).

By routing `plugins` natively, SpecWeaver utilizes **Dynamic Tool Gating**, securely intercepting JSON schema declarations prior to LLM exposure natively, removing tools directly corresponding to explicit strings array `intents.hide`!

```yaml
# Inside your plugin config dynamically:
intents:
  hide:
    - run_shell_command
    - configure_aws
```
The SpecWeaver LLM physically is blocked from executing shell logic cleanly without brittle `python` wrappers.

## 4. Validating Contract Drift (Features 3.31+)
Because LLMs often hallucinate endpoints, SpecWeaver features **Contract Drift Analysis (Rule C13)** natively in its validation pipeline Engine.
If you inject an OpenAPI or gRPC definition (`protocol_schema`), the Architecture framework statically queries your source code's Abstract Syntax Tree (`ast_payload`) post-generation to guarantee mathematically every `ProtocolEndpoint` mapped has a corresponding backend router (e.g. `@app.post("/users")`). Any unresolved endpoints force an automatic rollback!
