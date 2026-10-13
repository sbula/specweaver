# E-SENS-01 — Loom FS Tools

**Status**: ✅ Finished — signed off by the user 2026-10-12. · **Phase**: 1 (Step 1b)

| | |
|---|---|
| Touches | `sandbox/filesystem/` (executor, tool, role interfaces) · `sandbox/dispatcher.py` |
| Plan | [as built](E-SENS-01_implementation_plan.md) |

## What it does

Gives a model file tools that cannot reach a file outside the project or outside its grants. A
model is offered four read tools: `read_file`, `list_directory`, `grep`, `find_files`. Each path
passes two checks, so one bug alone does not open a way out: the grant check, then the root check
after the path is resolved.

The write tools (`write_file`, `edit_file`, `create_file`, `delete_file`) and the protected files
they refuse (`context.yaml`, `.env`, `.git`, `.specweaver`) are built but offered to no model.
`B-FLOW-01` offers them to the scenario agent `[agreed 2026-10-12]`.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Inside the project and the grants | File tool | SHALL refuse a path that no grant covers, or that resolves outside the project root (`../`, an absolute path) | a model reads only what it was granted |
| FR-2 | No symlinks | File executor | SHALL refuse a path that passes a symlink, and skip symlinks in a search | a link cannot lead out of the project or around a grant |
| FR-3 | Read tools only | Dispatcher | SHALL offer a model the four read tools and no write tool, whatever its role | no model changes a file through a file tool |
| FR-4 | No streams | File executor | SHALL refuse a path with `:` in a segment, on every OS | a model cannot read a Windows alternate data stream |
| FR-5 | Tools do what they say | File tool, role interfaces | SHALL accept every parameter a tool's definition offers: `path` optional (`.`) for `grep`, `find_files`, `list_directory`; `read_file` lines `start_line` to `end_line`; `list_directory` `depth` levels and at most `max_entries`, never entering a symlink, an excluded folder or an ungranted one `[agreed 2026-10-13]` | a model that follows the definition gets a result, not an error |

## Live demo

In a project with `src/own.py`, a folder `outside/secret.txt` next to it, and the links
`src/link.txt → outside/secret.txt` and `linkroot → outside/`: build the tools as `sw review` does
(`ToolDispatcher.create_standard_set`) for the reviewer and the implementer. `src/own.py` reads;
`../outside/secret.txt`, the absolute path, both links, `grep` and `find_files` on `linkroot` and
`..` all return an error, and the secret is in no result. A scenario agent cannot read `src/` through
a link in `scenarios/`. `tests/integration/sandbox/test_agent_file_tools_stay_inside.py` does
exactly this.
