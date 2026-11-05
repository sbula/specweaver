# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Going down the folder tree a module gets stricter; it is wider only where it declares `widens`.

Proves: TECH-082 FR-15

The rule `[agreed 2026-11-03]`: a child's `forbids` are its own plus all its ancestors'; each of its
`consumes` lies inside its parent's `consumes` (plus the parent's `widens`), inside the parent's own
folder (a sibling), or in its own `widens`. A `consumes` entry that overlaps a forbidden path, inside
it or containing it, breaks the rule unless `widens` covers it. A `widens` entry needs a reason and
must widen something. A folder without a manifest takes its nearest ancestor's rule.

| Bucket | Case |
|---|---|
| Happy | inside the parent passes; a grandparent's forbid reaches a grandchild; a sibling is no widening; a declared widening lifts one forbidden path only; an undeclared one is "wider" |
| Boundary | a top manifest is judged alone; a glob forbid; name-form and path-form entries; a folder without a manifest takes its ancestor's rule; `allows` per target |
| Degradation | an empty manifest; a parent without `consumes`; a node without a path is ignored |
| Hostile | an empty or blank reason; a stale `widens`; a broad entry containing a forbidden part; `..` and absolute entries |
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from specweaver.assurance.graph.boundary_rule import Breach, allows, breaches
from specweaver.assurance.graph.topology import TopologyNode


def _tree(root: Path, **folders: dict) -> dict[str, TopologyNode]:
    """One node per folder; keys are folders with `__` for `/`, values the manifest lists."""
    nodes = {}
    for key, lists in folders.items():
        folder = key.replace("__", "/")
        name = lists.get("name", folder)
        nodes[name] = TopologyNode(
            name=name,
            level="module",
            purpose="",
            archetype="",
            consumes=list(lists.get("consumes", [])),
            forbids=list(lists.get("forbids", [])),
            widens=dict(lists.get("widens", {})),
            yaml_path=root / folder / "context.yaml",
        )
    return nodes


# -- Happy ------------------------------------------------------------------


def test_a_child_inside_its_parent_passes(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={"consumes": ["lib"]}, a__c={"consumes": ["lib/net"]})

    assert breaches(nodes, tmp_path) == []


def test_a_grandparents_forbid_reaches_the_grandchild(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={"forbids": ["lib/net"]},
        a__b={},
        a__b__c={"consumes": ["lib/net"]},
    )

    found = breaches(nodes, tmp_path)

    assert Breach("a/b/c", "lib/net", "uses-forbidden", "a/b") in found


def test_a_sibling_is_no_widening(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={}, a__x={"consumes": ["a/y"]}, a__y={})

    assert breaches(nodes, tmp_path) == []


def test_a_declared_widening_lifts_one_forbidden_path_only(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={"forbids": ["lib/*"]},
        a__c={"consumes": ["lib/net", "lib/disk"], "widens": {"lib/net": "it sends"}},
    )

    found = breaches(nodes, tmp_path)

    assert [b for b in found if b.entry == "lib/net"] == []
    assert Breach("a/c", "lib/disk", "uses-forbidden", "a") in found


def test_an_undeclared_widening_is_wider(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={"consumes": ["lib"]}, a__c={"consumes": ["other"]})

    assert breaches(nodes, tmp_path) == [Breach("a/c", "other", "wider", "a")]


def test_a_widening_beyond_the_parent_passes(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={"consumes": ["lib"]},
        a__c={"consumes": ["kit"], "widens": {"kit": "the commands print through it"}},
    )

    assert breaches(nodes, tmp_path) == []


def test_a_parents_widening_counts_as_its_consumes(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        top={},
        top__a={"consumes": ["kit"], "widens": {"kit": "why"}},
        top__a__c={"consumes": ["kit/print"]},
    )

    assert breaches(nodes, tmp_path) == []


# -- Boundary ---------------------------------------------------------------


