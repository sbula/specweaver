# Design: Architectural Documentation Modularization

- **Feature ID**: TECH-008
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DESIGN_HARDENED

## Business Context & Goal

SpecWeaver's architectural documentation has evolved into a monolithic 46KB `architecture_reference.md` file alongside 17 loosely structured markdown documents. This structural debt creates an impenetrable onboarding experience, makes GitHub publishing impossible, and obscures the strict Domain-Driven Design (DDD) boundaries the project enforces.

The goal of TECH-008 is to execute a **Non-Destructive Copy-and-Verify** refactoring of `docs/architecture` into a modular, visually-rich, GitHub-publishable reference site aligned perfectly with DDD principles (Hexagonal Layers, Bounded Contexts).

## Core Requirements

1. **Zero Data Loss**: Every byte of the existing 18 files and 14 monolith sections must be mapped and preserved.
2. **DDD Alignment**: The folder structure must explicitly represent horizontal layers (Foundational Principles) and vertical slices (Bounded Contexts).
3. **Visual Clarity**: Integration of Mermaid sequence diagrams and graphs to explain complex concepts like Dependency Inversion (The Composition Root).
4. **Historical Preservation**: Formalization of Architectural Decision Records (ADRs) to preserve the "why" behind decisions (e.g., CLI vs Atoms, Composition Root vs Factories) without cluttering the reference with chat noise.

## Technical Details

The new structure will mimic a static site generator (like MkDocs) for seamless GitHub navigation:

```text
docs/architecture/
├── README.md                           
├── 01_foundational_principles/         
├── 02_bounded_contexts/                
├── 03_system_topology/                 
├── 04_pipelines_and_methodology/       
├── 05_delivery_mechanisms/             
├── 06_lessons_and_future/              
└── 07_architectural_decision_records/  
```

## Sub-Feature Breakdown

### SF-01: Structure Scaffold & File Migration
- **Scope**: Create the new category folders and execute 1-to-1 moves for standalone files (e.g., `completeness_tests.md`).
- **Impl Plan**: `docs/roadmap/features/topic_07_technical_debt/TECH-008/TECH-008_sf01_implementation_plan.md`

### SF-02: Monolith Slicing
- **Scope**: Extract the 14 sections of the 46KB `architecture_reference.md` into their respective modular homes.
- **Impl Plan**: `docs/roadmap/features/topic_07_technical_debt/TECH-008/TECH-008_sf02_implementation_plan.md`

### SF-03: Hub Creation & Linking (Verification)
- **Scope**: Create the master `README.md`, formalize the ADRs, update all relative markdown links, and perform the byte audit to guarantee zero data loss.
- **Impl Plan**: `docs/roadmap/features/topic_07_technical_debt/TECH-008/TECH-008_sf03_implementation_plan.md`

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Scaffold & Migration | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-02 | Monolith Slicing | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-03 | Hub & Link Verification| SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
