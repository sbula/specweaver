# Spec Rot Pre-Commit Workflow

Use when: you install the Spec Rot hook in a project, or a commit was blocked by it.

The **Bi-Directional Spec Rot Interceptor** (Feature 3.23) is a Git pre-commit hook. It targets the
"2nd-Day Problem": a developer hot-fixes code in the IDE and forgets to update the markdown spec
(e.g. `Spec.md`). On every `git commit` it compares the AST signatures of staged code files with the
structural contracts in the Spec. On mismatch the commit is blocked.

## Install

```bash
# From the root of your project
sw hooks install --pre-commit
```

- Installs into your local `.git` repository. The hook runs `sw drift check-rot --staged`. Drift raises a fatal **Exit Code 42**.
- The installer records your active Python/UV executable (`sys.executable`), so the hook uses the
  right environment from the git CLI and from IDE source control.

## A blocked commit

`git commit -m "update"` with structural drift prints:

```
>>> SpecWeaver: Running Bi-Directional Spec Rot Interceptor (Feature 3.23) <<<

[red]Failure: AST Drift Detected![/red] (my_service.py)
...

================================================================
ERROR: SpecWeaver detected structural drift between Spec and Code!
Fix the mismatch to proceed with this commit.
================================================================
```

Two ways out:

| Situation | Fix |
|---|---|
| **The Code is Wrong (Hallucination/Bug):** an LLM or developer made an unauthorized signature change that violates the design | Revert or update the code to match the Spec |
| **The Code is Right (Intentional Hot-Fix/Evolution):** the structure changed on purpose, the doc did not | Update the `## Contract` or `## Scenarios` section of `Spec.md` to the new signature, `git add Spec.md`, commit again |

## Traps

- **"The SpecWeaver pipeline crashed"**: `ERROR: The SpecWeaver pipeline crashed` is an environment
  error, not drift. Check SpecWeaver is still installed in your virtual environment. After moving the
  project directory, run `sw hooks install --pre-commit` again.
- **Bypassing**: `git commit --no-verify` works for emergency operational rollbacks, but it violates
  the Constitution and the CI pipeline flags it anyway.