def test_a_top_manifest_is_judged_by_its_own_lists(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={"consumes": ["anything", "lib/net"], "forbids": ["lib"]})

    assert breaches(nodes, tmp_path) == [Breach("a", "lib/net", "uses-forbidden", None)]


def test_a_glob_forbid_matches_one_segment(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={"consumes": ["lib"], "forbids": ["lib/*/api"]},
        a__c={"consumes": ["lib/net/api/x", "lib/net/core"]},
    )

    found = breaches(nodes, tmp_path)

    assert Breach("a/c", "lib/net/api/x", "uses-forbidden", "a") in found
    assert [b for b in found if b.entry == "lib/net/core"] == []


def test_name_form_and_path_form_entries_agree(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        tools__kit={"name": "kit"},
        a={"consumes": ["kit"]},
        a__c={"consumes": ["tools/kit/print", "kit"]},
    )

    assert breaches(nodes, tmp_path) == []


def test_dotted_entries_name_the_same_folder(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={"consumes": ["lib.net"]}, a__c={"consumes": ["lib/net/x"]})

    assert breaches(nodes, tmp_path) == []


def test_a_folder_without_a_manifest_takes_its_ancestors_rule(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={"consumes": ["lib"], "forbids": ["lib/net"]},
        a__c={"consumes": ["lib/disk"]},
    )

    assert allows(nodes, tmp_path, "a/c/deep/er", "lib/disk/read")
    assert not allows(nodes, tmp_path, "a/c/deep/er", "lib/net")
    assert not allows(nodes, tmp_path, "a/c/deep/er", "other")


def test_allows_the_folder_itself_a_widening_and_a_whole_module(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={"forbids": ["lib/*"]},
        a__c={"consumes": ["lib/net", "box/git/core"], "widens": {"lib/net": "it sends"}},
    )

    assert allows(nodes, tmp_path, "a/c", "a/c/inner")
    assert allows(nodes, tmp_path, "a/c", "lib/net/socket")
    assert allows(nodes, tmp_path, "a/c", "box")  # a whole module whose part is consumed
    assert not allows(nodes, tmp_path, "a/c", "lib/disk")


# -- Degradation ------------------------------------------------------------


def test_an_empty_manifest_breaks_nothing(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={}, a__c={})

    assert breaches(nodes, tmp_path) == []


def test_a_parent_without_consumes_makes_every_child_entry_wider(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={}, a__c={"consumes": ["lib"]})

    assert breaches(nodes, tmp_path) == [Breach("a/c", "lib", "wider", "a")]


def test_a_node_without_a_path_is_ignored(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={"consumes": ["lib"]})
    nodes["ghost"] = TopologyNode(name="ghost", level="", purpose="", archetype="", consumes=["x"])

    assert breaches(nodes, tmp_path) == []


# -- Hostile ----------------------------------------------------------------


def test_an_empty_or_blank_reason_is_refused(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={},
        a__c={"consumes": ["kit", "box"], "widens": {"kit": "", "box": "   "}},
    )

    found = breaches(nodes, tmp_path)

    assert Breach("a/c", "kit", "empty-reason", "a") in found
    assert Breach("a/c", "box", "empty-reason", "a") in found


def test_a_widening_that_widens_nothing_is_stale(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={"consumes": ["lib"]},
        a__c={"consumes": ["lib/net"], "widens": {"lib/net": "not needed", "gone": "no consumer"}},
    )

    found = breaches(nodes, tmp_path)

    assert Breach("a/c", "lib/net", "stale-widens", "a") in found
    assert Breach("a/c", "gone", "stale-widens", "a") in found


def test_a_broad_entry_containing_a_forbidden_part_breaks_the_rule(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={"consumes": ["lib"], "forbids": ["lib/*/api"]},
        a__c={"consumes": ["lib"]},
    )

    found = breaches(nodes, tmp_path)

    assert Breach("a/c", "lib", "uses-forbidden", "a") in found


def test_parent_and_absolute_entries_name_no_folder(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={"consumes": ["../outside", "/etc", "lib/../../x"]})

    found = breaches(nodes, tmp_path)

    assert {(b.entry, b.kind) for b in found} == {
        ("../outside", "bad-entry"),
        ("/etc", "bad-entry"),
        ("lib/../../x", "bad-entry"),
    }


