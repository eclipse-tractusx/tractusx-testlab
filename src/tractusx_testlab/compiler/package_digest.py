#################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""The digest of a compiled package — computed once, used to seal and to verify.

A TCK is a certification instrument that travels between organisations, so the
one thing its digest has to cover is **everything the player will execute**.

It did not. The digest was computed in the IR builder over
``manifest.yaml + tck-execution.json + asset digests``, and the archive was
assembled afterwards by the CLI, which added the test files the player actually
runs. Appending a step to one of those inside a compiled ``.tck`` therefore
changed what executed and matched the recorded digest exactly — the package
verified, and the injected step ran.

Writing and verifying live in this one module for the same reason the mismatch
existed: they were in two places, computed over two different sets of bytes, and
nothing compared them.
"""

from __future__ import annotations

import hashlib

#: The entry carrying the digest. Excluded from its own computation — a checksum
#: cannot cover the field it is written into.
MANIFEST_ENTRY = "manifest.yaml"

#: Prefix identifying the algorithm, so a future change is a visible one.
ALGORITHM = "blake2b"

_DIGEST_SIZE = 32


def compute(entries: dict[str, bytes], *, manifest_bytes: bytes) -> str:
    """Return the digest of a package whose archive holds *entries*.

    *entries* is every file in the archive keyed by its archive path, and
    *manifest_bytes* is the manifest with its ``package.checksum`` field blanked.

    Every entry is covered, name included: renaming a file changes the digest as
    surely as editing one, so a test cannot be swapped for another under a name
    the manifest already trusts.
    """
    digest = hashlib.blake2b(digest_size=_DIGEST_SIZE)
    digest.update(manifest_bytes)
    for name in sorted(entries):
        if name == MANIFEST_ENTRY:
            continue
        digest.update(name.encode("utf-8"))
        digest.update(hashlib.blake2b(entries[name], digest_size=_DIGEST_SIZE).digest())
    return f"{ALGORITHM}:{digest.hexdigest()}"


def blank_checksum(manifest: dict) -> dict:
    """Return *manifest* with its recorded checksum cleared.

    The value being computed cannot be part of its own input, so both sides
    blank the same field the same way — through here, rather than each
    remembering to.
    """
    package = {**manifest.get("package", {}), "checksum": ""}
    return {**manifest, "package": package}


def _dump(manifest: dict) -> bytes:
    """Serialise a manifest the one way both sides serialise it."""
    import yaml

    return yaml.dump(manifest, default_flow_style=False, sort_keys=False).encode("utf-8")


def seal(entries: dict[str, bytes]) -> dict[str, bytes]:
    """Return *entries* with the manifest's ``package.checksum`` filled in.

    The single place a package is sealed. The compiler calls it when building an
    archive and the tests call it when building a fixture, so a fixture is
    necessarily a package the loader will accept — a test cannot accidentally
    assert against a sealing rule that only exists in the test.

    Raises:
        ValueError: if there is no manifest to record the digest in.
    """
    import yaml

    manifest_bytes = entries.get(MANIFEST_ENTRY)
    if manifest_bytes is None:
        raise ValueError(f"Cannot seal a package with no {MANIFEST_ENTRY}.")

    manifest = yaml.safe_load(manifest_bytes.decode("utf-8")) or {}
    checksum = compute(entries, manifest_bytes=_dump(blank_checksum(manifest)))
    manifest.setdefault("package", {})["checksum"] = checksum

    return {**entries, MANIFEST_ENTRY: _dump(manifest)}


def verify(entries: dict[str, bytes]) -> None:
    """Refuse *entries* unless they are the contents the manifest was sealed with.

    Nothing here returns early. A missing manifest, a missing digest and a
    mismatch are all refusals: a verification that passes because its input is
    absent is worse than no verification, because the caller records the package
    as verified — which is precisely what deleting one file from a ``.tck`` used
    to achieve.
    """
    import yaml

    manifest_bytes = entries.get(MANIFEST_ENTRY)
    if manifest_bytes is None:
        raise ValueError(
            f"Package has no {MANIFEST_ENTRY} — nothing states what it should "
            f"contain, so it cannot be verified."
        )

    manifest = yaml.safe_load(manifest_bytes.decode("utf-8")) or {}
    expected = str(manifest.get("package", {}).get("checksum", ""))
    if not expected:
        raise ValueError(
            "Package manifest records no checksum. Re-compile it with a current "
            "testlab: a package that carries no digest cannot be shown to be the "
            "one that was compiled."
        )

    actual = compute(entries, manifest_bytes=_dump(blank_checksum(manifest)))
    if actual != expected:
        raise ValueError(
            "Package checksum mismatch — the contents are not the ones this "
            f"package was sealed with.\n  expected {expected}\n  actual   {actual}"
        )
