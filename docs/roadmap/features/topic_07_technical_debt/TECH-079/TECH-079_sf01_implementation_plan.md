# Implementation Plan: Language and Toolchain Are Decided in a Dozen Places That Disagree [SF-01: One profile decision]
- **Feature ID**: TECH-079
- **Sub-Feature**: SF-01 — One profile decision
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf01_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-06)

## Scope

One pure function in `commons` decides a project's language and build tool from the root's file
names, a reader and the two pins; one reader in `workspace/project` feeds it; `[implement]` gains
`build_tool`. FRs: **FR-1..FR-6**. NFRs: NFR-2 (commons stays I/O-free), NFR-4 (one listing). No
caller uses the profile yet; SF-02 rewires them, so no user-visible behaviour changes in SF-01.
SF-03 adds the framework field. Paths: P-1 and P-2 begin here; their journeys are proven in SF-02.

Today (measured 2026-11-05):

- `sandbox/language/core/detect.py:33` `detect_language(cwd: Path) -> str`: package.json →
  typescript, Cargo.toml → rust, a JVM build → kotlin when `src/main/kotlin` is a folder or a build
  file mentions `kotlin` (`_is_kotlin`, `:63`), else java; no manifest → python.
- `workspace/project/prepare_plan.py:132` `detect_toolchain(source_root: Path) -> str` over
  `_TOOLCHAIN_MANIFESTS` (`:114`): `uv` (pyproject.toml, uv.lock), `cargo`, `maven`, `gradle`; `""`
  when none. No `npm` entry: TypeScript has no prepare today.
- `core/config/implement_policy.py:17` `Language = Literal["python","java","kotlin","typescript","rust"]`;
  `ImplementPolicy(extra="forbid", frozen=True)` with `language: Language | None = None`;
  `parse_implement(text, source)` = `parse_section(text, source, "implement", ImplementPolicy)`.
  A wrong value raises `SettingsFileError` naming key and line (`test_implement_policy.py`).
- `commons/languages.py:14` `LANGUAGE_SUFFIXES` (9 languages), `language_of(path)` (suffix lowered).
- tach: `workspace.project` depends on `assurance.graph`, `workspace.analyzers`,
  `workspace.ast.parsers` only (its `context.yaml` also consumes `core/config`); `commons` is
  `utility = true`, `depends_on = []`.

## Findings (Phase 4)

| # | Sev | Question | Options | Proposal |
|---|---|---|---|---|
| Q1 | HIGH | The two pins contradict (`language = "python"`, `build_tool = "maven"`) | A: refuse, naming both pins; B: trust both | **Refuse, naming both pins `[agreed 2026-11-05]`** |
| F1 | HIGH | The refusal type | its own exception `ProjectUndecidedError(Exception)`, not a `ValueError` | `interfaces/api/v1/implement.py:91` maps `ValueError` to `SPEC_INVALID`; a subclass would get the wrong code |
| F2 | MEDIUM | Does `build_tool` pick the language? | no: it decides only the build tool; the language rules stand | KISS; a mixed root still needs `language` |
| F3 | MEDIUM | How the reader gets the pins | as plain arguments from the caller, who already loads `[implement]` (`builder.py:135`, `implement.py:85`, `cli_kit/_core.py:134`) | no new tach edge `workspace.project → core.config` |
| F4 | MEDIUM | Where the "generatable" set lives | one tuple in `commons`; a test asserts `Language`'s values equal it; SF-04 removes the other copies | one source now, no churn in SF-01 |
| F5 | MEDIUM | What counts as a root file | regular files directly in the root, hidden ones included; folders never | a folder named `pom.xml` is not a build file |
| F6 | MEDIUM | Java vs Kotlin | the pure function takes `kotlin_sources: bool` (the reader checks `src/main/kotlin`) and reads the JVM build files for `kotlin` | today's rule, kept inside one language |
| F7 | LOW | Unreadable build file | the reader returns `None` on `OSError` or `UnicodeDecodeError`; the function treats it as empty text | a broken file still names its language by its name |
| F9 | MEDIUM | A root entry that is a symlink to a file outside the root | the reader reads it as `None` (resolved path not under the root) | a project file must not make SpecWeaver read elsewhere (red/blue R5) |
| F10 | LOW | TypeScript's build tool is `npm`, but no npm prepare exists | SF-02 keeps "no prepare" for npm, as today | the profile names the tool; the prepare plan decides what it does (red/blue R3) |
| F8 | LOW | Docs | §6c of `1_installation_and_setup.md` is rewritten in SF-02, when callers use the profile | a key documented before it acts would mislead |

## Proposed Changes

### `commons`

#### [NEW] `src/specweaver/commons/project_profile.py`
- `GENERATED_LANGUAGES = ("python", "java", "kotlin", "typescript", "rust")`.
- `BUILD_TOOLS = ("uv", "maven", "gradle", "cargo", "npm")`.
- `@dataclass(frozen=True) class ProjectProfile: language: str; build_tool: str` (`""` = none, as
  `detect_toolchain` today).
- `class ProjectUndecidedError(Exception)` with the message as its text.
- `decide_profile(root_files: frozenset[str], read: Callable[[str], str | None], *, kotlin_sources: bool, language: str | None = None, build_tool: str | None = None) -> ProjectProfile`.

Order of checks (the order matters: the pins first, so a pin always wins):
1. Contradicting pins → refuse, naming both `[agreed 2026-11-05]`. The pairs that agree: uv–python, cargo–rust,
   npm–typescript, maven/gradle–java/kotlin.
