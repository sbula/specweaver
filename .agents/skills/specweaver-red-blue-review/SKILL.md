---
name: specweaver-red-blue-review
description: "Adversarial Red Team / Blue Team architecture review. Multi-cycle review where Red Team attacks and Blue Team defends design/implementation decisions. Runs until no significant findings remain. Use when the user asks for red team, blue team, adversarial review, design review, or architecture review."
---

# Red/Blue Team Review Skill

```
Trigger: "red team", "blue team", "red/blue", "adversarial review",
         "architecture review", "design review", "red blue review",
         "red team blue team", "adversarial analysis"
```

## Purpose

This skill performs multi-cycle adversarial reviews of design documents,
implementation plans, or code. It discovers architectural flaws, security
risks, maintainability issues, and design contradictions through structured
adversarial analysis.

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute all cycles autonomously. Present the final consolidated report
> to the user only after no more significant findings are discovered.
> If in doubt about a finding's severity or validity: research the internet,
> then decide. If still unsure: flag it and ask the user.

---

## Protocol

### Cycle Structure

Each cycle has exactly two phases:

**🔴 Red Team (Attacker)**

> [!CAUTION]
> **EXHAUSTIVE SEARCH MANDATE:** The Red Team's job is to find AS MANY mistakes,
> errors, misunderstandings, contradictions, violations, risks, ambiguities,
> and weaknesses as possible. Leave no stone unturned. Check every single focus
> area listed below. Do NOT stop after finding 2-3 issues — dig until you have
> found EVERYTHING. If a cycle produces zero findings, you MUST explicitly confirm
> you checked every single focus area and found nothing.

- Challenge every design decision, architectural choice, and implementation detail
- Look for weaknesses, contradictions, violations, risks, misunderstandings, and ambiguities
- Produce specific, actionable findings (not vague concerns)
- Rate every finding by severity (see Severity Definitions below)
- There is NO LIMIT on findings per cycle — report ALL of them

**🔵 Blue Team (Defender)**
- Respond to EVERY Red Team finding — none may be silently ignored
- If the finding is valid: propose a specific fix with concrete details
- If the finding is invalid: explain why with evidence and references
- If the finding is partially valid: acknowledge the valid part, refute the rest

### Severity Definitions

| Severity | Definition | Examples |
|----------|-----------|----------|
| **CRITICAL** | Will cause data loss, security breach, architectural corruption, or system failure if not fixed | Circular dependency, `forbids` violation, credential leak, unbounded resource usage |
| **HIGH** | Significant risk of bugs, maintenance burden, or degraded performance. Likely to cause problems in production | Missing error handling on critical path, DRY violation across 3+ modules, wrong archetype placement |
| **MEDIUM** | Suboptimal design that works but accumulates tech debt. May cause confusion or minor bugs | Naming inconsistency, missing edge case test, unclear interface contract |
| **LOW** | Cosmetic, stylistic, or minor improvement. No functional risk | Comment quality, variable naming, documentation phrasing |

### Iteration Rules

1. **Cycle 1**: Red Team attacks the original document/code. Blue Team responds to each finding.
2. **Cycle 2**: Red Team takes Blue Team's Cycle 1 *responses* and **challenges them**.
   Are the defenses solid? Are the proposed fixes correct? Did Blue Team miss anything?
   Red Team also looks for NEW issues not found in Cycle 1.
3. **Cycle N**: Red Team takes Blue Team's Cycle N-1 *responses* and challenges them.
   Continue looking for new issues as well.

### Continuation Thresholds

After each cycle, count the findings by severity. **Continue to the next cycle if ANY
of these thresholds are met:**

| Severity | Threshold to Continue |
|----------|-----------------------|
| CRITICAL | ≥ 1 finding |
| HIGH | ≥ 2 findings |
| MEDIUM | ≥ 5 findings |
| LOW | ≥ 10 findings |

> The logic: the lower the risk, the more findings are needed to justify another cycle.
> A single CRITICAL issue demands another cycle. It takes 10 LOW issues to justify one.

**Minimum cycles**: 2 (even if Cycle 1 produces zero findings — verify explicitly).

**Stop condition**: A cycle's findings fall BELOW all thresholds in the table above.
The review is complete. Produce the consolidated report.

### HITL Escalation (Safety Valve)

