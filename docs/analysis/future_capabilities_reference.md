# Future Capabilities Reference — Extracted Patterns for Post-MVP

> **Status**: REFERENCE — Ideas to revisit when building RAG, agent isolation, verification gates, and multi-project support.
> **Date**: 2026-03-08
> **Sources**: flowManager `rag_analysis.md`, `rag_architecture.md`, `agent_isolation.md`, `verification_gates_backlog.md`, `validation_gate_proposal.md`, `verifiable_agentic_orchestration.md`, `methodology_open_research.md`, `v_next_architecture_proposal.md`, `bad_ideas_and_traps_to_avoid.md`
> **MVP Impact**: None — all items are post-MVP. This doc exists so we don't lose good ideas.

---

## 1. Tiered RAG Access Rights (Zero-Trust Knowledge)

**The Core Idea**: Prevent "God-Object" agents that hallucinate capabilities by seeing internals they shouldn't know about.

Every RAG query includes an `agent_scope` parameter. The knowledge service filters results based on the agent's tier:

| Tier | Scope | Sees | Does NOT See |
|:---|:---|:---|:---|
| **Internal** | Own module/service | Full AST: public + private symbols, DB schema, call graph | — |
| **Contract** | Other module/service | Public API only: interfaces, exported types, event schemas | Private methods, internal classes, implementation logic |
| **Architectural** | System-wide consulting | Service topology, event schemas, data flow direction | Any code, any implementation details |

**Why this matters for SpecWeaver**: When agents generate code, they should only see the **public interfaces** of other modules, not their internals. This enforces contract-driven development and prevents tight coupling.

**Implementation sketch**:
- All symbols in the index carry a `visibility` field and a `namespace` (owning module)
- RAG queries include `agent_scope: { module: "validation", tier: "internal" }`
- Cross-module edges (function calls, imports) are always visible — they represent the *contract*

---

## 2. Hierarchical Hashing (L1/L2/L3 Drift Detection)

**The Core Idea**: Not all code changes are equal. Distinguish implementation changes from API changes from breaking contract changes.

| Level | What's Hashed | RAG Impact on Change |
|:---|:---|:---|
| **L1: Implementation** | Function body (local vars, control flow) | None — no re-index, but may trigger test re-run |
| **L2: Signature** | Normalized name + params + return type + visibility | RAG entry invalidated; consumers alerted |
| **L3: Contract** | Public interface surface (proto, exported types) | Breaking change notification; full downstream audit |

**Benefits**:
- Prevents over-indexing: only L2/L3 changes trigger re-embedding (~60-80% fewer updates)
- Enables precise drift detection: "harmless refactoring" vs "API break"
- Supports git-committed index with minimal diffs

**Implementation**: Before hashing, signatures are normalized (stripped of comments, whitespace, formatting) for stable hashes. Python uses `ast.parse()`.

---

## 3. AST-Based Semantic Chunking

**The Core Idea**: Don't split code by token count. Parse it into semantic units using AST.

- **Tree-sitter** (or Python `ast`) parses code into function/class boundaries
- Each chunk is a complete, structurally valid code unit
- Agents always receive full functional blocks, never half-broken methods
- Metadata per chunk: language, file path, imports, visibility, parent class

**Hybrid strategy**:
1. **For code**: AST-based chunking + multi-vector (semantic summary + structural fingerprint)
2. **For docs/specs**: Markdown header-based splitting (H2/H3 sections)

---

## 4. Cross-Module Symbol Linking

**The Core Idea**: Track inter-module relationships explicitly so agents understand call chains.

```
.specweaver/
  symbol_index/
    validation_module.symbols.json
    drafting_module.symbols.json
    cross_module_edges.json    # imports, function calls between modules
```

**Relation types**:

| Relation | Example |
|:---|:---|
| `imports` | `validation.runner` → `validation.models.Rule` |
| `calls` | `cli.validate_cmd` → `validation.runner.run_all` |
| `implements` | `rules.s01_one_sentence` implements `validation.models.Rule` |

**Ghost signatures**: When a public symbol is deleted, keep it as a ghost entry for N commits so agents can discover "this was deleted in commit X, replacement is Y."

---

## 5. Context Budget Management

**The Core Idea**: Prevent RAG retrieval from overwhelming the LLM context window.

```yaml
knowledge:
  max_retrieval_chunks: 10
  max_retrieval_tokens: 4096
  max_symbols_per_request: 20
  retrieval_radius: module    # module | package | project
```

