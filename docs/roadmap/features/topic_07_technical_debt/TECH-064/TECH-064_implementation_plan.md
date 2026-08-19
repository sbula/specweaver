# Implementation Plan: TECH-064

- **Feature ID**: TECH-064
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — the parser bug and the two silent stubs

| Task | FR | Change |
|---|---|---|
| T1 | FR-1 | `KotlinCodeStructure.SCM_IMPORT_QUERY`: `(import_header)` → `(import)`, the node type this grammar actually emits |
| T2 | FR-2 | `ArchitectureRunResult` gains `note: str = ""`, the same disclosure shape as `TestRunResult.toolchain_note` |
| T3 | FR-2 | `KotlinRunner` and `RustRunner` `run_architecture_check` set `note`, and say in the docstring why they return rather than raise |
| T4 | FR-3 | `QARunnerAtom._intent_run_architecture` reports `Architecture check did not run: …` and exports `note` |
| T5 | FR-2 | The guard: every language runner either performs the check or sets a `note`, detected by an unconditional return in the parsed method body |

**Order.** T1 first, because it is the one item with no scope question attached. T5 was written
before T2–T4 and failed on Kotlin and Rust — and on Java, which is how the discriminator was
corrected from "returns an empty result" to "returns unconditionally".

**Why T4 is not optional.** T2 and T3 alone would add a field nothing reads. The atom's message is
what a reader acts on, so leaving it saying "No architectural violations" would have closed the
ticket on paper with the lie intact.
