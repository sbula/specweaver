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

## CB-2: the pins and the reader (FR-2, FR-1's seam) — closes SF-01

**What changed**
- `core/config/implement_policy.py`: `[implement] build_tool` (`uv`, `maven`, `gradle`, `cargo`,
  `npm`); a wrong value is refused naming its key and line, as `language` is.
- `decide_profile` takes the two pins. A set pin wins over the root. Pins that disagree are refused,
  naming both `[agreed 2026-11-05]`. Not in the plan, taken at dev: a `build_tool` pin that cannot
  build the language the root decides (`build_tool = "maven"` on a Python root) is refused too,
  the same rule as two pins; raised to the user at the CB-2 stop.
- New `workspace/project/project_profile.py` `read_project_profile(root, *, language, build_tool)`:
  lists the root once, regular files only; a file whose real path leaves the root reads as None;
  an unreadable or non-UTF-8 file reads as None; a missing root raises the OS error.
- Found at the gate, removed: a "read only listed names" check the decision can never reach.

**Tests**
- `test_implement_policy.py`: each build tool; `ant` refused naming `implement.build_tool` line 3;
  the `Language` and `BuildTool` values equal `GENERATED_LANGUAGES` and `BUILD_TOOLS`. Red first.
- `test_project_profile.py`: a language pin wins over a mixed root, a build-tool pin over pom.xml
  with Gradle, contradicting pins, a build-tool pin that does not build the root language, a
  language pin SpecWeaver cannot generate. Red first (no pin arguments).
- `tests/integration/workspace/project/test_read_project_profile.py` (12): red first (no module).
- Mutants added, each OBJECTED: `language-pin-ignored`, `contradicting-pins-trusted`,
  `build-tool-pin-mismatch-trusted`, `subfolder-counts`, `link-outside-root-read`,
  `kotlin-sources-ignored`, `root-not-resolved`.

**Red/blue**
- Safe: symlink loops, FIFOs and unreadable entries are not regular files, so they are not listed.
- Accepted: a very large build file in the user's own root is read whole; only that user is hurt,
  and a size limit would be a number nobody agreed.
- Accepted: `build_tool` is accepted in `specweaver.toml` but acts only from SF-02; the user guide
  §6c is written then (F8).
