# Agent Tools and Atoms Reference

Use when: you need what a filesystem or git tool lets an agent (or the engine) do.

Agents get role-restricted tools (after the `flowManager` atoms & tools architecture): each role has
exactly what it needs and nothing an agent could misuse. Import paths today (2026-09-25):
`FileSystemTool` in `specweaver.sandbox.filesystem.interfaces.tool`, `FolderGrant` / `AccessMode`
in `specweaver.sandbox.security`, `create_git_interface` in
`specweaver.sandbox.git.interfaces.facades`, `GitAtom` in `specweaver.sandbox.git.core.atom`.

## FileSystemTool

Grant-based read access. Each agent gets `FolderGrant` objects naming the directories it may read.
There are four tools and no write tool: agents change code through the code-structure tools, and
the engine writes whole files.

```python
from specweaver.sandbox.filesystem.interfaces.tool import FileSystemTool
from specweaver.sandbox.security import AccessMode, FolderGrant

grants = [FolderGrant("src/billing", AccessMode.WRITE, recursive=True)]
tool = FileSystemTool(executor=executor, role="implementer", grants=grants)

tool.read_file("src/billing/calc.py")           # ✅ within grant
tool.read_file("src/auth/secrets.py")           # ❌ outside grant
tool.read_file("src/billing/../../etc/passwd")  # ❌ path traversal blocked
```

| Intent | Description |
|---|---|
| `read_file` | Read a file (up to 100 KB), or lines `start_line` to `end_line` of a file of any size |
| `list_directory` | Paths from the project root, `depth` levels deep (default 2), at most `max_entries` (50); folders end in `/`; links, excluded and ungranted folders are never entered |
| `grep` | Regex search across files |
| `find_files` | Find files by glob |

**Security:** paths are normalized via `posixpath.normpath`; absolute paths are rejected; `..`
traversal beyond the project root returns an error, for `grep` and `find_files` too. A path through
a symlink, or with `:` in a segment, is refused.
Grant matching is `sandbox.security.grant_mode_for`, shared with the AST tool.

## CodeStructureTool

Reads and changes code by symbol, never by raw text: `read_file_structure`, `read_symbol`,
`read_symbol_body`, `list_symbols` for every role that reads; `replace_symbol`,
`replace_symbol_body`, `add_symbol`, `delete_symbol` and `rename_symbol` for the implementer.
`CodeStructureAtom` (`sandbox/code_structure/core/atom.py`) offers the same intents to the flow
engine without grants.

`rename_symbol(path, symbol_name, new_name)` (Python, Java, Kotlin, TypeScript, Rust; Java and Kotlin are searched together) renames a function, class or method and
every **proven** use in the project, in one change: all files or none. The plan is pure logic in
`workspace/ast/refactor/`; reading and writing are in `sandbox/code_structure/core/changes.py`.

| A use is | When |
|---|---|
| proven | the definition; an import that resolves to it, also through a re-export; a bare name that resolves to it; `self.m()` in its class or a subclass; `Class.m()`; `module.f()` |
| unrelated | a name its own file binds to something else: a local, a parameter, another import |
| unsure | anything else in code: `obj.m()` with an unknown `obj`, the name as a string, `global`, a free name |
| a mention | a comment, a docstring word, a doc or config file: reported, not changed |

One unsure use refuses the whole rename and lists the lines. A file that does not parse and holds
the name counts as unsure: its uses cannot be seen. In TypeScript, so do `export *`, a
`tsconfig.json` path alias, an object-literal key, and a `.js` file holding the name; in Rust, a
glob `use` and any name inside a macro. A Rust trait method renames in the trait and every impl. A method is renamed in its whole
override family: every class above and below it that defines it. A family with a base outside the
project refuses. The tool also
refuses when a changed file is outside the role's write grants, and counts (does not name) spots
and mentions in files the role may not read.

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

The atom also has `strip_merge`, `worktree_commit` and `is_tracked`
(`sandbox/git/core/atom.py`).
