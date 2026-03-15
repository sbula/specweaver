# Scenario Testing — Independent Verification (Phase 3.13)

> **Status**: 📋 Proposal
> **Depends on**: Phase 2 Steps 11–12 (runner + gates), Phase 3.8 (traceability)
> **Origins**: [agent-system](../../ORIGINS.md#agent-system--independent-verification--wave-parallelism), [NVIDIA HEPH & BDD](../../ORIGINS.md#nvidia-heph--bdd-renaissance--spec-traceable-scenario-testing), [agentwise](../../ORIGINS.md#agentwise--agent-claim-verification)

---

## Problem

Today, the coding agent that generates code also generates (or influences) its own tests. This creates **correlated hallucinations** — if the agent misunderstands the spec, both code and tests will be consistently wrong in the same way. No amount of coverage or rule-based validation catches this.

## Solution

**Two parallel pipelines** derived independently from the same spec, meeting at a **validation JOIN gate**:

- **Coding pipeline** — generates code + unit/integration/e2e tests. Sees `src/`, `tests/`, specs. Cannot see `scenarios/`.
- **Scenario pipeline** — generates acceptance scenarios + converts them to executable tests. Sees `scenarios/`, specs, API contract. Cannot see `src/`, `tests/`.

Both pipelines work from the same spec and API contract, but are **information-isolated**. When scenario tests run against the actual code and pass, confidence in correctness is extremely high — because the test author had no access to the implementation.

## Architecture

### Pipeline Flow

```
Spec (validated + reviewed)
        │
        ▼
   Generate API Contract (Python Protocol/ABC)
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
┌───────────────────────┐    ┌──────────────────────────────┐
│  CODING PIPELINE      │    │  SCENARIO PIPELINE            │
│  Sees: spec, API,     │    │  Sees: spec, API              │
│        src/, tests/   │    │        scenarios/              │
│                       │    │                                │
│  1. generate code     │    │  1. generate scenarios (LLM)   │
│  2. generate tests    │    │     (multi per public method)  │
│  3. run unit tests    │    │  2. convert → pytest           │
│  4. validate code     │    │     (mechanical, no LLM)       │
│  5. signal READY      │    │  3. signal READY               │
└───────┬───────────────┘    └──────────┬───────────────────┘
        │                               │
        ▼                               ▼
    ┌───────────────────────────────────────┐
    │         JOIN GATE                     │
    │   Both pipelines READY               │
    │         ↓                             │
    │   Run scenario tests against code     │
    │         ↓                             │
    │   PASS → ✅ Done                      │
    │   FAIL → Arbiter Agent               │
    │         ↓                             │
    │   Filtered feedback → loop back       │
    └───────────────────────────────────────┘
```

### Filesystem Isolation

```
project/
├── src/              ← coding agent: R/W | scenario agent: ❌
├── tests/            ← coding agent: R/W | scenario agent: ❌
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scenarios/        ← coding agent: ❌  | scenario agent: R/W
│   ├── definitions/  ← structured YAML scenarios
│   └── generated/    ← pytest files (mechanical conversion)
├── contracts/        ← BOTH: read-only (generated from spec)
│   └── api_contract.py
└── specs/            ← BOTH: read-only
```

### API Contract (Generated Artifact)

Generated from the spec's `## Contract` section before either pipeline starts:

```python
# contracts/api_contract.py — AUTO-GENERATED from spec
from typing import Protocol

class UserService(Protocol):
    def create_account(self, email: str, password: str) -> User:
        """Create a new user account.
        
        Raises:
            UserExistsError: If email is already registered.
            ValidationError: If email format is invalid.
        """
        ...
    
    def deactivate(self, user_id: str) -> None:
        """Deactivate a user account.
        
        Raises:
            UserNotFoundError: If user_id does not exist.
        """
        ...
```

### Structured YAML Scenarios (Not Gherkin)

**Why YAML over Gherkin**: LLMs produce and consume structured data more reliably than natural-language Gherkin. YAML eliminates ambiguity, provides type information, and maps mechanically to parametrized pytest.

```yaml
# scenarios/definitions/user_service_create_account.yaml
feature: UserService.create_account
spec_clause: "## 2. Contract → create_account()"

scenarios:
  - name: "Happy path — valid email creates account"
    preconditions:
      - database_empty: true
    inputs:
      email: "alice@example.com"
      password: "StrongP@ss123"
    expected:
      returns: User
      properties:
        email: "alice@example.com"
        active: true
    postconditions:
      - user_persisted: true

  - name: "Duplicate email raises UserExistsError"
    preconditions:
      - user_exists:
          email: "alice@example.com"
    inputs:
      email: "alice@example.com"
      password: "AnyPassword1"
    expected:
      raises: UserExistsError
      message_contains: "already registered"

  - name: "Invalid email format raises ValidationError"
    inputs:
      email: "not-an-email"
      password: "StrongP@ss123"
    expected:
      raises: ValidationError

  - name: "Boundary — maximum length email"
    inputs:
      email: "a@b.c"  # minimum valid
      password: "StrongP@ss123"
    expected:
      returns: User
```

### Spec Template Enforcement

The spec-writing agent must produce structured scenario inputs. New required section in component specs:

```markdown
## 5. Scenario Inputs

Each public method must list concrete inputs for scenario generation:

### create_account(email, password) → User

```yaml
happy_path:
  inputs: {email: "alice@example.com", password: "StrongP@ss123"}
  expected: User with active=true

error_paths:
  - {inputs: {email: "duplicate@test.com"}, raises: UserExistsError}
  - {inputs: {email: "invalid"}, raises: ValidationError}

boundary:
  - {inputs: {email: "a@b.c"}, expected: User}  # minimum valid
  - {inputs: {email: ""}, raises: ValidationError}  # empty
`` `
```

### Arbiter Agent — Error Attribution

When scenario tests fail, a third **Arbiter Agent** determines fault:

| Verdict | Feedback to Coding Agent | Feedback to Scenario Agent | Escalation |
|---------|-------------------------|---------------------------|------------|
| **Code bug** | Stack trace + spec reference + expected behavior | "Your scenario is correct, waiting for fix" | — |
| **Scenario error** | "Your code is correct, waiting for scenario fix" | Spec clause + expected vs actual + suggestion | — |
| **Spec ambiguity** | — | — | HITL: shows both interpretations, asks human to clarify |

**Arbiter access**: Full read to all (spec, API, code, scenarios, test output, stack traces).
**Arbiter output**: Two filtered reports — never includes the other agent's implementation.

### Role Gating

| Role | `src/` | `tests/` | `scenarios/` | `specs/` | `contracts/` |
|------|--------|----------|-------------|----------|-------------|
| `coding_agent` | R/W | R/W | ❌ | R | R |
| `scenario_agent` | ❌ | ❌ | R/W | R | R |
| `arbiter` | R | R | R | R | R |
| `validator` | R | R | R | R | R |

---

## Implementation Order

| Sub-step | What | Sessions |
|----------|------|----------|
| **3.13a** | Spec `## Scenarios` section + S07 enhancement | 1 |
| **3.13b** | API contract generation handler | 1 |
| **3.13c** | Scenario generation atom (LLM) | 1–2 |
| **3.13d** | Scenario → pytest conversion (mechanical) | 1 |
| **3.13e** | `scenario_agent` role + filesystem restrictions | 1 |
| **3.13f** | `scenario_validation.yaml` pipeline | 0.5 |
| **3.13g** | JOIN gate type in models.py | 1 |
| **3.13h** | Pipeline orchestrator (parallel execution) | 2 |
| **3.13i** | Arbiter agent | 1–2 |
| **3.13j** | Feedback loops + retry | 1 |

**Total estimated effort**: 10–12 sessions.

---

## When to Implement

**Best timing: Early Phase 3, after 3.8 (traceability).**

Rationale:
- **Needs**: Flow engine runner + gates (Phase 2 Steps 11–12) ← partially done already
- **Needs**: Spec-to-code traceability (Phase 3.8) ← for `spec_clause` linking
- **Does NOT need**: RAG, domain brain, web UI, advanced agent isolation (those are later phases)
- **High value**: Catches the #1 risk in AI-generated code (correlated hallucinations)
- **Incremental**: Sub-steps 3.13a–d can deliver value without the full parallel pipeline

**Suggested order within Phase 3**: 3.1 → 3.2 → ... → 3.8 → **3.13a–d** (scenario basics) → 3.9–3.12 → **3.13e–j** (parallel pipeline).

This lets us start generating scenarios early (valuable on its own) and add the parallel pipeline infrastructure when the rest of Phase 3 is mature.
