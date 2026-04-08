# Spec Rot Pre-Commit Workflow

## Overview

SpecWeaver implements a **Bi-Directional Spec Rot Interceptor** (Feature 3.23) using standard Git Hooks. 

The goal of this interceptor is to solve the "2nd-Day Problem" where developers hot-fix code in their IDE but forget to update the associated markdown specification (e.g., `Spec.md`) to reflect the new realities of the implementation.

SpecWeaver intercepts every `git commit` to mathematically compare the AST signatures of the staged code files against the structural contracts defined in the Spec. If the structures don't match, the commit is blocked!

## Installation

You must install the SpecWeaver pre-commit hook in your local `.git` repository for this to work natively.

```bash
# From the root of your project
sw hooks install --pre-commit
```

*Note: This command will attempt to determine the path of your active Python/UV executable (`sys.executable`) to ensure that native bash execution triggers the correct environment when you use traditional git CLI clients or IDE integrated source controls.*

## Workflow during a blocked commit

When you execute `git commit -m "update"` and structural drift is detected, you will see output like this:

```
>>> SpecWeaver: Running Bi-Directional Spec Rot Interceptor (Feature 3.23) <<<

[red]Failure: AST Drift Detected![/red] (my_service.py)
...

================================================================
ERROR: SpecWeaver detected structural drift between Spec and Code!
Fix the mismatch to proceed with this commit.
================================================================
```

### Resolution Paths

When blocked, you have two options:

1. **The Code is Wrong (Hallucination/Bug):**
   - The LLM or human developer made an unauthorized structural change to the signature that violates the design.
   - **Fix:** Revert or update your code changes to match the Spec. 

2. **The Code is Right (Intentional Hot-Fix/Evolution):**
   - You intentionally changed the required structure, but you forgot to update the documentation.
   - **Fix:** Open the `Spec.md` file and update the `## Contract` or `## Scenarios` section to match the new code signature. Then `git add Spec.md` to your staging area and attempt the commit again!

---

## Troubleshooting

### "The SpecWeaver pipeline crashed"
If the hook script emits `ERROR: The SpecWeaver pipeline crashed`, it indicates an environment error rather than spec drift. Check that your Python virtual environment still has SpecWeaver installed. You may need to run `sw hooks install --pre-commit` again if you moved the project directory.

### Bypassing the Hook
SpecWeaver strongly discourages bypassing the interceptor (it violates the Constitution). However, for emergency operational rollbacks, you can use standard Git bypass mechanisms: `git commit --no-verify`.  This action will be flagged by the CI pipeline anyway!
