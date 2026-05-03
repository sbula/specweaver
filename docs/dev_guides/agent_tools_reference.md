# Agent Tools & Atoms Reference

SpecWeaver provides role-restricted tools for LLM agents, inspired by the `flowManager` atoms & tools architecture. This ensures that agents only have access to exactly what they need, eliminating the risk of rogue AI executions.

## FileSystemTool

Grant-based file access for agents. Each agent receives a set of `FolderGrant` objects that define which directories it can read, write, or execute — with path traversal prevention built in.

```python
from specweaver.loom.tools.filesystem.tool import FileSystemTool, FolderGrant, AccessMode

grants = [FolderGrant("src/billing", AccessMode.WRITE, recursive=True)]
tool = FileSystemTool(executor=executor, role="implementer", grants=grants)

tool.read_file("src/billing/calc.py")           # ✅ within grant
tool.create_file("src/billing/utils.py", code)  # ✅ write access
tool.read_file("src/auth/secrets.py")           # ❌ outside grant
tool.read_file("src/billing/../../etc/passwd")  # ❌ path traversal blocked
```

| Intent | Description |
|---|---|
| `read_file` | Read file contents (with line range support) |
| `create_file` | Create a new file |
| `edit_file` | Replace a specific section of a file |
| `delete_file` | Remove a file |
| `list_directory` | List directory contents |
| `search_content` | Regex search across files |
| `find_placement` | Suggest where to place new code (uses `context.yaml`) |

**Security:** All paths are normalized via `posixpath.normpath`, absolute paths are rejected, and `..` traversal beyond grant boundaries returns an error.

## GitTool

High-level git operations that agents call by intent, not raw commands. Each intent maps to a safe sequence of git commands executed on the target project directory (never SpecWeaver's own repo).

```python
from specweaver.loom.tools.git.interfaces import create_git_interface

# Agent gets only the methods its role allows
git = create_git_interface("implementer", project_path)
git.commit("feat: add login endpoint")    # ✅ stages, validates, commits
git.history()                              # ❌ AttributeError — not on this interface
```

| Role | Allowed Intents |
|---|---|
| **Implementer** | commit, inspect_changes, discard, uncommit, start_branch, switch_branch |
| **Reviewer** | history, show_commit, blame, compare, list_branches |
| **Debugger** | history, file_history, show_old, search_history, reflog, inspect_changes |
| **Drafter** | commit, inspect_changes, discard |
| **Conflict Resolver** | list_conflicts, show_conflict, mark_resolved, abort_merge, complete_merge |

## GitAtom

Flow-level git operations for the Engine. Unlike GitTool (agent-facing, role-restricted), GitAtom handles orchestrator-driven tasks using `EngineGitExecutor` (no blocked commands).

```python
from specweaver.loom.atoms.git import GitAtom

atom = GitAtom(cwd=project_path)
result = atom.run({"intent": "checkpoint", "message": "flow step complete"})
result = atom.run({"intent": "integrate", "source": "feat/login", "target": "main"})
```

| Intent | Purpose | Git commands |
|---|---|---|
| **checkpoint** | Semantic commit after flow step | add, diff, commit |
| **isolate** | Create isolation branch for flow | switch -c |
| **restore** | Return to original branch | switch |
| **discard_all** | Clean working tree | restore . |
| **rollback** | Undo last checkpoint | reset --soft HEAD~1 |
| **publish** | Push flow results to remote | push |
| **integrate** | Merge branch into target | checkout, merge |
| **sync** | Pull latest from remote | fetch, pull |
| **tag** | Mark release/milestone | tag |
| **worktree_add** | Create isolated parallel worktree branch | worktree add |
| **worktree_teardown** | Force removal with Windows retry resilience | worktree remove, prune |

**Built-in guardrails:**
- Conventional commit messages enforced (`feat:`, `fix:`, `docs:`, ...)
- Branch naming enforced (`feat/`, `fix/`, `docs/`, ...)
- `push`, `pull`, `merge`, `rebase`, `tag` are permanently blocked
- Auto-stash on branch switch