def test_a_backslash_entry_names_no_folder(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={"consumes": ["lib\\net"]})

    assert breaches(nodes, tmp_path) == [Breach("a", "lib\\net", "bad-entry", None)]


def test_bad_forbids_and_widens_entries_are_named(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={"forbids": ["../up"], "widens": {"/abs": "why"}})

    found = breaches(nodes, tmp_path)

    assert Breach("a", "../up", "bad-entry", None) in found
    assert Breach("a", "/abs", "bad-entry", None) in found


def test_a_node_outside_the_root_is_ignored(tmp_path: Path) -> None:
    root = tmp_path / "project"
    nodes = _tree(root, a={"consumes": ["lib"]})
    nodes["far"] = TopologyNode(
        name="far",
        level="",
        purpose="",
        archetype="",
        consumes=["x"],
        yaml_path=tmp_path / "elsewhere" / "context.yaml",
    )

    assert breaches(nodes, root) == []


def test_allows_without_any_manifest_and_for_a_bad_target(tmp_path: Path) -> None:
    nodes = _tree(tmp_path, a={"consumes": ["lib"]})

    assert allows(nodes, tmp_path, "other/place", "anything")
    assert not allows(nodes, tmp_path, "a", "../lib")


def test_a_root_manifests_own_folder_does_not_lift_its_forbids(tmp_path: Path) -> None:
    nodes = {
        "root": TopologyNode(
            name="root",
            level="",
            purpose="",
            archetype="",
            consumes=["app"],
            forbids=["app/legacy"],
            yaml_path=tmp_path / "context.yaml",
        )
    }

    assert allows(nodes, tmp_path, "", "app/new")
    assert not allows(nodes, tmp_path, "", "app/legacy/old")


def test_an_entry_a_forbid_glob_only_might_reach_is_not_containing(tmp_path: Path) -> None:
    nodes = _tree(
        tmp_path,
        a={"consumes": ["box/dispatch", "box"], "forbids": ["box/*/api"]},
    )

    found = breaches(nodes, tmp_path)

    assert [b.entry for b in found] == ["box"]


def test_needs_widens_only_where_consumes_is_not_enough(tmp_path: Path) -> None:
    from specweaver.assurance.graph.boundary_rule import BoundaryRule

    nodes = _tree(tmp_path, a={"consumes": ["lib"], "forbids": ["lib/net"]}, a__c={})
    rule = BoundaryRule(nodes, tmp_path)

    assert rule.needs_widens("a", "lib/net")  # forbidden
    assert rule.needs_widens("a/c", "other")  # wider than the parent `a`
    assert not rule.needs_widens("a", "other")  # `a` has no parent: consumes is enough
    assert not rule.needs_widens("tools", "lib/net")  # no manifest rules `tools`


def test_a_library_is_forbidden_by_its_written_name(tmp_path: Path) -> None:
    """An import that reaches no project folder still meets `forbids` `[agreed 2026-11-05]`."""
    from specweaver.assurance.graph.boundary_rule import BoundaryRule

    nodes = _tree(tmp_path, a={"forbids": ["*.orm", "acme/net/*"]}, a__c={})
    rule = BoundaryRule(nodes, tmp_path)

    assert rule.forbids_library("a/c", "sqlalchemy.orm")  # an ancestor's glob, dotted name
    assert rule.forbids_library("a", "sqlalchemy.orm.session")  # below the forbidden name
    assert rule.forbids_library("a", "acme::net::tcp")  # Rust's `::`
    assert rule.forbids_library("a", "acme/net")  # a `/` name
    assert not rule.forbids_library("a", "requests")
    assert not rule.forbids_library("tools", "sqlalchemy.orm")  # no manifest rules `tools`
    assert not rule.forbids_library("a", ".orm")  # a relative name is no library
    assert not rule.forbids_library("a", "")
