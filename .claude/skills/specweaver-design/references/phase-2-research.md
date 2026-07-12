---
description: "Phase 2: Research — two parallel tracks (codebase + internet), ROI analysis, refactoring opportunities, then synthesis. Fully autonomous, no HITL."
---

# Phase 2: Research

> [!IMPORTANT]
> **This phase is fully autonomous. No HITL.**
> Execute both research tracks, then synthesize. Do not stop for confirmation.

This phase runs two parallel research tracks, then synthesizes findings.
Both tracks should be executed before synthesis.

---

## Track A — Codebase Research (autonomous)

A.1. Search for all modules, files, classes, and patterns related to the feature:
     - Use `grep_search` for key terms from the working definition.
     - Use `list_dir` to explore relevant package directories.
     - Use `view_file` to read any relevant source files found.

A.2. Read the architecture reference in full:
     `docs/architecture/architecture_reference.md`
     Focus on: module map, dependency rules (`consumes`/`forbids`), archetypes,
     Known Boundary Violations, Feature Map, Anti-Patterns.

A.3. Read `context.yaml` files in ALL modules the feature will likely touch.

A.3a. **MANDATORY**: Read ALL files in `docs/dev_guides/` and `docs/user_guides/`.
      These contain established patterns, conventions, and extension points that
      the design MUST respect. Skipping these leads to designs that contradict
      existing project standards.

A.4. Read `ORIGINS.md` for blueprint references related to this feature's domain.

A.5. Read any existing adjacent implementation plans covering related features.

A.6. Record:
     - What already exists that could be reused or extended?
     - Which modules will be touched?
     - What would be duplicated if we build from scratch?
     - What boundary rules constrain the design?

---

## Track B — External Research (autonomous)

B.1. For each external API, library, framework, or tool mentioned in or implied
     by the feature description or working definition:
     - Web-search the official documentation.
     - Web-search the changelog or release notes for the last 2 major versions.
     - Prefer results < 18 months old.

B.2. For each tool found, record:
     - Tool name and relevant version(s)
     - The specific API surface relevant to this feature (not the full API)
     - Deprecation notices affecting this feature's use case
     - Breaking changes since the version last used in this project (`pyproject.toml`)

B.3. Search for recent articles, blog posts, or GitHub issues about known
     gotchas, pitfalls, or production issues with these tools at the target version.

B.4. **MANDATORY**: Search the internet for **ideas, inspiration, and best practices**
     related to this feature's domain. Not just API docs — look for how other projects,
     frameworks, or products solve the same problem. Record novel approaches, patterns,
     or insights that could improve the design.

---

## Synthesis (sequential, after both tracks)

S.1. Combine Track A and Track B findings into a unified research brief.

S.2. Identify and document:
     - **Reuse opportunities**: existing code that covers part of the feature
     - **Gaps**: capabilities that must be built from scratch
     - **Contradictions**: design ideas that clash with existing architecture
     - **Version risks**: tools with breaking changes or instability

S.3. **ROI Analysis** — identify existing features that would benefit from this new feature:
     - Which already-implemented features should be refactored to use this new feature?
     - What is the ROI of each refactoring? (effort vs. benefit)
     - Pros/Cons of each refactoring opportunity
     - Where in the codebase should we refactor so existing features profit from the new feature?

S.4. **Refactoring Opportunities** — look beyond this feature:
     - What should we refactor to optimize overall performance?
     - What can be cleaned up architecturally?
     - What redundancies can be eliminated?
     - What can be refactored to be used by MULTIPLE features (while still fitting the architecture)?

S.5. Proceed autonomously to Phase 3.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 2 complete. Research brief ready.
> Proceed to Phase 3 (Feature Detail).
