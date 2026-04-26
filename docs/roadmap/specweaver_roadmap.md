# SpecWeaver Roadmap

> **Status**: ACTIVE
> **Context**: SpecWeaver is a Spec-First Development platform orchestrating LLM agents via deterministic AST constraints. 

> [!IMPORTANT]
> **The Core Principle**: "Good Enough" Vertical Architecture. 
> We build vertical Epics (User Stories) instead of horizontal layers. Every User Story strictly defines a Core Required (MVS) baseline, with optional Sub-Story Add-Ons built later.

> [!WARNING]
> **Legacy Phase Model Deprecated**
> The old horizontal planning model (Phase 1 through Phase 6) has been deprecated because it caused architectural bloat. All planning now occurs in the Master Story Roadmap.

---

## Single Source of Truth

All development, tracking, and prioritization is managed via the 19-Story Master Roadmap:
👉 **[Master Story Roadmap](master_story_roadmap.md)**

---

## The Capability Matrix (DO-178C)

While the Master Story Roadmap tracks *deliverables*, the Capability Matrix acts as the "Periodic Table" of SpecWeaver's internal architecture. It maps every atomic capability (from Phase 1 through Phase 6 + Backlog) against its **Domain Assurance Level (DAL)** and groups them by functional **Topic**.

👉 **[View the full Capability Matrix & Topic Files](capability_matrix.md)**

---

We are currently tracking against the Master Story Roadmap to complete **US-5 (Polyglot Code Understanding)** and **US-19 (Microservice Fleet Orchestration)**. By building out robust parsing support for enterprise languages (C/C++, Markdown, Go), we are securing the physical "Sensors" required to power the downstream engine capabilities like Deep Semantic Hashing and the Persistent Knowledge Graph.

---

## Success Criteria

**The platform is PROVEN when you can:**
1. ✅ `sw init my-app --path .` registers and scaffolds the project
2. ✅ `sw check some_spec.md` reports PASS/FAIL with findings
3. ✅ `sw draft greet_service` produces a real spec via HITL interaction
4. ✅ `sw implement greet_service_spec.md` generates code + tests
5. ✅ `sw check --level code greet_service.py` checks syntax, tests, coverage
6. ✅ `sw review code greet_service.py` provides LLM semantic judgment

**The platform is ENTERPRISE-READY when additionally:**
7. ✅ You've used it on SpecWeaver itself (dogfooding)
8. 🔜 You've used it to build an external proprietary trading system (US-18)
9. ✅ Features can be added without restructuring (interface extensibility confirmed)
10. 🔜 Topology-aware spec authoring catches cross-service issues before code generation (US-19)
11. ✅ Multi-project management: `sw projects`, `sw use`, `sw remove`, `sw update`, `sw scan`
