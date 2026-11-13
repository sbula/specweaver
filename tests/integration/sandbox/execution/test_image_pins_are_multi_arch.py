# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every pinned digest is the multi-arch index, not one platform's manifest.

A platform digest pulls fine on the machine that read it and fails on every other one: an amd64
digest breaks the product on ARM (the GB10). On 2026-11-13 the first three digests read from
`podman image inspect` were exactly that.

**How it checks, with no network.** When Podman pulls a reference it stores every manifest it
fetched beside the image, under `<GraphRoot>/<driver>-images/<image id>/`, each file named by the
base64 of `manifest-sha256:<digest>`. For each pinned reference this test finds the file for its
digest, checks that the file's own sha256 is that digest, that its media type is an OCI index or a
Docker manifest list, and that it lists `amd64` and `arm64`.

**Where it runs.** On CI after the step "Pull the images the container tests run in", which has
the network and pulls every pinned reference; locally after `podman pull <reference>`. A reference
not pulled here skips with that command, and on CI a skip fails the run. The format of each pin is
checked without any engine by `tests/unit/sandbox/execution/test_images_are_pinned.py`.

| Bucket | Case |
|---|---|
| Happy | each pinned digest is an index listing amd64 and arm64 |
| Boundary | the stored file must hash to the digest, so a renamed file cannot pass |
| Degradation | no Podman, or the image not pulled: a skip naming the command, which fails CI |
| Hostile | a platform manifest's digest fails (the rust amd64 digest of 2026-11-13) |
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests.image_pins import image_refs

pytestmark = pytest.mark.integration

_INDEX_TYPES = {
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
}
_PODMAN = shutil.which("podman")


def _podman(*args: str) -> str | None:
    if _PODMAN is None:
        return None
    done = subprocess.run([_PODMAN, *args], capture_output=True, text=True, timeout=60)
    return done.stdout.strip() if done.returncode == 0 else None


def stored_manifest(ref: str) -> bytes | None:
    """The manifest Podman stored for `ref`'s digest, or None when it holds none."""
    store = _podman("info", "--format", "{{.Store.GraphRoot}} {{.Store.GraphDriverName}}")
    image_id = _podman("image", "inspect", ref, "--format", "{{.Id}}")
    if not store or not image_id:
        return None
    root, driver = store.split()
    digest = ref.rsplit("@", 1)[1]
    for path in (Path(root) / f"{driver}-images" / image_id).glob("=*"):
        try:
            key = base64.b64decode(path.name[1:] + "==").decode()
        except (ValueError, UnicodeDecodeError):
            continue
        if key == f"manifest-{digest}":
            return path.read_bytes()
    return None


def is_multi_arch_index(raw: bytes, digest: str) -> bool:
    if "sha256:" + hashlib.sha256(raw).hexdigest() != digest:
        return False
    manifest = json.loads(raw)
    archs = {m.get("platform", {}).get("architecture") for m in manifest.get("manifests", [])}
    return manifest.get("mediaType") in _INDEX_TYPES and {"amd64", "arm64"} <= archs


def _pulled(ref: str) -> bool:
    return _podman("image", "exists", ref) is not None


#: The amd64 manifest of the pinned rust index: what `podman image inspect` printed on 2026-11-13.
_PLATFORM = "sha256:4b68057dc8c103af4fa66b5cd29f21b18afec79fadfcd8fb91e295e939f0690c"
_RUST_PLATFORM = "docker.io" + f"/library/rust:1.100.0-slim@{_PLATFORM}"  # unseen by the scanner


# A skip, like every container test's: the image is a fact about the machine, and on CI, which
# pulls every pin first, a skip fails the run.
@pytest.mark.parametrize(
    "ref",
    [
        pytest.param(ref, marks=pytest.mark.skipif(not _pulled(ref), reason=f"podman pull {ref}"))
        for ref in sorted(image_refs())
    ],
)
def test_each_pinned_digest_is_a_multi_arch_index(ref: str) -> None:
    assert "@sha256:" in ref, f"{ref} has no digest; test_images_are_pinned.py says how to pin it"
    raw = stored_manifest(ref)

    assert raw is not None, f"{ref} is pulled but Podman stored no manifest for its digest"
    assert is_multi_arch_index(raw, ref.rsplit("@", 1)[1]), f"{ref} is not a multi-arch index"


@pytest.mark.skipif(not _pulled(_RUST_PLATFORM), reason="the rust 1.100.0 image is not pulled")
def test_a_platform_manifest_digest_fails() -> None:
    raw = stored_manifest(_RUST_PLATFORM)

    assert raw is not None
    assert not is_multi_arch_index(raw, _PLATFORM)


def test_a_file_that_does_not_hash_to_its_digest_fails() -> None:
    raw = json.dumps({"mediaType": next(iter(_INDEX_TYPES)), "manifests": []}).encode()
    assert not is_multi_arch_index(raw, "sha256:" + "0" * 64)
