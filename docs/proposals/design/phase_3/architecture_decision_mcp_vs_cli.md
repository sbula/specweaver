# Architectural Decision Record: MCP Server vs. Master Orchestrator

**Status:** DECIDED (SpecWeaver remains Master Orchestrator)
**Date:** 2026-04-02
**Context:** Evaluating whether SpecWeaver should pivot to becoming a Model Context Protocol (MCP) server for Agentic IDEs (Claude Code, Cursor) or remain a CLI-based Master Orchestrator (Dictator) making direct LLM API calls.

## Decision
We reject the MCP Server model. SpecWeaver will remain the Master Orchestrator running its own LLM API calls. We prioritize absolute architectural control (Friction Gating) and Dynamic Rulesets over the "flat-fee" marketing illusions of external IDEs.

---

## 1. The Token Economics: Before vs. After

### How it works now (CLI Context Builder)
1.  **Human Command:** `sw implement feature-1`
2.  **SpecWeaver CPU Logic:** Scans SQLite, evaluates Constitution, parses `context.yaml`.
3.  **The Prompt:** Assembles a highly optimized, minimized 4,000-token prompt.
4.  **The LLM:** Receives 4,000 tokens immediately.

### How it operates in MCP (The "Initialization Pull")
If SpecWeaver were an MCP Server, the IDE agent hits the `mcp.get_prompt` endpoint. The LLM receives the exact same 4,000 token payload instantly as its system instructions. There is zero token waste conceptually.

## 2. The "Trust Boundary" Reality (Why We Reject Soft Guardrails)

We are officially rejecting prompt-based or watcher-based guardrails. 

If we made SpecWeaver an MCP Server for an external IDE (like Cursor or Claude Code), we hand over the "Execution Loop" to the IDE. As long as the IDE has OS-level write access to the folder, the LLM *will* eventually bypass the prompt, hallucinate, and use its built-in generic tools to write to forbidden files. Filesystem watchers just cause race conditions where SpecWeaver and the IDE fight over the state of a file.

If we want **dictatorial, mathematical control** over the agent while still allowing them to use modern IDE interfaces, we would have to use OS-level enforcement. There are three true "Hard Boundary" solutions:

### Solution A: The FUSE Virtual Filesystem (The Aerospace Path)
SpecWeaver mounts a Virtual Filesystem (FUSE). It dynamically sets the OS-level file permissions on the virtual mount (e.g. `chmod 400` for Billing module). If the IDE attempts to write, it hits a hard `EACCES (Permission denied)`. 
*Result: Too heavy for multi-developer UX.*

### Solution B: The "Git Worktree" Sandbox (The Pragmatic Walled Garden)
SpecWeaver creates a temporary `git worktree`. The Agentic IDE is told to open *that* worktree. When the session ends, SpecWeaver runs the merge. It mathematically compares the git diffs against the `context.yaml` and aggressively strips out hallucinated modifications to forbidden files from the patch before applying.
*Result: Viable, but introduces branch juggling overhead.*

### Solution C: Reject MCP server status and remain the Dictator (CHOSEN)
We keep SpecWeaver as the Master Orchestrator making direct API calls to the LLM. 
*   **The Reality of Cost:** While it seems like paying metered API tokens is the most expensive route, it is actually the most **optimized** route for high-complexity architectures. The idea of a "$20/month flat fee" for AI coding is a marketing illusion for power users. Claude Code charges per token via the Anthropic Console. Cursor Pro's $20 tier caps out at 500 fast requests, after which metered keys are required anyway. 
*   **Why SpecWeaver Wins Here:** Because heavy API token costs are unavoidable at 15-microservice scale, SpecWeaver saves money not by changing the billing model, but by **Friction Gating**. When an agent hallucinates a circular dependency, Claude Code will burn $2 blindly retrying the compiler 15 times. SpecWeaver's C01-C08 gating detects the violation instantly and stops the LLM from wasting tokens on doomed execution loops.

## 3. The "Dynamic Ruleset" Engine (Risk-Based Governance)

By remaining the Master Orchestrator, we unlock the ability to implement a **Design Assurance Level (DAL)** Matrix without skipping QA stages. 

The 10-test gate mechanism remains fixed, but the *Ruleset* injected into those gates changes based on the module's target domain:

*   **High-Risk Target (Trading / Risk Management Module):** SpecWeaver detects the module context via inheritance and dynamically loads the `finance-strict` ruleset. The validation criteria are brutal: It enforces deterministic math (blocking the use of standard `float`), demands thread-safety static analysis, and requires 95% AST test coverage. The LLM is forced to follow these rules.
*   **Low-Risk Target (Basic CRUD Service):** SpecWeaver detects the module is a simple web interface. It dynamically loads the `web-standard` ruleset. The validation criteria relax: standard database types are allowed, and 70% test coverage passes. 

This is the true power that MCP servers forfeit. SpecWeaver does not define a single, global fixed ruleset that punishes simple CRUD development just to keep Trading safe. SpecWeaver dynamically tightens or loosens the rules of physics based on the context boundary.

### Conclusion
Soft guardrails (prompts) fail. By rejecting the MCP Server model, SpecWeaver retains the absolute, dictatorial control necessary to orchestrate complex polyglot environments securely and cost-effectively.