**Budget enforcement strategies**:
- **Top-K hard cap**: Never return more than N chunks
- **Retrieval radius**: Limit search scope (current module vs whole project)
- **Summary fallback**: If raw code exceeds token budget, replace with signature summary

---

## 6. Agent Isolation Patterns

**The Core Idea**: Prevent groupthink and context contamination between agents working on different concerns.

### Branch Separation
Each agent gets a unique `branch_id`. Agent A cannot see Agent B's prompt or conversation history. Parallel execution prevents sequential bias.

### Stage-Agnostic Personas
Expert identity (WHO they are) is defined separately from task criteria (WHAT they do). Same expert, different stages get different success criteria.

### Adversarial Review Phase
After synthesis, a dedicated critic agent attacks the output:
- **Structurally forbidden from approving** — output schema has no "APPROVE" option
- **Minimum issue threshold**: Must find ≥3 issues
- **Clean slate protocol**: Spawned in fresh context with no collaborative history
- **Evidence-grounded**: Every claim must cite specific file/line

### Rubric-Based Scoring
Replace qualitative "You FAILED if..." with numeric rubrics:

| Dimension | Weight | Min Threshold (1-5) |
|:---|:---|:---|
| Completeness | 0.3 | 3 |
| Specificity | 0.3 | 4 |
| Actionability | 0.2 | 3 |
| Risk identification | 0.2 | 3 |

If weighted average < overall threshold → auto-loop. After max loops → escalate to HITL.

---

## 7. Mock-First Protocol (Interface Before Implementation)

**The Core Idea**: Before an agent writes implementation code, it must first define the interface/contract.

1. Agent defines interface (class signatures, function stubs)
2. Commits interface to symbol index
3. Only then proceeds to implementation
4. Validation Gate has a target to validate against *during* implementation

**Benefits**:
- Multiple agents can work in parallel — one defines interface, others implement against it
- Contract-first development prevents tight coupling
- Validation Gate can reject code that doesn't match the declared interface

---

## 8. Filesystem Scoping for Agents

**The Core Idea**: Different agents working on different modules get different filesystem permissions.

```yaml
expert_config:
  validation_developer:
    tools:
      - name: read_file
        allowed_paths: ["./src/specweaver/validation/", "./docs/", "./tests/"]
      - name: write_file
        allowed_paths: ["./src/specweaver/validation/"]
        blocked_patterns: ["*.env", "pyproject.toml"]
```

Tool wrappers resolve absolute paths and validate against `allowed_paths` BEFORE execution. Attempts outside scope raise `SecurityError`.

---

## 9. LLM Model Parameter Overrides per Role

**The Core Idea**: Different cognitive tasks benefit from different model parameters.

| Role Category | Temperature | Rationale |
|:---|:---|:---|
| Analytical (QA, Architect) | 0.0 – 0.2 | Minimize creativity, maximize precision |
| Structural (Review, Validation) | 0.2 – 0.4 | Balance thoroughness and exploration |
| Creative (Drafting, UX) | 0.4 – 0.7 | Allow exploratory suggestions |
| Adversarial (Critic) | 0.0 – 0.2 | Rigorous, evidence-based criticism |

**Override precedence**: Default (global) → Role persona → Expert set (highest priority).

---

## 10. Deterministic Feature Vectors (No-LLM Embedding)

**The Core Idea**: For environments where LLM-based embedding is too slow or expensive, support deterministic feature vectors derived purely from AST properties.

- Fixed 256-dimension vector: symmetry bits (32) + identity hash (64) + structural fingerprint (160)
- Same code always produces the same vector — no API cost, fully reproducible
- Cannot find "similar intent" — only structurally similar code
- Use as secondary vector alongside LLM-generated semantic vectors for dual-track search

---

## Mapping to SpecWeaver Future Features

