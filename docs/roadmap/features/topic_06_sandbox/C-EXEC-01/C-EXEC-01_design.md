# Feature 3.20a: Internal Layer Enforcement (Tach)

- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_06_sandbox/C-EXEC-01/C-EXEC-01_design.md
Currently, SpecWeaver relies on standard Python linting (`ruff`) and `__init__.py` boilerplate
encapsulation to prevent architectural spaghetti. This is insufficient to guarantee that L3
Capabilities do not accidentally depend on L1 Interface dependencies. Feature 3.20a formally adopts
`Tach` (a Rust-based Python architectural linter) to mathematically enforce a strict Domain-Driven
"Layer Cake" architecture across the `src/specweaver/` directory.

## 2. Requirements & Constraints
### Functional Requirements

Rewritten into the ledger's table form 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-01-SF02-MIG`. **The four requirements were always here — as prose bullets (`**FR1:**`), which
`check_fr_coverage.py` and `check_fr_sweep.py` both read as no requirements at all**, because both
match `| FR-N |` table rows. So a capability with four declared FRs and eight committed sub-features
counted as a design with nothing to cite. Same class as `C-SENS-02`'s `_impl_plan.md` filenames: the
content was written, the gate could not see it.

Wording is preserved. FR-5 is new, and covers SF-08, which shipped with no requirement describing it.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | The layer cake is a declared artefact | System | `tach.toml` names each module and the modules it may depend on | The architecture is machine-checkable rather than a convention, and a config naming a module that does not exist is itself a failure |
| FR-2 | Boundaries are enforced, not documented | CI | Runs `tach check` over `src/specweaver/` | A forbidden upstream import fails the suite — at **zero** violations, not a baseline |
| FR-3 | Public surfaces are declared, not implied | System | `tach.toml`'s `interfaces:` blocks name what each module exposes | Importing a module's internals from outside is a violation, and a soft-deprecated name cannot be quietly re-exposed |
| FR-4 | A violation becomes a reviewable finding | Validation rule C05 | Reads the hydrated QA architecture result for a target project | Each boundary violation is reported as an ERROR `Finding` with a message, rather than an exit code nobody reads |
| FR-5 | A target project's topology becomes its `tach.toml` | Developer | Syncs a `TopologyGraph` into the analysed project's `tach.toml` | `context.yaml` boundaries are enforced by tach in that project too, with `[[modules]]` rebuilt from the graph rather than merged into stale ones |

**FR1 as originally worded — "`Tach` must be added as a dev-dependency" — is folded into FR-1.** A
dependency declaration has no independent failure: remove it and `tach check` cannot run, which is
FR-2's mutant. Keeping it as its own row would add one whose only observable consequence is another
row's.

### Two findings, both guards that had stopped guarding

**1. `tach check` was enforced against a baseline of 95 violations.**
`test_tach_architectural_boundaries` asserted `fail_count <= 95`, introduced 2026-05-25 (`07ce7544`)
when the debt was real. `tach check` now reports **zero**. The slack outlived the debt by nearly three
months, and it was not inert: a new cross-layer import — verified by mutation, `interfaces.cli`
imported into `graph.lineage.scanner`, whose `depends_on` is empty — passed the entire suite, as would
the next ninety-four. The assertion is now `returncode == 0`.

This is the shape worth naming. A stale threshold does not announce itself. The test kept passing, kept
appearing in the suite, and kept reading like enforcement, while the thing it enforced had moved.
`CLAUDE.md` states "No cross-layer imports" as a critical rule; nothing checked it.

**2. `test_tach_keeps_runner_soft_deprecated` had never run its assertion.**
It searched the `interfaces` blocks for `from = "src.specweaver.assurance.validation"`. `tach.toml`
sets `source_roots = ["src"]`, so its module paths begin at `specweaver.` — the string never matched,
the loop body never executed, and the test passed unconditionally. Verified: adding `runner` straight
back into the expose list passed the whole suite. Fixed, and it now also asserts that the block was
*found*, so the same drift cannot return it to silently passing.

Both were found the same way: a mutant that should have died and did not.

### Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | No `__init__.py` encapsulation hacks | Internal `__init__.py` proxy files and `__all__` re-export boilerplate are replaced by `tach.toml` `interfaces:` declarations. **[proof: meta — a one-time refactor over the tree, not a runtime behaviour; SF-06 removed the last 20, and FR-3's `interfaces:` blocks are what replaced them]** |
| NFR-2 | Enforced at the commit boundary | `tach check` runs as part of the commit-boundary gate. **[proof: meta — gate wiring, not product behaviour; `scripts/quality.py` registers `tach` at the `cb`, `sf` and `feature` gates, and `tests/unit/test_architecture.py` runs it inside the suite]** |

