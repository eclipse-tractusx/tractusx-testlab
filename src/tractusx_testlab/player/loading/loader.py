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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Loader — resolves a YAML file or a ``.tck`` archive into a :class:`Tck`."""

from __future__ import annotations

import logging
import tempfile
import zipfile
from pathlib import Path

import yaml
from pydantic import ValidationError

from tractusx_testlab.compiler import package_digest
from tractusx_testlab.models.primitives.enums import ScriptKind
from tractusx_testlab.player.loading._parser import (
    _SCRIPT_ADAPTER,
    _TCK_ADAPTER,
    _normalize_discriminator,
    parse_script_file,
)
from tractusx_testlab.scripting.script import Tck as Tck
from tractusx_testlab.scripting.script import TestScript

# Entry name for the bundled authoring YAML inside .tck ZIP archives
_TCK_BUNDLE_ENTRY = "tck-bundle.yaml"

logger = logging.getLogger(__name__)


def _load_test_scripts(tests: list, base_dir: Path) -> list[TestScript]:
    """Resolve TCK ``tests:`` entries into TestScript objects.

    Each entry is a ``TckTestEntry`` with an ``id`` filename relative to
    ``<base_dir>/tests/``.  The ``skippable`` flag from the manifest entry is
    forwarded to the ``TestScript`` so the player can enforce skip rules.
    """
    scripts: list[TestScript] = []
    tests_dir = base_dir / "tests"
    validation_errors = []
    for entry in tests:
        test_path = tests_dir / entry.id
        if not test_path.exists():
            logger.warning("Test file not found, skipping: %s", test_path)
            continue
        try:
            script_def = parse_script_file(test_path)
            scripts.append(TestScript(script_def, skippable=entry.skippable, test_id=entry.id))
        except ValidationError as e:
            # 3. if Pydantic fails, capture exception to add filename
            validation_errors.append(f"File: {entry.id}\n{e}")
    if validation_errors:
        separator = "\n" + "-" * 80 + "\n"
        raise ValueError(
            f"Can't run. Validation failure in {len(validation_errors)} test(s):"
            f"{separator}{separator.join(validation_errors)}"
        )
    return scripts

def _detect_kind(data: dict) -> ScriptKind:
    """Detect the kind of a YAML document.

    Priority: explicit ``kind`` field → structural heuristic (``tests`` key).
    Raises ``ValueError`` if ``kind`` contradicts the document structure.
    """
    explicit = data.get("kind")
    has_tests_key = "tests" in data

    if explicit is not None:
        kind = ScriptKind(explicit)
        if kind == ScriptKind.TEST and has_tests_key:
            raise ValueError(
                "YAML declares kind: test but contains a 'tests' key. "
                "Use kind: tck for manifests that group multiple tests."
            )
        if kind == ScriptKind.TCK and not has_tests_key:
            raise ValueError(
                "YAML declares kind: tck but is missing the 'tests' key. "
                "A TCK must list its tests under the 'tests' key."
            )
        return kind

    return ScriptKind.TCK if has_tests_key else ScriptKind.TEST


class Loader:
    """Loads a TCK from a YAML file or a ``.tck`` archive, plain or encrypted."""

    __slots__ = ()

    def load(
        self,
        path: Path,
        player_private_key: bytes | None = None,
        compiler_public_key: bytes | None = None,
    ) -> Tck:
        """Load a TCK from *path*.

        Uses the local parser to support testlab-extended enum values
        (assertion types, service types) that the SDK parser rejects.
        """
        if path.suffix == ".tck":
            return self._load_tck_package(path, player_private_key, compiler_public_key)

        return self._load_yaml(path)

    def _load_tck_package(
        self,
        path: Path,
        player_private_key: bytes | None = None,
        compiler_public_key: bytes | None = None,
    ) -> Tck:
        """Load a .tck ZIP archive — plain or encrypted (payload.enc format).

        Extracts ``tck-bundle.yaml`` from the archive and parses it
        using the standard YAML pipeline.  The archive is extracted to
        a temporary directory so that relative asset paths resolve.
        """
        if not zipfile.is_zipfile(path):
            raise ValueError(
                f"File has .tck extension but is not a valid ZIP archive: {path}"
            )

        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()

        if "payload.enc" in names:
            return self._load_encrypted_tck_package(path, player_private_key, compiler_public_key)

        with zipfile.ZipFile(path, "r") as zf:
            entries = {name: zf.read(name) for name in zf.namelist()}

        if _TCK_BUNDLE_ENTRY not in entries:
            raise ValueError(
                f"Package is missing the bundled test definition "
                f"({_TCK_BUNDLE_ENTRY}). Re-compile the package with "
                f"the latest testlab compiler."
            )

        # Verified before anything is written to disk, so a package that fails
        # never reaches a path something else might read.
        _verify_tck_integrity(entries)

        extract_dir = Path(tempfile.mkdtemp(prefix="tck_"))
        for name, blob in entries.items():
            target = extract_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)

        data = yaml.safe_load(entries[_TCK_BUNDLE_ENTRY].decode("utf-8"))
        return self._parse_data(data, source_path=path, base_dir=extract_dir)

    def _load_encrypted_tck_package(
        self,
        path: Path,
        player_private_key: bytes | None,
        compiler_public_key: bytes | None,
    ) -> Tck:
        """Decrypt payload.enc, extract the TAR, and load tck-bundle.yaml."""
        import base64
        import io as _io
        import tarfile

        from tractusx_testlab.security.crypto.encryption import decrypt_package
        from tractusx_testlab.security.crypto.signing import verify_signature

        if player_private_key is None:
            raise ValueError(
                f"Package {path.name!r} is encrypted — provide --player-keys to load it."
            )

        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            manifest_raw = zf.read("manifest.yaml")
            payload_raw = zf.read("payload.enc")
            sig_raw = zf.read("signature.sig") if "signature.sig" in names else None

        manifest = yaml.safe_load(manifest_raw)
        players = manifest.get("security", {}).get("authorized_players", [])
        if not players:
            raise ValueError("Encrypted .tck has no authorized_players in manifest.")

        enc_key = base64.b64decode(players[0]["encrypted_key"])
        blob = base64.b64decode(payload_raw)
        tar_bytes = decrypt_package(enc_key, blob[:12], blob[12:], player_private_key)

        # A signed package is verified or refused; there is no third outcome.
        # This used to be `if compiler_public_key and sig_raw:`, so a caller that
        # supplied no key simply skipped the check — and `testlab run` only
        # required one for the since-deleted `.stck`, which meant an encrypted
        # `.tck` decrypted and ran with its signature unexamined.
        if sig_raw is None:
            raise ValueError(
                f"Encrypted package {path.name!r} carries no signature. It cannot "
                f"be shown to come from the compiler it claims."
            )
        if compiler_public_key is None:
            raise ValueError(
                f"Encrypted package {path.name!r} is signed, but no compiler public "
                f"key was supplied to check it against. Pass --compiler-pub."
            )
        if not verify_signature(tar_bytes, base64.b64decode(sig_raw), compiler_public_key):
            raise ValueError("Package signature verification failed — untrusted source.")

        with tarfile.open(fileobj=_io.BytesIO(tar_bytes), mode="r:gz") as tf:
            entries = {
                member.name: (tf.extractfile(member) or _io.BytesIO()).read()
                for member in tf.getmembers()
                if member.isfile()
            }

        if _TCK_BUNDLE_ENTRY not in entries:
            raise ValueError(
                f"Decrypted package is missing {_TCK_BUNDLE_ENTRY}. "
                "Re-compile with the latest testlab compiler."
            )
        _verify_tck_integrity(entries)

        extract_dir = Path(tempfile.mkdtemp(prefix="tck_enc_"))
        for name, blob in entries.items():
            target = extract_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)

        data = yaml.safe_load(entries[_TCK_BUNDLE_ENTRY].decode("utf-8"))
        return self._parse_data(data, source_path=path, base_dir=extract_dir)

    def _load_yaml(self, path: Path) -> Tck:
        """Load a plain YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return self._parse_data(data, source_path=path, base_dir=path.parent)

    def _parse_data(self, data: object, source_path: Path, base_dir: Path) -> Tck:
        """Parse raw YAML data into a Tck runtime object.
        """
        if not isinstance(data, dict):
            raise ValueError(
                f"Expected a YAML mapping from {source_path}, got {type(data).__name__}"
            )
        kind = _detect_kind(data)
        normalized = _normalize_discriminator(data, source_path)

        if kind == ScriptKind.TCK:
            tck_def = _TCK_ADAPTER.validate_python(normalized)
            tck = Tck(tck_def, base_dir=base_dir)
            tck._scripts = _load_test_scripts(tck_def.tests, base_dir)
            return tck
        else:
            script_def = _SCRIPT_ADAPTER.validate_python(normalized)
            return Tck.from_single_script(script_def, base_dir=base_dir)


def _verify_tck_integrity(entries: dict[str, bytes]) -> None:
    """Refuse a package whose contents are not the ones it was sealed with.

    Delegates to :func:`~tractusx_testlab.compiler.package_digest.verify`, the
    same function the compiler seals with. The two used to be separate
    computations over two different sets of bytes: the digest covered
    ``manifest.yaml``, the compiled IR and the asset digests, while the player
    executed ``tests/*.yaml``, which was in none of them. A step appended to a
    test file inside a compiled ``.tck`` ran with no integrity error at all.
    """
    package_digest.verify(entries)