| Pattern | Maps to SpecWeaver Feature | When |
|:---|:---|:---|
| Tiered access rights (§1) | Context provider with scope filtering | Post-MVP: RAG provider |
| Hierarchical hashing (§2) | Code validation rule upgrades | Post-MVP: advanced C05/C08 rules |
| AST-based chunking (§3) | FileSearchProvider implementation | Post-MVP: RAG provider |
| Cross-module linking (§4) | Dependency direction validation (S04/C05) | Could enhance MVP rules |
| Context budget (§5) | LLM adapter configuration | Post-MVP: multi-model support |
| Agent isolation (§6) | Multi-agent review flows | Post-MVP: L5 review layer |
| Mock-first protocol (§7) | Implementation flow (F5) enhancement | Post-MVP |
| Filesystem scoping (§8) | Agent tool sandboxing | Post-MVP: L4-L5 |
| Model param overrides (§9) | LLM adapter per-task config | Post-MVP: multi-model routing |
| Deterministic vectors (§10) | Local-first RAG fallback | Post-MVP: offline mode |
| Symbol index / anti-hallucination (§11) | Code review via symbol validation | Post-MVP: F7 Code Review |
| Same-error abort & context reset (§12) | LLM retry strategies | Post-MVP: F2/F5 robustness |
| Diff-explosion guard & assertion density (§13) | Code review quality gates | Post-MVP: F7 Code Review |
| Mutation testing (§14) | Test quality verification | Post-MVP: advanced verification |
| Cross-model shadow reviewers (§15) | Review pipeline model diversity | Post-MVP: F4/F7 review |
| Blast radius / locality enforcement (§16) | Implementation scope control | Post-MVP: F5 implementation |
| Spec-to-code traceability (§17) | Bidirectional spec↔code linking | Post-MVP: `sw check` enhancement |
| Automated decomposition (§18) | Feature → Component spec splitting | Post-MVP: F2 Spec Drafting |
| Domain profiles (§19) | Per-project threshold calibration | Could enhance MVP `sw check` |

---

## 11. Anti-Hallucination Symbol Index (`.machine-doc/`)

*Source: `validation_gate_proposal.md`*

**The Core Idea**: A deterministic, git-committed directory containing the machine-readable representation of the codebase. The Validation Gate intercepts all agent write operations and validates against this index.

```
.machine-doc/
  schema_version.json       # index format version
  symbols.json              # all extracted symbols (functions, classes, methods)
  edges.json                # call graph, inheritance relationships
  file_hashes.json          # per-file hash for incremental updates
```

**Key design decisions**:
1. **Committed to git** — every branch has its own symbol state
2. **Deterministic output** — same code always produces same index (sorted, canonical JSON)
3. **Incremental** — only changed files are re-parsed via content hash comparison
4. **Not an LLM artifact** — purely AST-based extraction, no embeddings

**Gate behavior**: When an agent writes code referencing `UserService.deleteAccount()` and that symbol doesn't exist → structured JSON error back to agent. No prose, just actionable data for targeted correction.

**Phased implementation**: Python `ast` (Phase 1) → Tree-sitter (Phase 3) → polyglot (future).

---

## 12. Same-Error Abort & Context-Window Reset

*Source: `verification_gates_backlog.md` — F1, F2*

**Same-Error Abort (3-Strike Rule)**: If an agent produces the same error 3 times in a row, abort. LLMs almost never self-correct after 3 identical failures — they oscillate and burn tokens.
- Store hash of last N error messages in retry context
- Content-based deduplication, not just count-based

**Context-Window Reset on Retry**: On retry, provide ONLY the current broken code + current error. Deliberately discard failure history. Each retry is a "fresh start."
- Transformer attention gives disproportionate weight to accumulated failure patterns
- An agent seeing "you failed 3 times" fixates on failure framing, not the actual problem

---

## 13. Diff-Explosion Guard & Assertion Density Gate

*Source: `verification_gates_backlog.md` — F3, F4*

**Diff-Explosion Guard**: If an agent rewrites >X% of a file (default: 40%) to fix a small error, reject the edit. Massive rewrites signal context pollution — the agent has lost track and is "shotgun rewriting."

**Assertion Density Gate**: Count assertion calls vs. lines of code in test files:
```
Density = AssertionCalls / TestLOC
```
- Density < 0.05 (one assertion per 20 lines): likely a "ghost test"
- Density < 0.02: almost certainly fake — flag as `GHOST_TEST`
- Cheap static check that filters the worst before expensive mutation testing

---

## 14. Mutation Testing (Diff-Only)

*Source: `verification_gates_backlog.md` — F11, `verifiable_agentic_orchestration.md` §5*

**The Core Idea**: After tests pass, inject small logic bugs (operator swaps, boundary shifts) into the diff and re-run tests. If tests still pass (failing to catch the mutant), the test suite is fraudulent.

```
Mutation Score = Killed / (Total - Equivalent)
Target: MS > 85%
```

**Key optimization**: Run mutation testing ONLY on the git diff (changed lines), not the entire codebase. Use language-specific mutation drivers (`mutmut` for Python, `cargo-mutants` for Rust).

**Performance guards**: Skip if >5 changed files. Hard 5-minute timeout. Stop if mutation score hasn't improved by >2% over last two iterations.

---