2. Language: the pin, else the candidates from the build files (FR-3); with no build file at all,
   the languages of the root's code files by `language_of`. More than one → refuse (FR-4). None →
   refuse ("no build file and no code file in <root>"). Not in `GENERATED_LANGUAGES` → refuse
   (FR-5).
3. Build tool: the pin, else from the language and its build file (FR-6); pom.xml and
   build.gradle* both → refuse.

Refusal texts (shown to users; one line, naming what was found and the setting):
- `the project root has build files for python (pyproject.toml) and typescript (package.json); set [implement] language in specweaver.toml`
- `go (go.mod) cannot be generated; SpecWeaver generates python, java, kotlin, typescript and rust`
- `the project root has pom.xml and build.gradle; set [implement] build_tool in specweaver.toml (maven or gradle)`

#### [MODIFY] `src/specweaver/commons/context.yaml`
`exposes` += `decide_profile`, `ProjectProfile`, `ProjectUndecidedError`, `GENERATED_LANGUAGES`, `BUILD_TOOLS`.

### `core/config`

#### [MODIFY] `src/specweaver/core/config/implement_policy.py`
`build_tool: Literal["uv","maven","gradle","cargo","npm"] | None = None`. The docstring stops saying
"its manifests decide (`sandbox.language`)".

### `workspace/project`

#### [NEW] `src/specweaver/workspace/project/project_profile.py`
`read_project_profile(root: Path, *, language: str | None = None, build_tool: str | None = None) -> ProjectProfile`:
list the root once (regular files), build a reader confined to the root that reads only names in the
listing, check `root / "src/main/kotlin"` is a folder, call `decide_profile`. It raises
`ProjectUndecidedError` unchanged.

#### [MODIFY] `src/specweaver/workspace/project/context.yaml`
`exposes` += `read_project_profile`.

## Commit Boundaries

### CB-1: the pure decision (FR-1, FR-3, FR-4, FR-5, FR-6)
Tests first, `tests/unit/commons/test_project_profile.py`, red because the module does not exist:

| Bucket | Case |
|---|---|
| Happy | each build file names its language; pom → maven, gradle → gradle, pyproject → uv, requirements only → `""`, Cargo → cargo, package.json+tsconfig → typescript/npm |
| Boundary | no build file: root `.py` files → python; package.json with a root `.ts` file → typescript; package.json alone → javascript → refused; JVM with `kotlin_sources` or `kotlin` in the build text → kotlin |
| Degradation | `read` returns None for an unreadable build file: still java, never a crash |
| Hostile | pyproject + package.json → refusal naming both files and `[implement] language`; go.mod, CMakeLists.txt → refusal naming the language; pom + build.gradle → refusal naming `build_tool`; empty root → refusal |

Plus `tests/unit/commons/test_foundation_reads_no_files.py` (NFR-2): parses every `commons/*.py` and
fails on a call to `open`, `read_text`, `read_bytes`, `iterdir`, `exists`, `is_file`, `is_dir`,
`glob`, `listdir`, `walk`.

Plus `tests/integration/commons/test_profile_agrees.py` (found at dev: the `cb` gate needs an
integration test beside `commons`): every ending of the one table is decided by it, and a
one-language root gets today's `detect_language`/`detect_toolchain` answer (npm aside, F10). SF-02
deletes its second half with the two detectors.

Mutants for the corpus (`TECH-079_mutants.json`), each must be OBJECTED:
- `mixed-root-picks-first`: the "more than one candidate" refusal returns the first candidate.
- `no-manifest-is-python`: the empty-root refusal returns python.
- `go-is-generated`: the `GENERATED_LANGUAGES` check is skipped.
- `pom-and-gradle-picks-gradle`: the build-tool clash returns gradle.
- `package-json-is-typescript`: the TypeScript test drops the `tsconfig.json`/`.ts` condition.

### CB-2: the pins and the reader (FR-2, FR-1's seam) — closes SF-01
Tests first:
- `tests/unit/core/config/test_implement_policy.py`: each `build_tool` value is read; `build_tool = "ant"`
  is refused naming `implement.build_tool` and its line; `Language`'s values equal
  `GENERATED_LANGUAGES`.
- `tests/unit/commons/test_project_profile.py`: a language pin wins over a mixed root; a build-tool
  pin wins over pom+gradle; contradicting pins (Q1).
- `tests/integration/workspace/project/test_read_project_profile.py` (seam reader → decision, real
  files in `tmp_path`): a folder named `pom.xml` is ignored; `src/main/kotlin` makes kotlin; a
  build file without read permission still names its language; a mixed root raises
  `ProjectUndecidedError` with both file names; files in subfolders never count (a `web/package.json`
  under a Python root stays python); a root `pom.xml` symlinked to a file outside the root is read as
  `None` (F9).

Red reason recorded at write time: `read_project_profile` and `build_tool` do not exist.

Mutants: `language-pin-ignored` (the pin is not read first), `subfolder-counts` (the reader walks
below the root).

Gates: `scripts/tests.py cb TECH-079 --kind bugfix`, `quality.py cb`, `tach check`, `mypy src/specweaver`.

## Verification
- `python scripts/tests.py sf TECH-079 --kind bugfix` at the end of CB-2.
- `check_fr_coverage.py TECH-079` cites FR-1..FR-6 from the files above.

## Research Notes
- `parse_section` (`core/config/settings_file.py:67`) validates against the model with
  `prefix=(name,)`, so a bad `build_tool` gets the same key-and-line error as `language` with no new code.
- `language_of` lowers the suffix (`commons/languages.py:41`), so `MAIN.PY` in the root counts as python.
- SpecWeaver's own root has `pyproject.toml` and `uv.lock` only (checked 2026-11-05): it decides python/uv.
