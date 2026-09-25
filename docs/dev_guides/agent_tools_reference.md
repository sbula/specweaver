# Agent Tools and Atoms Reference

Use when: you need what a filesystem or git tool lets an agent (or the engine) do.

Agents get role-restricted tools (after the `flowManager` atoms & tools architecture): each role has
exactly what it needs and nothing an agent could misuse. Import paths today (2026-09-25):
`FileSystemTool` in `specweaver.sandbox.filesystem.interfaces.tool`, `FolderGrant` / `AccessMode`
in `specweaver.sandbox.security`, `create_git_interface` in
`specweaver.sandbox.git.interfaces.facades`, `GitAtom` in `specweaver.sandbox.git.core.atom`.

## FileSystemTool

Grant-based file access. Each agent gets `FolderGrant` objects naming the directories it may read,
write, or execute.

```python
from specweaver.sandbox.filesystem.tool import FileSystemTool, FolderGrant, AccessMode

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

**Security:** paths are normalized via `posixpath.normpath`; absolute paths are rejected; `..`
traversal beyond grant boundaries returns an error.

## GitTool (agents)

Agents call git by intent, not raw commands. Each intent maps to a safe sequence of git commands on
the target project directory (never SpecWeaver's own repo).

```python
from specweaver.sandbox.git.interfaces import create_git_interface

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

Guardrails:

- Conventional commit messages enforced (`feat:`, `fix:`, `docs:`, ...).
- Branch naming enforced (`feat/`, `fix/`, `docs/`, ...).
- `push`, `pull`, `fetch`, `merge`, `rebase`, `tag` are permanently blocked (`GitExecutor`).
- Auto-stash on branch switch.

## GitAtom (engine)

Orchestrator-driven git for the Engine. Uses `EngineGitExecutor`: no blocked commands, but each
intent still runs only its whitelisted commands.

```python
from specweaver.sandbox.git import GitAtom

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

The atom also has `worktree_sync`, `strip_merge`, `worktree_commit` and `is_tracked`
(`sandbox/git/core/atom.py`).