## 15. Cross-Model Shadow Reviewers

*Source: `verifiable_agentic_orchestration.md` §6*

**The Core Idea**: Use different LLM models for implementation and review. The same model reviewing its own code leads to "Collaborative Hallucination."

- Step 1: Coding agent (e.g., Claude) outputs a diff
- Step 2: Review agent (e.g., Gemini) receives ONLY the diff + requirements, with NO prior chat history
- This creates a "Blind Auditor" with genuine independence and fresh context

---

## 16. Deterministic Blast Radius (Locality Enforcement)

*Source: `verifiable_agentic_orchestration.md` §4*

**The Core Idea**: When an agent is authorized to modify `calculateAlpha()`, reject any diff that also touches unrelated `saveToDatabase()`. AST locality checks enforce that modifications stay within the assigned scope.

```
Error: Locality violation. You modified lines outside your assigned scope.
```

Prevents "collateral damage" — agents reformatting, pruning imports, or modifying siblings due to context bias.

---

## 17. Spec-to-Code Traceability

*Source: `methodology_open_research.md` §4*

**The Core Idea**: Bidirectional links between specs and source files, kept in sync.

**Spec → Code** (in the spec):
```markdown
## Implementation References
- `src/specweaver/validation/runner.py` — validation execution
- `tests/test_validation.py` — test coverage
```

**Code → Spec** (in the code):
```python
"""Spec: docs/specs/validation.md §2 (Contract)"""
```

**Automation opportunities**:
- Link rot detection (pre-commit hook)
- Coverage gap detection (spec interface vs actual implementation)
- Drift detection (spec Contract vs code's actual interface via AST)

---

## 18. Automated Decomposition (Feature → Component Specs)

*Source: `methodology_open_research.md` §1*

**The Core Idea**: Can an agent read a Feature Spec and propose the decomposition into Component Specs?

**Answer**: Yes, with constraints:
1. Agent needs the Component Hierarchy Map as input
2. Agent proposes, HITL decides — never auto-decompose without review
3. Each resulting component must pass Structure Tests 1-5
4. Must check: "does the decomposition cover 100% of the Feature Spec's Change Map?"

**DMZ pattern**: `auto-create-issues.sh` reads ALL docs + ALL existing issues → creates one issue with acceptance criteria → deduplicates → loops until agent outputs DONE 3 consecutive times.

---

## 19. Domain Profiles for Threshold Calibration

*Source: `methodology_open_research.md` §6*

**The Core Idea**: Validation thresholds may need per-domain tuning.

| Domain | Adjustment |
|:---|:---|
| **RFC-style** (networking) | Don't flag "should" — it has specific RFC 2119 meaning |
| **Regulated** (healthcare, finance) | Stricter error paths (≥3 per interface), done = compliance |
| **Safety-critical** (embedded) | Zero ambiguity tolerance at ALL levels |
| **Data science / ML** | Allow stochastic protocol sections, statistical "done" criteria |

**Implementation**: Define domain profiles (threshold overrides). Projects select via Constitution. `sw check --profile=regulated`.

---

## 20. Anti-Patterns Catalog

*Source: `bad_ideas_and_traps_to_avoid.md`, `verifiable_agentic_orchestration.md`*

Critical "what NOT to do" insights collected from flowManager's development:

| Anti-Pattern | Why It's Dangerous |
|:---|:---|
| **Co-locating tool with target project** | Agents can modify SpecWeaver's own Validation Gate or engine |
| **Shared chat contexts during reviews** | Mode collapse — reviewers agree with each other |
| **Agent-authored specs** | Hallucinated spec → Validation Gate perfectly enforces a broken architecture |
| **Naive text splitting for RAG** | Destroys architectural invariants; AST parsing mandatory |
| **Infinite regeneration loops** | No structured error feedback = blind retry = burnt tokens |
| **Committing vector DB to git** | Merge conflicts; commit only deterministic JSON `.machine-doc/` |
| **Polyglot hallucination** | Agent writes Kotlin-style logic in Rust; filter RAG by target language |
| **Graph explosion in legacy** | Hard-cap retrieval radius (`radius=1`, `max_symbols=20`) |
| **Version ghost trap** | Agent code based on stale index; validate `index_version` matches |
| **Spec degradation to fuzzy prose** | Validation Gate loses leverage; enforce machine-readable schemas |
| **Over-specifying implementation** | Prescribing private method names constrains agent unnecessarily |
| **3-Line Pragma omission** | Every module needs Intent + Pre-conditions + Post-conditions |