> [!WARNING]
> **ESCALATION TRIGGERS — STOP and inform the user if ANY of these occur:**
> - **Cycle count > 10**: Something is fundamentally wrong with the design. The review
>   is not converging. Present all findings to the user and ask how to proceed.
> - **Total findings > 50**: The volume of issues suggests the document needs a major
>   rewrite rather than incremental fixes. Present findings and ask for guidance.
> - **Oscillation detected**: Blue Team's fix for Finding A introduces Finding B,
>   and fixing B re-introduces A. Flag the oscillation and escalate to HITL.
>
> On escalation: present ALL findings so far, explain why you're escalating,
> and **STOP. YIELD YOUR TURN. Wait for the user.**

---

## Focus Areas

The Red Team MUST systematically check each of these categories in every cycle:

### Architecture & Design
- **DDD Compliance**: Are bounded contexts respected? Is the ubiquitous language consistent?
- **Hexagonal Architecture**: Are ports and adapters properly separated? Is I/O at the edges?
- **Separation of Concerns**: Does each module have exactly one reason to change?
- **KISS**: Is the solution the simplest that satisfies the requirements? Any over-engineering?
- **DRY**: Is there redundant logic that should be extracted?
- **YAGNI**: Is there speculative code that isn't driven by a test or FR?

### Boundaries & Dependencies
- **DAL-Level Violations**: Does pure-logic code perform I/O? Do adapters leak domain logic?
- **Import/Access Violations**: Do modules respect `consumes`/`forbids` rules in `context.yaml`?
- **Circular Dependencies**: Are there import cycles (direct or transitive)?
- **Stability Direction**: Do volatile modules depend on stable ones (correct) or vice versa (wrong)?

### Security & Safety
- **Data Exposure**: Can sensitive data (API keys, credentials) leak through logs, errors, or `/proc`?
- **Input Validation**: Are all inputs sanitized? Path traversal? Injection?
- **Resource Limits**: Can an adversary cause unbounded memory/CPU/disk usage?
- **Privilege Escalation**: Can a component gain access to resources it shouldn't have?

### Robustness & Edge Cases
- **Error Handling**: Are all failure modes handled? What happens on timeout, OOM, disk full?
- **Race Conditions**: Are there TOCTOU bugs or concurrent access issues?
- **Zombie Processes**: Can child processes outlive their parent?
- **Platform Differences**: Does it work on both Windows and Linux?

### Maintainability
- **Testability**: Can every component be tested in isolation?
- **Readability**: Is the code self-documenting? Are complex algorithms explained?
- **Extension Points**: Can new features be added without modifying existing code?

---

## Finding Format

Each finding MUST use this structure:

```markdown
### 🔴 RED-<cycle>.<number>: <title>

**Category**: <category from focus areas above>
**Severity**: CRITICAL | HIGH | MEDIUM | LOW
**Target**: <file, class, function, or design section>
**Finding**: <specific description of the weakness or issue>
**Evidence**: <concrete evidence — line numbers, code snippets, or document references>
**Attack Vector**: <how this could cause a real problem — scenario description>

---

### 🔵 BLUE-<cycle>.<number>: Response to RED-<cycle>.<number>

**Verdict**: VALID — FIX REQUIRED | VALID — ACCEPTED RISK | INVALID — NO ACTION
**Response**: <defense or proposed fix>
**Fix**: <concrete code/design change if applicable>
```

---

## Output

After all cycles complete, produce a consolidated report:

```markdown
# Red/Blue Team Review Report

## Summary
- **Target**: <what was reviewed>
- **Cycles**: <number of cycles run>
- **Findings**: <total findings across all cycles>
- **Critical/High fixes applied**: <count>

## Corrections Made
<List every change made to the document/code as a result of this review>

## Accepted Risks
<List findings that were valid but accepted as risks, with justification>

## Cycle Log
<Full log of all cycles, findings, and responses>
```

---

## Integration Points

This skill is invoked by:
- **Design skill Phase 6**: Red/Blue review of the design document before approval
- **Implementation-plan skill Phase 5**: Red/Blue review of the implementation plan before approval
- **Standalone**: When the user explicitly asks for an adversarial review of any document or code

When invoked by another skill, keep the review focused and proportionate.
Do not over-engineer the review for a simple feature. Use judgment on depth.
