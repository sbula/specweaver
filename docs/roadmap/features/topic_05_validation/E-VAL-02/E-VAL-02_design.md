# Design: Auto-Discover Standards

- **Feature ID**: E-VAL-02
- **Epic**: Topic 05 (Validation)
- **Status**: ✅ Delivered — this document is a **record**, not a plan.
- **Legacy**: 3.5
- **Created**: 2026-08-17 under `INT-US-01-SF03-MIG`. The capability shipped with an implementation
  plan and **no design document**, so no requirement of it was ever written in the ledger's form.

## What shipped

`sw scan --standards` reads a project's own code and derives the conventions it actually follows —
naming, error handling, type hints, docstring style, test patterns, import patterns — for Python,
JavaScript and TypeScript. Results are stored per project *and per scope* in
`workspace_project_standards`, and injected into generation prompts through
`PromptBuilder.add_standards()`.

The point is mimicry over instruction: an agent writing into an existing codebase should match that
codebase, and nobody should have to write the conventions down for it to do so. `CONSTITUTION.md`
bootstrap is the human-readable side of the same data.

**Complete:** four sub-phases (Python analyzer, scanner + CLI + DB, JS/TS analyzers, constitution
bootstrap), 2774 tests at delivery.

## Functional Requirements

Written 2026-08-17 under `specweaver-dev` §3.2c, on contact from `INT-US-01-SF03-MIG`. Written from
**why the capability exists** — the agent should write code that looks like this project's code, and
should learn that by reading rather than being told — not from an inventory of its modules. Each is
behind a killed mutant; none was believed before that.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Read the code that represents the project | System | Discovers source files, preferring what git tracks, and honours `.specweaverignore` | Vendored, generated and ignored code cannot teach the agent conventions the project does not hold |
| FR-2 | Derive conventions per language | System | Routes each file to the analyzer for its extension and extracts by category | Python, JavaScript and TypeScript each yield their own standards rather than one averaged set |
| FR-3 | Recent code counts for more | System | Weights each file by age against a half-life derived from the project itself | A convention the project has moved away from does not outvote the one it moved to |
| FR-4 | Conventions are scoped, not global | System | Detects scopes and stores standards per scope | A monorepo's modules keep their own style instead of being flattened into a house average |
| FR-5 | Discovered standards persist | System | Upserts each `(project, scope, language, category)` into `workspace_project_standards` | A later run reads the standards back with their content and confidence, rather than rediscovering them |
| FR-6 | The agent is told, without being asked | Engine | Injects stored standards into the generation prompt | Conventions reach the model that writes the code — discovery nothing consumes is inert |
| FR-7 | A project with nothing to learn from still gets guidance | System | Falls back to built-in defaults when extraction yields nothing and the mode is `best_practice` | A greenfield project is given good practice instead of silence |

**FR-1's mutant fails 41 test files**, the widest here: `.specweaverignore` no longer applied, so the
discovery set swells with everything the project excluded. **FR-4's fails 27** — no scopes detected, and
every standard collapses to one bucket.

**FR-5 needed its second mutant.** The first removed `await self.session.flush()` from
`upsert_standard` and the whole suite passed — an **equivalent mutant**, because the session commits
later regardless. Nothing about persistence was untested; the probe simply changed no behaviour. The
mutant that matters stores `json.dumps({})` in place of the discovered content: the row is still
written, still counted, still has its confidence, and carries nothing. Four files fail.

That distinction is worth keeping. A test that counts rows cannot tell a populated standard from an
empty one, and the first mutant would have been reported as a coverage gap by anyone who stopped there.

## Non-Functional Requirements

None declared. The capability has no measured threshold recorded anywhere in the repository, and
inventing one now would add a row nothing checks. Stated rather than left blank, per §3.2c.
