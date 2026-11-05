# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The shared boundary check judges a file's imports by the effective rule of its folder.

Proves: TECH-082 FR-16, FR-17, FR-19

Manifest paths start at the project root `[agreed 2026-11-05]`; imports under `if TYPE_CHECKING:`
count `[agreed 2026-11-05]`; a file no `context.yaml` covers is not judged `[agreed 2026-11-05]`.

| Bucket | Case |
|---|---|
| Happy | an allowed import passes; a forbidden one is a violation that names the fix; so is a forbidden library |
| Boundary | a grandparent's `forbids`; a declared `widens`; a sibling; a one-file module; `TYPE_CHECKING` |
| Degradation | no manifest gives a note; an unreadable file elsewhere in the tree is skipped; ignored folders are not judged |
| Hostile | a `..` entry in `consumes` opens nothing |
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.sandbox.language.core.boundary_check import check_boundaries

if TYPE_CHECKING:
    import pytest

DOMAIN = "name: domain\narchetype: pure-logic\nconsumes: [lib]\nforbids: [infra, '*.orm']\n"
CLI = "name: domain-cli\narchetype: adapter\nconsumes: [lib, infra]\nwidens:\n  infra: runs the database\n"


def _tree(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _base(root: Path) -> None:
    _tree(
        root,
        {
            "domain/context.yaml": DOMAIN,
            "domain/cli/context.yaml": CLI,
            "infra/__init__.py": "",
            "infra/db.py": "",
            "lib/__init__.py": "",
            "lib/util.py": "",
            "domain/__init__.py": "",
            "domain/cli/__init__.py": "",
        },
    )


def test_a_forbidden_import_is_a_violation_that_names_the_fix(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(tmp_path, {"domain/core/svc.py": "from infra import db\n"})

    result = check_boundaries(tmp_path, "domain/core/svc.py")

    assert result.violation_count == 1
    message = result.violations[0].message
    for part in ("domain/core/svc.py", "'infra'", "'domain'", "domain/context.yaml", "widens"):
        assert part in message, message


def test_allowed_imports_pass_and_libraries_are_counted(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(tmp_path, {"domain/core/svc.py": "import os\nimport requests\nfrom lib import util\n"})

    result = check_boundaries(tmp_path, "domain/core/svc.py")

    assert (result.violation_count, result.unmapped, result.note) == (0, 2, "")


def test_a_declared_widening_passes(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(tmp_path, {"domain/cli/main.py": "from infra import db\n"})

    assert check_boundaries(tmp_path, "domain/cli/main.py").violation_count == 0


def test_a_grandparents_forbids_still_applies(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(
        tmp_path,
        {
            # It consumes `infra` but declares no `widens`: `domain`'s `forbids` still binds it.
            "domain/cli/inner/context.yaml": "name: inner\narchetype: adapter\nconsumes: [lib, infra]\n",
            "domain/cli/inner/x.py": "from infra import db\n",
        },
    )

    assert check_boundaries(tmp_path, "domain/cli/inner/x.py").violation_count == 1


def test_a_sibling_inside_the_folder_passes(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(tmp_path, {"domain/core/svc.py": "from domain.cli import x\n", "domain/cli/x.py": ""})

    assert check_boundaries(tmp_path, "domain/core/svc.py").violation_count == 0


def test_a_one_file_module_matches_the_entry_naming_it(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(
        tmp_path,
        {
            "domain/context.yaml": DOMAIN.replace("consumes: [lib]", "consumes: [lib/util]"),
            "domain/core/svc.py": "from lib.util import f\n",
        },
    )

    assert check_boundaries(tmp_path, "domain/core/svc.py").violation_count == 0


def test_an_import_for_type_checking_counts(tmp_path: Path) -> None:
    _base(tmp_path)
    code = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from infra import db\n"
    _tree(tmp_path, {"domain/core/svc.py": code})

    assert check_boundaries(tmp_path, "domain/core/svc.py").violation_count == 1


def test_a_file_no_manifest_covers_is_not_judged(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(tmp_path, {"tools/run.py": "from infra import db\n"})

    result = check_boundaries(tmp_path, "tools/run.py")

    assert result.violation_count == 0
    assert "no context.yaml covers this file" in result.note


def test_a_file_of_no_code_language_is_not_judged(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(tmp_path, {"domain/notes.txt": "infra"})

    assert check_boundaries(tmp_path, "domain/notes.txt").note


def test_an_unreadable_file_elsewhere_is_skipped(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(tmp_path, {"domain/core/svc.py": "from infra import db\n"})
    (tmp_path / "lib" / "bad.py").write_bytes(b"\xff\xfe\x00broken")

    assert check_boundaries(tmp_path, "domain/core/svc.py").violation_count == 1


def test_a_dotdot_entry_opens_nothing(tmp_path: Path) -> None:
    _base(tmp_path)
    _tree(
        tmp_path,
        {
            "domain/context.yaml": DOMAIN.replace("consumes: [lib]", "consumes: [lib, ../infra]"),
            "domain/core/svc.py": "from infra import db\n",
        },
    )

    assert check_boundaries(tmp_path, "domain/core/svc.py").violation_count == 1


def test_an_import_only_missing_from_consumes_says_consumes(tmp_path: Path) -> None:
    """`other` is neither forbidden nor wider than a parent: `consumes` alone allows it."""
    _base(tmp_path)
    _tree(tmp_path, {"other/__init__.py": "", "domain/core/svc.py": "import other\n"})

    message = check_boundaries(tmp_path, "domain/core/svc.py").violations[0].message

    assert "add 'other' to consumes in domain/context.yaml" in message, message
    assert "widens" not in message, message


def test_a_folder_target_judges_every_code_file_under_it(tmp_path: Path) -> None:
    from specweaver.sandbox.language.core.boundary_check import check_architecture

    _base(tmp_path)
    _tree(
        tmp_path,
        {
            "domain/core/a.py": "from infra import db\nimport os\n",
            "domain/core/b.py": "from infra import db\n",
            "domain/core/notes.txt": "from infra import db\n",
        },
    )

    result = check_architecture(tmp_path, "domain/core", executor=None)

    assert sorted(v.file for v in result.violations) == ["domain/core/a.py", "domain/core/b.py"]
    assert (result.violation_count, result.unmapped, result.note) == (2, 1, "")


def test_a_folder_no_manifest_covers_says_so(tmp_path: Path) -> None:
    from specweaver.sandbox.language.core.boundary_check import check_architecture

    _tree(tmp_path, {"tools/a.py": "import os\n", "tools/b.py": "import sys\n"})

    result = check_architecture(tmp_path, "tools", executor=None)

    assert result.violation_count == 0
    assert "no context.yaml covers" in result.note


def test_a_forbidden_library_is_a_violation_others_are_counted(tmp_path: Path) -> None:
    """`forbids` meets a library by its written name; `consumes` never does `[agreed 2026-11-05]`."""
    _base(tmp_path)
    _tree(tmp_path, {"domain/core/svc.py": "import requests\nfrom sqlalchemy.orm import Session\n"})

    result = check_boundaries(tmp_path, "domain/core/svc.py")

    assert (result.violation_count, result.unmapped) == (1, 1)
    message = result.violations[0].message
    for part in ("'sqlalchemy.orm'", "reaches no project file", "'*.orm'", "domain/context.yaml"):
        assert part in message, message


def test_a_folder_target_skips_ignored_folders(tmp_path: Path) -> None:
    """`.specweaverignore` and each parser's default ignores (`node_modules/`) are not judged."""
    from specweaver.sandbox.language.core.boundary_check import check_architecture

    _base(tmp_path)
    _tree(
        tmp_path,
        {
            ".specweaverignore": "domain/core/gen/\n",
            "domain/core/gen/out.py": "from infra import db\n",
            "domain/core/node_modules/x/index.js": "const db = require('../../../../infra/db');\n",
            "domain/core/svc.py": "import os\n",
        },
    )

    result = check_architecture(tmp_path, "domain/core", executor=None)

    assert (result.violation_count, result.unmapped, result.note) == (0, 1, "")


def test_an_ignored_folder_is_never_entered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A JavaScript project's `node_modules/` can hold 100,000 files: the walk does not go in."""
    import os

    from specweaver.sandbox.language.core import boundary_check

    _base(tmp_path)
    _tree(tmp_path, {"web/node_modules/lib/deep/index.js": "", "web/app.js": ""})
    entered: list[str] = []
    real_walk = os.walk

    def spy(top, *args, **kwargs):
        for folder, dirs, names in real_walk(top, *args, **kwargs):
            entered.append(Path(folder).relative_to(tmp_path).as_posix())
            yield folder, dirs, names

    monkeypatch.setattr(boundary_check.os, "walk", spy)

    boundary_check.check_architecture(tmp_path, "web", executor=None)

    assert "web" in entered
    assert not [f for f in entered if "node_modules" in f], entered
