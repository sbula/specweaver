# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the wizard worked out about an undocumented project is what the first prompt carries.

Proves: INT-US-08 P-5

`sw scan` on a repository that documents nothing infers a `context.yaml` per module. This asserts the
thing that makes that worth doing: the inferred description reaches the prompt an agent is given, so
the model is told what the project's modules are *for* rather than being handed bare paths.

**An e2e for this already appeared to exist and does not.** `test_topology_e2e.py` says it covers
*"sw review --selector nhop injects neighbor context into prompt"*, runs `sw scan`, runs the review,
and then asserts:

    assert result.exit_code in (0, 1)
    assert "Traceback" not in result.output

That is a check that the command did not crash. It passes whether or not one word of topology reaches
the prompt, and `exit_code in (0, 1)` accepts failure as well as success. The claim in its docstring
is not the claim in its assertions.

One note for whoever mutates this next. `TopologyContext.get_prompt_content` renders the same fields
in the same layout and **is not the renderer on this path** — `PromptBuilder.add_topology` builds the
line itself. Breaking the former leaves this test green; breaking the latter is what fails it.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.graph.topology import TopologyGraph
from specweaver.graph.topology.engine import TopologyEngine
from specweaver.infrastructure.llm.prompt.builder import PromptBuilder

if TYPE_CHECKING:
    from pathlib import Path

_GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(_GIT is None, reason="git required")

#: The package docstring is the only description anywhere in this project — no `context.yaml`, no
#: manifest. Inference reads a Python package's purpose from its `__init__.py`, which is where a
#: package's docstring conventionally lives, so that is where the fixture puts it.
_INIT = '"""Double-entry ledger arithmetic."""\n'
_POSTINGS = "def post(amount: int) -> int:\n    return amount\n"


@pytest.fixture
def undocumented_project(tmp_path: Path) -> Path:
    project = tmp_path / "brownfield"
    ledger = project / "src" / "ledger"
    ledger.mkdir(parents=True)
    (ledger / "__init__.py").write_text(_INIT, encoding="utf-8")
    (ledger / "postings.py").write_text(_POSTINGS, encoding="utf-8")

    assert _GIT is not None
    for args in (("init",), ("config", "user.email", "t@t"), ("config", "user.name", "t")):
        subprocess.run([_GIT, *args], cwd=str(project), check=True, capture_output=True)

    assert not (ledger / "context.yaml").exists(), "the premise is that nothing is documented"
    return project


def test_what_inference_learned_is_what_the_prompt_says(undocumented_project: Path) -> None:
    """Infer → graph → prompt, with the inferred *content* asserted at the far end."""
    project = undocumented_project

    graph = TopologyGraph.from_project(project, TopologyEngine(), auto_infer=True)
    assert "ledger" in graph.nodes, (
        f"inference produced no node for src/ledger: {sorted(graph.nodes)}"
    )

    contexts = graph.format_context_summary("ledger", {"ledger"})
    assert contexts, "the graph produced no prompt context for a module it knows about"

    prompt = PromptBuilder().add_topology(contexts).build()

    # The assertion is on the *inferred* content, not on the section existing. A `<topology>` block
    # with nothing in it would satisfy a laxer check and tell the model nothing.
    assert "ledger" in prompt, f"the module's own name never reached the prompt:\n{prompt}"
    assert "Double-entry ledger arithmetic" in prompt, (
        "the purpose inference read out of the source did not reach the prompt — the model is being "
        f"handed a path and no description:\n{prompt}"
    )
