# Walkthrough: TECH-079 SF-01 — One profile decision

## CB-1: the pure decision (FR-1, FR-3, FR-4, FR-5, FR-6)

**What changed**
- New `commons/project_profile.py`: `decide_profile(root_files, read, *, kotlin_sources)` returns a
  `ProjectProfile(language, build_tool)` or raises `ProjectUndecidedError`. It reads nothing itself;
  it asks `read` only for the JVM build files, to tell Kotlin from Java. `GENERATED_LANGUAGES` and
  `BUILD_TOOLS` are the one list of each. No caller uses it yet (SF-02).
- The plan named the exception `ProjectUndecided`; ruff's N818 wants the `Error` suffix, so it is
  `ProjectUndecidedError`, in the plan too.
- A mixed-root message names a JVM build as `java or kotlin`, the two values the user can set.
  A list longer than three names ends with `...`.

**Tests**
- `tests/unit/commons/test_project_profile.py`, red first (no module): each build file, the root
  code endings, TypeScript vs JavaScript, Kotlin vs Java, an unreadable build file, mixed roots,
  languages that cannot be generated, pom.xml with Gradle, an empty root, case-exact names.
- `tests/unit/commons/test_foundation_reads_no_files.py` (NFR-2): no `commons` module calls a file
  function; it proves it finds the modules and catches a planted call.
- `tests/integration/commons/test_profile_agrees.py` (found at dev: the `cb` gate needs an
  integration test beside `commons`): every ending of the one table is decided by it; a
  one-language root in `tmp_path` gets today's `detect_language`/`detect_toolchain` answer, npm
  aside (F10). Written after the code, so probed: three mutants, each objected.
- Mutants in `TECH-079_mutants.json`, each OBJECTED: `mixed-root-picks-first`,
  `no-manifest-is-python`, `go-is-generated`, `pom-and-gradle-picks-gradle`,
  `package-json-is-typescript`.

**Red/blue**
- Fixed: `fnmatch` follows the platform's case rule, so `REQUIREMENTS.TXT` was Python on Windows
  only; now `fnmatchcase`. Linux cannot show the red; the test pins the rule.
- Fixed: the root's code endings were collected once per root file (quadratic on a large root);
  now once per decision.
- Accepted: a file name holding a newline breaks the one-line refusal. The name comes from the
  user's own root and is shown to that user only.
- Accepted: `read` must return None rather than raise; the reader in CB-2 owns that (F7, F9).
