# Phase 6: External Validation

> **Status**: Pending
> **Goal**: SpecWeaver is used on a real project that isn't SpecWeaver itself.

> [!TIP]
> **Reference**: [Spec Kit](https://github.com/github/spec-kit)'s workflow (Specify → Plan → Tasks → Implement) is a useful model for structuring the external validation runs. See [ORIGINS.md](../../ORIGINS.md) § Spec Kit for blueprint references.

- [ ] Identify a target project (e.g., the automatic trading system — 20 microservices, multi-tenant, multi-strategy)
- [ ] Run the full workflow: `sw init` → `sw draft` → `sw check` → `sw implement` → `sw check --level code` → `sw review code`
- [ ] Document the experience: what worked, what didn't, what's missing
- [ ] **Milestone**: SpecWeaver is **useful** on real-world projects.
