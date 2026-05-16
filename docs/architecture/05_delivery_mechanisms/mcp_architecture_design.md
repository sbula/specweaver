# MCP Architecture Blueprint: Features 3.32c and 3.32c-1 (Red-Team Approved)

This document maps out the final, securely vetted design for implementing the **Model Context Protocol (MCP)** in SpecWeaver, effectively eliminating "Blank Canvas Syndrome" and target environment hallucinations.

---

## 1. Feature 3.32c: Common MCP Client Architecture

**Goal:** Implement the JSON-RPC protocol natively into SpecWeaver while guaranteeing Zero-Trust security and solving LLM latency.

### The "Pre-Fetched Context Envelope" Pattern (Solving Token Bloat)
Instead of exposing massive MCP Tool Arrays directly to the LLM (which consumes 3000+ tokens) or forcing the LLM to waste API rounds executing MCP tools to find data (Latency Death Spiral), SpecWeaver adopts a **Pre-Fetch Architecture**.

1. **The Target Bound**: The local `context.yaml` defines its exact data needs.
   ```yaml
   consumes_resources:
     - "mcp://database/schema/users"
     - "mcp://database/schema/billing"
   ```
2. **The Assembler Hook**: Before any prompt is sent to the LLM, SpecWeaver's `ContextAssembler` mechanically connects to the MCP Server, runs the queries for those specific resources, and serializes the exact schema strings.
3. **The Yield**: The exact data is injected into an `<environment_context>` XML block inside the System Prompt.
   **Result:** The LLM gets immediate, latency-free reality checks. Token bloat is mathematically limited to only the resources explicitly permitted by the architecture boundary.

---

## 2. Feature 3.32c-1: External DB Context Harness

**Goal:** Securely allow SpecWeaver to introspect target databases without allowing RCE (Remote Code Execution), supply-chain vulnerabilities, or orphaned connections.

### The "Ephemeral Docker MCP Pod" Pattern
We strictly ban `npx` or `uvx` wrapper execution. Native execution introduces supply-chain RCE vulnerabilities and "zombie" processes that cripple database connection pools.

1. **Pinned Docker Execution:**
   SpecWeaver mandates that MCP DB servers run inside ephemeral, strictly version-pinned Docker containers using `docker run -i --rm`.
   ```yaml
   mcp_servers:
     postgres:
       command: "docker"
       args: ["run", "-i", "--rm", "mcp/postgres@sha256:abcd...", "${VAULT:DB_URL}"]
   ```
   **Security Benefit:** When SpecWeaver shuts down the pipe, Docker instantaneously kills the container. Zero zombie processes. Zero lingering TCP socket connections to the database.

2. **The `vault.env` Credential Shield:**
   Database connection strings cannot be stored in `context.yaml` (which is tracked by Git). SpecWeaver introduces a local `.specweaver/vault.env` (which is strictly `.gitignore`d). The execution harness securely injects these secrets dynamically at runtime into the Docker container, eliminating credential leaks.

---

## 3. Known Limitations & Mitigations

### 1. The "Temporal Disconnect" & Topology Cycle Deadlock
**The Danger:** The MCP Server pulls the live schema *from the physical database*. If SpecWeaver is running an 8-minute pipeline to **build a brand new database table** (Tier 1), and then Tier 2 boots up and attempts to query the MCP server to read that new schema, the MCP Server will return an empty result (because the code hasn't been physically deployed to the DB yet).
**The Mitigation:** Proper Topology DAG routing (Feature 3.49 and Tiered Dependencies). The `ContextAssembler` must execute **lazily** per-tier, not at global `Wave 0`. Furthermore, agents must treat `Spec.md` as the ultimate source of truth for the *delta* (the future), while the MCP context represents the *baseline past*.

### 2. The Docker Friction Barrier
**The Danger:** Mandating `docker run -i --rm` completely solves supply chain security and zombie process problems, but forces a massive physical prerequisite onto the developer: **They must have Docker / Podman installed and running locally.**
**The Mitigation:** SpecWeaver already establishes strong dependencies on Podman/Docker across its broader ecosystem (e.g., Feature 3.45 Ephemeral Execution Containers). Integrating MCP explicitly standardizes container-runtimes as a core SpecWeaver prerequisite, consolidating infrastructure requirements rather than fracturing them.
