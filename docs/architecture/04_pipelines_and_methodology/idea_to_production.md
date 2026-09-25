# Idea to Production — The Default Workflow

SpecWeaver spans 6 lifecycle layers. Each transition is gated by the 10-test battery at the
matching fractal level (the code now runs 12 rules — see [Methodology Index](methodology_index.md)).

```text
L1 Business       ─Feature Spec──▶  L2 Architecture  ─Decomposition──▶  L3 Specification
(HITL + Agent)                      (Architect + Agent)                  (Developer + Agent)
                                                                               │
                                                                       Component Specs
                                                                               │
L6 Deploy  ◄──CI/CD──  L5 Review  ◄──Code──  L4 Implementation  ◄────────────┘
(DevOps)               (Reviewer Agent)       (Implementer Agent)
```

## Typical Flow for a Single Feature

1. **L1 — Business**: HITL describes the feature → agent structures it into a Feature Spec →
   completeness tests run → HITL approves
2. **L2 — Architecture**: agent proposes component decomposition → readiness tests check each split
   → architect approves
3. **L3 — Specification**: agent drafts the component spec from the 5-section template → 10-test
   battery validates → LLM semantic review pipeline scores quality
4. **L4 — Implementation**: agent generates code from spec → generates tests → runs tests →
   validates code → LLM reviews code against spec
5. **L5 — Review**: reviewer agent (read-only) checks against spec + checklist → ACCEPTED or DENIED
   with feedback → loops back to L4 if DENIED
6. **L6 — Deploy**: CI/CD pipeline runs (lint, type check, tests, security, build)

## SpecWeaver Pipelines Automate L3–L5

The `flow/` engine runs the spec→code→review cycle from declarative YAML pipelines
(`src/specweaver/workflows/pipelines/`):

| Pipeline | Steps | Purpose |
|----------|-------|---------|
| `new_feature` | draft→validate→review→generate→test→validate→review | Full spec-first loop |
| `feature_decomposition` | draft→validate→decompose | Feature→components via dynamic topological DAG waves |
| `scenario_integration` | validate→generate_contract→dual_pipeline→run_scenarios→arbitrate | Dual-pipeline scenario verification with error attribution |
| `validate_only` | validate | Static quality check |
| `validation_spec_*` | validate (with domain presets) | Domain-specific rules |
| `validation_code_default` | validate code | Code quality check |
