# Context YAML Specification

**Status**: DRAFT, 2026-03-10. **Scope**: universal — a fractal boundary manifest for any
hierarchy level (system through sub-module) in every SpecWeaver-managed project.

| | |
|---|---|
| Protects | [Lifecycle Layers](../01_foundational_principles/lifecycle_layers.md) |
| Extends | [Codebase Context Specification (CCS)](https://github.com/Agentic-Insights/codebase-context-spec) |
| Gated by | [Spec Methodology](../04_pipelines_and_methodology/spec_methodology.md) — the 10-test battery that gates layer transitions |

## Overview

Any directory may hold a `context.yaml`. It declares:

1. identity — what this boundary is
2. public surface — what it exposes
3. whitelist — what it may depend on
4. archetype — what pattern it follows

Used for:

- **Semantic search** — agents find where new code goes by scanning `purpose` fields.
- **Pre-code validation** — proposed imports are checked against `consumes` and `forbids`.
- **Post-code validation** — generated code is checked against the archetype's structural constraints.

```
project/
├── context.yaml              ← level: system
├── billing-svc/
│   ├── context.yaml          ← level: service
│   └── domain/
│       ├── context.yaml      ← level: module
│       └── taxes/
│           ├── context.yaml  ← level: sub-module
│           └── vat.py
└── auth-svc/
    └── context.yaml          ← level: service
```

**Key principle**: One `context.yaml` per boundary. One archetype per boundary. If a directory needs two archetypes, split it into sub-directories.

## Relationship to CCS

CCS v1.1.0-RFC is a community standard for AI-readable metadata in codebases. `context.yaml` is
CCS-compatible and adds enforcement.

### CCS recap

CCS uses a `.context/` directory containing:
- `index.md` — YAML frontmatter (`module-name`, `description`, `related-modules`, `architecture`) plus prose overview
- `docs.md` — detailed documentation
- `diagrams/` — Mermaid diagrams

CCS supports three hierarchy levels (root → module → feature) with context inheritance.

### What CCS lacks

CCS is **documentation-only** — no enforcement:
- No dependency whitelisting (`consumes`)
- No forbidden import declarations (`forbids`)
- No structural pattern validation (`archetype`)
- No pre-code validation flow
- No semantic search for code placement

### Compatibility mapping

| CCS Field | SpecWeaver `context.yaml` | Notes |
|---|---|---|
| `module-name` | `name` | Identical semantics |
| `description` | `description` | Longer prose explanation |
| *(no equivalent)* | `purpose` | One-liner for semantic search |
| `related-modules` | `related-modules` | Cross-references, same format |
| `architecture.style` | `archetype` | CCS: descriptive. SpecWeaver: validated |
| `architecture.components` | Child `context.yaml` files | SpecWeaver uses hierarchy instead |
| `architecture.patterns` | `architecture.patterns` | Passed through unchanged |
| *(not in CCS)* | `level` | SpecWeaver extension |
| *(not in CCS)* | `consumes` | SpecWeaver extension |
| *(not in CCS)* | `forbids` | SpecWeaver extension |
| *(not in CCS)* | `exposes` | SpecWeaver extension |
| *(not in CCS)* | `constraints` | SpecWeaver extension |
| *(not in CCS)* | `owner` | SpecWeaver extension |

A SpecWeaver `context.yaml` can be losslessly converted into CCS `index.md` frontmatter. The reverse conversion loses enforcement fields.

## Schema

### Full example

```yaml
# ── Identity ──────────────────────────────────────────────
name: tax-calculator                  # REQUIRED — unique within parent
level: module                         # REQUIRED — see Level Enum
purpose: >                            # REQUIRED — one sentence, semantic-searchable
  Pure VAT/GST calculation logic for EU digital services.

# ── CCS-compatible ────────────────────────────────────────
description: |                        # OPTIONAL — longer prose
  Implements EU VAT Directive 2006/112/EC for digital services.
  Supports standard, reduced, and zero rates per member state.

related-modules:                      # OPTIONAL — cross-references
  - name: currency-utils
    path: ../shared/currency

architecture:                         # OPTIONAL — structural docs
  style: functional
  patterns:
    - name: Strategy Pattern
      usage: Rate selection per country

# ── Enforcement ───────────────────────────────────────────
archetype: pure-logic                 # REQUIRED — see Archetype Enum

consumes:                             # OPTIONAL — whitelist of allowed dependencies
  - shared/currency                   #   Paths relative to project root
  - shared/types                      #   Wildcard: "shared/*" allowed

forbids:                              # OPTIONAL — explicit deny list
  - infra/*                           #   Hard deny even if parent consumes it
  - "*.orm"                           #   Pattern-based: no ORM imports

exposes:                              # OPTIONAL — public surface
  - TaxCalculator
  - TaxResult
  - RateTable

owner: billing-team                   # OPTIONAL — escalation target

constraints:                          # OPTIONAL — free-form rules for agent/veto
  - "No mutable global state"
  - "All functions must be pure (no side effects)"

# ── Operational Metadata ──────────────────────────────────
operational:                          # OPTIONAL — runtime/SLA characteristics
  multi_tenant_ready: true            #   Does this module handle tenant isolation?
  latency_critical: false             #   Is this on a latency-sensitive path?
  max_latency_ms: 200                 #   SLA warranty: max acceptable P99 latency
  data_freshness: batch               #   realtime | near-realtime | batch | static
  reliability_target: 0.999           #   Target availability (0.0-1.0)
  async_ready: true                   #   Does this module support async/await?
  concurrency_model: asyncio          #   asyncio | threading | process | none

# ── External Model Context (MCP) ──────────────────────────
mcp_servers:                          # OPTIONAL — External Context providers
  postgres-dwh:                       #   Alias for the server instance
    command: "docker"
    args: ["run", "-i", "--rm", "mcp/postgres"]
    env:
      DB_PASS: "${vault.DB_PASS}"     # Native substitution via vault.env

consumes_resources:                   # OPTIONAL — Pre-fetch URIs before generation
  - "postgres://schema/public"        # Evaluated and injected into Agent Envelope
```

### Required fields

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Unique name within the parent boundary |
| `level` | `Level` | Hierarchy position (see Level Enum) |
| `purpose` | `string` | One sentence describing responsibility. Used for semantic search |
| `archetype` | `Archetype` | Structural pattern this boundary follows (see Archetype Enum) |

### Optional fields

| Field | Type | Description |
|---|---|---|
| `description` | `string` | Extended prose. Maps to CCS `index.md` body |
| `related-modules` | `list[{name, path}]` | Cross-references. Maps to CCS `related-modules` |
| `architecture` | `object` | Structural docs. Maps to CCS `architecture` |
| `consumes` | `list[string]` | Whitelist of paths this boundary may import from. Supports `*` wildcards |
| `forbids` | `list[string]` | Explicit deny list. Overrides `consumes` and parent-level permissions |
| `exposes` | `list[string]` | Public symbols (classes, functions, constants) |
| `owner` | `string` | Team or person responsible for this boundary |
| `constraints` | `list[string]` | Free-form rules that the Veto Agent checks against |
| `operational` | `object` | Runtime/SLA characteristics (see Operational Metadata below) |
| `mcp_servers` | `object` | Definitions for external Model Context Protocol processes |
| `consumes_resources` | `list[string]` | MCP URIs strictly injected as pre-fetched schemas before Agent execution |

## Operational Metadata

Runtime and SLA characteristics of a boundary. **Not enforced at code level** — metadata read by:

- **Spec drafting agents** — to understand latency budgets and tenant requirements when writing specs
- **Topology analysis** — to detect SLA mismatches (e.g., a latency-critical service consuming a batch-only data source)
- **Qdrant enrichment** — to enable filtered semantic search ("find me a realtime, tenant-aware API")

| Field | Type | Default | Description |
|---|---|---|---|
| `multi_tenant_ready` | `bool` | `false` | Does this module handle tenant isolation (tenant IDs in params/context)? |
| `latency_critical` | `bool` | `false` | Is this module on a latency-sensitive execution path? |
| `max_latency_ms` | `int` | *(none)* | SLA warranty: maximum acceptable P99 latency in milliseconds |
| `data_freshness` | `enum` | *(none)* | Data recency requirement. Values: `realtime`, `near-realtime`, `batch`, `static` |
| `reliability_target` | `float` | *(none)* | Target availability as a decimal (e.g., `0.999` = 99.9% uptime) |
| `async_ready` | `bool` | `false` | Does this module support `async/await`? Used by the flow engine to decide parallel execution |
| `concurrency_model` | `enum` | `none` | Concurrency strategy. Values: `asyncio`, `threading`, `process`, `none` |

> [!NOTE]
> These fields are optional and only relevant for service/module boundaries with runtime behavior.
> Pure library or contract boundaries typically omit this section. Projects should define which
> fields are required for their domain in the system-level `context.yaml`.

### Operational inheritance

- `multi_tenant_ready` — **not inherited**. Each module explicitly declares tenant support.
- `latency_critical` — **inherited downward**. If parent is critical, children are critical unless they explicitly override with `false`.
- `max_latency_ms` — **inherited with tightening**. A child can set a stricter (lower) value but cannot relax the parent's constraint.
- `data_freshness` — **not inherited**. Each module declares its own data recency needs.
- `reliability_target` — **inherited with tightening**. A child can increase but not decrease the parent's target.
- `async_ready` — **not inherited**. Each module explicitly declares async support. A parent being async-ready does not imply children are.
- `concurrency_model` — **not inherited**. Each module declares its own concurrency strategy.

## Level Enum

The `level` field is always explicit. SpecWeaver does not infer it from nesting depth.

| Value | Description | Typical usage |
|---|---|---|
| `system` | Top-level orchestration (multi-service) | Project root |
| `service` | A deployable unit or microservice | Service directory |
| `meta-module` | A group of related modules | Package directory |
| `module` | A single functional unit | Feature directory |
| `sub-module` | A subdivision within a module | Sub-package or file group |

### Context inheritance

Each boundary inherits its parent's context:

- **`consumes`** — a child can narrow but not widen its parent's whitelist. If the parent allows `shared/*`, a child can restrict to `shared/currency` but cannot add `infra/*`.
- **`forbids`** — a child can add to the deny list but not remove from it. Forbidden items are cumulative going down the tree.
- **`archetype`** — not inherited. Each boundary declares its own.
- **`constraints`** — cumulative. A child inherits parent constraints and can add new ones.
- **`operational`** — per-field rules (see Operational Metadata above).

## Archetype Enum

What a boundary may structurally contain. **Exactly one** per boundary; a directory with two
patterns is split into sub-directories.

### Built-in archetypes

| Archetype | Allowed | Forbidden | Validation rule |
|---|---|---|---|
| `pure-logic` | Business logic, calculations, transformations, value objects | DB drivers, HTTP clients, I/O, framework imports | No imports from `infra/*` or `adapter/*` paths |
| `adapter` | Framework wrappers, external library integration | Direct business logic | Must implement an interface from a `contract` boundary |
| `facade` | Thin delegation, method signatures only | Implementation logic, private helpers, complex logic | Methods must delegate; no private methods with logic |
| `contract` | Interfaces, Protocols, DTOs, constants, type definitions | Any implementation code | No method bodies (abstract / Protocol only) |
| `entry-point` | CLI handlers, API routes, Lambda handlers | Business logic, DB access | Must delegate to `pure-logic` or `adapter` boundaries |
| `orchestrator` | Workflow coordination, event routing, pipeline assembly | Direct data transformation or computation | Calls other modules; does not compute |
| `store` | Persistence logic (SQL, ORM, file I/O) | Business rules | Must live behind a `contract` interface |
| `mixed` | No restrictions (escape hatch for transitional code) | — | No automated archetype validation |

### Custom archetypes

Projects can define custom archetypes in their root-level `context.yaml`:

```yaml
name: my-project
level: system
purpose: "E-commerce platform"
archetype: orchestrator

custom-archetypes:
  report-generator:
    allowed:
      - "Template rendering"
      - "Data formatting"
    forbidden:
      - "Direct DB access"
      - "Business logic"
    validation: "Must use the ReportTemplate base class"
```

Children can then use `archetype: report-generator`.

### The single-archetype rule

Every `context.yaml` declares exactly one archetype, because:

1. **Validation clarity** — multiple archetypes make it ambiguous which rules apply to which file.
2. **Fractal decomposition** — needing two archetypes signals a boundary that should be split:

```
# ✗ WRONG — mixed responsibilities
tools/git/
├── context.yaml          # archetype: ??? (facade + adapter)
├── interfaces.py         # facade behavior
└── executor.py           # adapter behavior

# ✓ RIGHT — one archetype per boundary
tools/git/
├── context.yaml          # archetype: facade
├── interfaces.py
├── tool.py
└── executor/
    ├── context.yaml      # archetype: adapter
    └── executor.py
```

3. **The `mixed` escape** — for existing code that hasn't been split yet, `archetype: mixed` disables validation without lying about the structure.

## Semantic Search for Code Placement

`purpose` is the search key. To place new code, SpecWeaver:

1. Scans all `context.yaml` files in the project
2. Embeds each `purpose` field (cheap — one sentence each)
3. Ranks by semantic similarity to the agent's task description
4. Returns the top matches with their archetype and dependency rules

```
Agent request: "I need to add a VAT calculator class"

Search results:
┌───────────────────────────────────────────────────────────┐
│ 1. src/domain/billing/taxes/context.yaml         (0.94)  │
│    purpose: "VAT/GST calculation for EU digital services" │
│    archetype: pure-logic                                  │
│    consumes: [shared/currency]                            │
├───────────────────────────────────────────────────────────┤
│ 2. src/domain/billing/context.yaml               (0.71)  │
│    purpose: "Invoice generation and billing state"        │
│    archetype: pure-logic                                  │
│    consumes: [shared/currency, shared/types]              │
├───────────────────────────────────────────────────────────┤
│ 3. src/infra/tax-api/context.yaml                (0.65)  │
│    purpose: "External tax rate API integration"           │
│    archetype: adapter                                     │
│    consumes: [domain/billing/taxes]                       │
└───────────────────────────────────────────────────────────┘
```

The agent takes the top match, checks the archetype constraints, and proceeds only if location and
code pattern are both valid.

## Pre-Code Validation Flow

Before any code is written, the proposal is checked against the boundary rules:

```
Agent proposes: "I will create VatCalculator.py in src/domain/billing/taxes/"

Step 1: Find nearest context.yaml
  → src/domain/billing/taxes/context.yaml
  → archetype: pure-logic
  → consumes: [shared/currency]
  → forbids: [infra/*]

Step 2: Check proposed imports
  → import shared.currency.convert   ✓ (in consumes)
  → import sqlalchemy                ✗ REJECT (infra dependency in pure-logic)

Step 3: Check archetype rules
  → File contains only pure functions  ✓
  → No I/O or global state             ✓

Result: PROCEED / REJECT with specific reason
```

Token savings: a rejected proposal costs ~100 tokens. A full implementation followed by rejection costs ~5,000+ tokens.

## Post-Code Validation

After generation, mechanical checks (no LLM):

| Check | Method | Cost |
|---|---|---|
| Import whitelist | Parse imports, compare to `consumes` | Free (AST parse) |
| Import deny list | Parse imports, compare to `forbids` | Free (AST parse) |
| Dependency direction | Check imports don't go "upward" in level hierarchy | Free (path comparison) |
| Archetype structure | Apply archetype-specific rules (see Archetype Enum table) | Free (AST analysis) |
| Constraint violations | Feed `constraints` to Veto Agent for semantic check | ~200 tokens per constraint |

## Ownership & Responsibility

**Rule: no directory with source code exists without a `context.yaml`.** Who writes it depends on
the lifecycle layer; the next layer's review gates it.

| Layer | Who writes `context.yaml`? | Gate |
|---|---|---|
| **L1** (Business) | — | Not applicable |
| **L2** (Architecture) | Architect (HITL) defines top-level boundaries | HITL approval |
| **L3** (Specification) | Agent proposes module structure + `context.yaml` | Spec review |
| **L4** (Implementation) | Agent creates `context.yaml` for any new directory | Pre-code validation |
| **L5** (Review) | Reviewer agent validates `context.yaml` consistency | Review checklist |

### Creation scenarios

| Scenario | Who creates `context.yaml` |
|---|---|
| New project scaffolded by SpecWeaver | `sw init` generates them from the architecture in the project spec |
| Existing project adopting SpecWeaver | An agent crawls imports and folder structure and proposes them; the architect approves |
| Ongoing evolution | A new directory at L4 must come with a `context.yaml` in the proposal; pre-code validation rejects a directory without one |

## Protection Model

An agent that can edit `context.yaml` can grant itself permissions. Protection reuses the git tool
layer's interface-level invisibility pattern.

### The filesystem tool parallel

The filesystem tool follows the same 4-tier architecture as the git tool:

| Git Tool Pattern | Filesystem Tool Equivalent |
|---|---|
| `GitExecutor` whitelist → only allowed commands | Filesystem executor → only allowed operations **within boundary** |
| `_BLOCKED_ALWAYS` → push, merge, rebase | `_PROTECTED_PATTERNS` → `context.yaml` |
| `EngineGitExecutor` bypasses blocklist | `EngineFileExecutor` bypasses protected patterns (engine-only, no agent access) |
| Role-specific interfaces hide methods | Role-specific interfaces hide file operations |

### Agent permissions

Non-permitted operations are **invisible** (the method does not exist on the interface), not merely
blocked at runtime.

```
ImplementerFileInterface:
  ✓ new_file("src/domain/vat.py")     → within boundary, allowed
  ✓ modify("src/domain/vat.py")       → within boundary, allowed
  ✗ new_file("src/infra/hack.py")     → outside boundary, INVISIBLE
  ✗ modify("context.yaml")            → protected file, INVISIBLE
  ✗ remove("context.yaml")            → protected file, INVISIBLE

BoundaryArchitectInterface:
  ✓ new_file("new_module/context.yaml")  → explicitly whitelisted
  ✓ modify("context.yaml")              → explicitly whitelisted
  ✗ modify("src/domain/vat.py")         → not this agent's job
```

### Defense layers

| Layer | Mechanism | Cost |
|---|---|---|
| **Interface invisibility** | `context.yaml` write methods absent from standard interfaces | Free (compile-time) |
| **Git diff detection** | Reviewer agent flags `context.yaml` in changeset → escalate to HITL | Free (mechanical) |
| **Role separation** | Only `BoundaryArchitectInterface` has write access to `context.yaml` | Free (architectural) |
| **Hash verification** *(optional)* | `context.lock` stores SHA-256 hashes; validate before any run | Free (mechanical) |

`context.yaml` is both the **rule definition** and the **enforcement input**: it declares what its
boundary allows and is itself protected by the system it defines.

## Implementation in SpecWeaver

| Component | Responsibility | Built (2026-09-25) |
|---|---|---|
| **Filesystem Tool** (`sandbox/filesystem/`) | `find_placement(description)` — scans `context.yaml` files and returns ranked placements | yes — `interfaces/tool.py` |
| **Filesystem Atom** (`sandbox/filesystem/`) | `scaffold()` — creates directories + `context.yaml` from boundary defs; `validate_boundaries()` — pre-code validation | yes — `scaffold` / `validate_boundaries` intents in `core/atom.py` |
| **Validation Rules** (`specweaver/validation/`) | `context_yaml_lint(path)` — structural validation of the YAML file itself | no |
| **CLI** | `sw context validate` — check all `context.yaml` files in a project for consistency | no |

Also not built: `BoundaryArchitectInterface` and `context.lock`. `_PROTECTED_PATTERNS` and
`EngineFileExecutor` exist in `sandbox/filesystem/core/executor.py`.

## Open Questions

1. **Glob syntax** — Should `consumes` and `forbids` use simple `*` wildcards or full glob patterns (`**/*.py`)?
2. **Version field** — Should `context.yaml` include a schema version for forward compatibility?
3. **Tags** — Should there be a `tags` field for more flexible semantic search beyond `purpose`?
4. **Conflict resolution** — When a child's `consumes` conflicts with a parent's `forbids`, which wins? (Current rule: `forbids` always wins.)
5. **Spec → scaffold pipeline** — When the drafter/spec authoring workflow creates a new component
   spec, the spec must define boundary information (name, level, purpose, archetype, consumes,
   forbids). How this is formatted in the spec template, and how the Engine parses it to call
   `FileSystemAtom.scaffold()`, is not yet defined. This is a prerequisite for the drafter workflow.
