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

**Grants by role** (`ToolDispatcher._compute_role_grants`, `E-SENS-03`): reviewer, planner and
arbiter read the project; the scenario agent reads `specs/` and `contracts/`; the `implementer`
reads the project and gets a `TaskGrant` — FULL on the files its task may write, the
`task_files` given to `create_standard_set`, matched by the worktree merge's own rule
(`write_verdict`: globs; the root `doc_updates.md` always; `README.md` and `docs/` only as the
project's `[docs]` rules allow, for the step named by `step=`; protected files never). A role with
no rule gets no grant at all.

## CodeStructureTool

Reads and changes code by symbol, never by raw text: `read_file_structure`, `read_symbol`,
`read_symbol_body`, `list_symbols` for every role that reads; `replace_symbol`,
`replace_symbol_body`, `add_symbol`, `delete_symbol`, `rename_symbol`, `move_module`,
`create_module`, `delete_module`, `read_symbol_doc` and `replace_symbol_doc` for the implementer.
`CodeStructureAtom` (`sandbox/code_structure/core/atom.py`) offers the same intents to the flow
engine without grants.

`rename_symbol(path, symbol_name, new_name)` (Python, Java, Kotlin, TypeScript, Rust, Go, C, C++; Java with Kotlin and C with C++ are searched together) renames a function, class or method and
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
glob `use` and any name inside a macro. A Rust trait method renames in the trait and every impl. In Go, a dot import is unsure,
and a method that any project interface declares, or that has a standard interface's name
(`String`, `Error`, `Read`, ...), refuses. In C and C++, a use is proven only where a
declaration is in reach through quoted includes; a macro body and `using namespace` are unsure. A method is renamed in its whole
override family: every class above and below it that defines it. A family with a base outside the
project refuses. The tool also
refuses when a changed file is outside the role's write grants, and counts (does not name) spots
and mentions in files the role may not read.

`move_module(path, new_path)` (all 8 code languages) moves a file and rewrites every import of it,
all files or none. It refuses a target that exists, is protected, or lies under another
`context.yaml`; an import it cannot rewrite for certain (a module path as a string, a `tsconfig`
alias) refuses with its line. A Go or Rust file moves only within its folder; a Java or Kotlin
file renamed in its folder renames its public class, and a move to another package refuses while
the old package uses it without an import. C and C++ includes are rewritten when they resolve beside
their includer, and unsure when only an include path finds them. The agent needs `FULL` on
both paths: a move creates one file and deletes another.

`create_module(path, code)` writes a new file. It refuses a path that exists, is outside the
project or protected, or has no parser, and code that does not parse. `delete_module(path)` deletes
a file only when nothing uses it: no import of it, and no proven or unsure use of its top-level
symbols in another file. The refusal names the files that use it; a Rust module is always used by
its parent's `mod` line. Each needs `FULL` on `path`.

`read_symbol_doc(path, symbol_name)` returns the doc above a symbol (Python: its docstring) as
plain text. `replace_symbol_doc(path, symbol_name, doc)` takes plain text and adds the markers and
the indentation: `/** */` in Java, Kotlin, TypeScript, C and C++, `///` in Rust, `//` in Go. An
existing doc keeps its own style, an empty `doc` removes it, and only the doc's lines change. A doc
that shares a line with other code, or text that would end its own comment, refuses. SQL and
Markdown have no doc intents. A doc goes above a Rust attribute, a decorator and a C++
`template` line.

`FileExecutor` reads and writes the text exactly as it is on disk, so every change keeps each
file's line endings: a read returns `\r\n` where the file has it.

## ProtocolTool

`extract_schema_endpoints` and `extract_schema_messages` read an OpenAPI, AsyncAPI or `.proto`
contract. The tool is built with the run's `WorkspaceBoundary` (the registry passes
`kwargs["boundary"]`), and `ProtocolAtom` needs one too: no boundary, no atom. A relative path is
read from the project root; a contract under a read-only API path is allowed; `..`, an outside
absolute path or a link that points outside is refused before the file is opened, and the error
names only the path as given (`TECH-075` FR-4).

## QARunnerTool and QARunnerAtom

Tests, lint, complexity, compile, debug and architecture checks, by intent. Before any intent runs,
`QARunnerAtom.run` checks every `target`, each `targets` entry and the debugger's `entrypoint`
against `WorkspaceBoundary([cwd])`. A path outside (`..`, an outside absolute path, a link that
points outside, a null byte, a value that is not a string) is a `FAILED` result and no tool starts.
A Java or Kotlin main-class name passes as a name inside the root. `/scenarios/…` passes only when
the atom was built with `scenarios_root`. An empty value is left to the intent, which names what is
missing (`TECH-075` FR-5).

A `run_tests` target runs exactly what it names, in every language. `<file>::<name>` is one test,
a file is its tests, a folder is its tests and its subfolders', and `.` or empty is the project.
`run_targets.parse_target` reads the target; each runner turns it into its tool's filter: pytest
takes it as it is, Gradle `--tests`, Maven `-Dtest`, cargo `--test`/`--lib` with `--exact`. A Rust
test in a `src/` file is named as `<module>::tests::<name>`. A named test ignores the `kind`
marker. A run that ran no test fails and names the target (`TECH-078` FR-7).

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