## 3. Codebase Patterns (Where to Implement)

To prevent breaking the CI pipeline, the implementation of Feature 3.20a must physically target the following files:

*   **SF-01 (Base Layer Initialization):**
    *   `pyproject.toml`: Add `tach` to dev dependencies.
    *   `tach.toml` (or `tach.yml`): Root configuration defining the Base Layer boundaries (`src.specweaver.core.config`, `src.specweaver.assurance.standards`).
*   **SF-02 (Resource/Capability Hardening):**
    *   `tach.toml`: Define Resource Layer (`src.specweaver.infrastructure.llm`, `src.specweaver.assurance.graph`) and block upward dependencies.
*   **SF-03 (Presentation Layer):**
    *   `tach.toml`: Define Presentation Layer (`src.specweaver.interfaces.api`, `src.specweaver.interfaces.cli`) and block internal logic from importing them.
*   **SF-04 (Interface Enforcement):**
    *   `tach.toml`: Enable `interfaces:` mapping.
    *   Delete `__init__.py` boilerplate across `src/specweaver/**`.

## 4. Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | **Standalone Refactor Feature** | Adopting Tach across the core architecture generates massive diffs. Sneaking it into 3.20b violates single-responsibility and destroys CI green-state reliability. It must be isolated as Feature 3.20a. | No |
| AD-2 | **Replacing `__init__.py`** | Use `Tach` `interfaces` mapping to formally define public module boundaries and delete messy `__init__.py` encapsulation hacks throughout `src/specweaver/`. | No |
| AD-3 | **Replacing Ruff TID252** | Drop Reliance on `ruff` tidy-imports in favor of true Domain-Driven Layer graphing via `Tach`. | No |

## 5. Sub-Feature Decomposition

| SF ID | Name | Description | Status |
|:---|:---|:---|:---|
| **SF-01** | Initialization & Base Layer Isolation | Install Tach. Map `config`, `standards`, and `logging.py` as strict base layers. Ensure they import absolutely nothing else from SpecWeaver. | [x] Committed |
| **SF-02** | Resource & Core Capability Hardening | Apply Tach rules to the `llm`, `graph`, `context`, and `project` modules. Formally isolate the `llm` engine from the business logic. | [x] Committed |
| **SF-03** | Presentation Layer Sterilization | Enforce that no domain logic inside `src/specweaver` is allowed to depend on `api` or `cli`. | [x] Committed |
| **SF-04** | Public Interface Enforcement | Use Tach's `interfaces:` to declare strict public boundaries and delete the messy `__init__.py` boilerplate hacks. | [x] Committed |
| **SF-05** | Legacy Linter Subsumption | Outsource manual architectural tests (soft-deprecations, cyclic guards) to Tach. | [x] Committed |
| **SF-06** | Global Implicit Namespace Conversion | Delete all 20 remaining internal `__init__.py` proxy files and enforce global `strict = true` topology using Tach. | [x] Committed |
| **SF-07** | Target Rule C05 Subsumption (Tach) | Gut the hardcoded AST parser inside `c05_import_direction.py`. Replace it with a subprocess execution of `tach check` on the target project, mapping structural boundary violations into standard SpecWeaver Findings. | [x] Committed |
| **SF-08** | TopologyGraph to Tach Adapter | Build an adapter or synchronization layer ensuring that when SpecWeaver maps `context.yaml` boundaries across a target codebase, a `tach.toml` is dynamically generated or synchronized behind the scenes. | [x] Committed |


## 6. Progress Tracker
- [x] Requirements Finalized
- [x] SF-01 Implementation (Committed)
- [x] SF-02 Implementation Plan
- [x] SF-02 Implementation (Committed)
- [x] SF-03 Implementation Plan
- [x] SF-03 Implementation (Committed)
- [x] SF-04 Implementation Plan
- [x] SF-04 Implementation (Committed)
- [x] SF-05 Implementation Plan
- [x] SF-05 Implementation (Committed)
- [x] SF-06 Implementation Plan
- [x] SF-06 Implementation
- [x] SF-07 Implementation Plan
- [x] SF-07 Implementation
- [x] SF-08 Implementation Plan
- [x] SF-08 Implementation
- [x] Feature 3.20a Fully Complete

## 7. Session Handoff

**Current status**: Feature 3.20a fully complete!
**Next step**: Proceed to next feature or `/dev` cycle.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
