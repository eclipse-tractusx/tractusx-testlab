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

"""Building an encrypted ``.tck`` — the payload.enc + signature.sig format.

Everything that turns a compiled package into a signed, encrypted artefact for
a named set of players. :mod:`tractusx_testlab.cli.compile` decides *what* to
build from the flags it was given; this module builds it.
"""

from __future__ import annotations

import base64
import io
import tarfile
import tempfile
import zipfile
from pathlib import Path

import typer
import yaml

from tractusx_testlab.compiler import package_digest
from tractusx_testlab.compiler.compiler import Compiler
from tractusx_testlab.security.crypto.encryption import encrypt_for_recipients
from tractusx_testlab.security.crypto.keygen import _fingerprint
from tractusx_testlab.security.crypto.signing import package_signing_message, sign_bytes
from tractusx_testlab.security.trust.identity import PlayerIdentity

# Archive entry name for the bundled authoring YAML
TCK_BUNDLE_ENTRY = "tck-bundle.yaml"


def embed_bundle_yaml(manifest_path: Path, output_dir: Path) -> None:
    """Embed manifest + test files in the output dir for runtime loading."""
    import shutil

    import yaml as _yaml

    with open(manifest_path, encoding="utf-8") as f:
        tck_data = _yaml.safe_load(f)

    bundled = _yaml.dump(tck_data, default_flow_style=False, sort_keys=False)
    (output_dir / TCK_BUNDLE_ENTRY).write_text(bundled, encoding="utf-8")

    # Copy referenced test files into tests/ subdirectory
    tests_raw = tck_data.get("tests", [])
    if not tests_raw:
        return

    tests_dir = output_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    base_dir = manifest_path.parent

    for entry in tests_raw:
        file_ref = entry if isinstance(entry, str) else entry.get("id", "")
        if not file_ref:
            continue
        source_file = base_dir / "tests" / file_ref
        if not source_file.exists():
            source_file = base_dir / file_ref
        if source_file.exists():
            shutil.copy2(source_file, tests_dir / Path(file_ref).name)


def sealed_entries(source_dir: Path) -> dict[str, bytes]:
    """Read every file under *source_dir* and seal the manifest over them.

    The one place a compiled directory becomes package entries, for both
    shapes. Keys are archive paths relative to *source_dir* — ``tests/a.yaml``,
    never ``./tests/a.yaml`` — so the loader finds ``tck-bundle.yaml`` under
    the name it looks for and the digest covers the names it verifies.
    """
    entries = {
        path.relative_to(source_dir).as_posix(): path.read_bytes()
        for path in sorted(source_dir.rglob("*"))
        if path.is_file()
    }
    return package_digest.seal(entries)


def create_tar_bytes(entries: dict[str, bytes]) -> bytes:
    """Pack *entries* into a gzip-compressed TAR in memory, under their own names.

    This used to ``tar.add(source_dir, arcname=".")``, which names every member
    ``./<path>``; the loader looked each entry up without the prefix and refused
    every encrypted package as missing ``tck-bundle.yaml``.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name in sorted(entries):
            info = tarfile.TarInfo(name)
            info.size = len(entries[name])
            tf.addfile(info, io.BytesIO(entries[name]))
    return buf.getvalue()


def build_encrypted_payload(
    tar_bytes: bytes,
    recipient_keys: dict[str, bytes],
) -> tuple[str, list[dict]]:
    """Encrypt *tar_bytes* with a single AES key wrapped for each recipient.

    Returns:
        (payload_b64, authorized_players) where payload_b64 = base64(nonce + ciphertext)
    """
    nonce, ciphertext, key_blocks = encrypt_for_recipients(tar_bytes, recipient_keys)
    payload_b64 = base64.b64encode(nonce + ciphertext).decode()
    authorized_players = [
        {"player_id": pid, "encrypted_key": base64.b64encode(enc_key).decode()}
        for pid, enc_key in key_blocks
    ]
    return payload_b64, authorized_players


def build_redacted_manifest(
    manifest_dict: dict,
    compiler_id: str,
    authorized_players: list[dict],
) -> dict:
    """Build a manifest that omits test IDs and asset paths but keeps TCK identity metadata.

    It carries no signature: the signature is over this manifest's bytes and
    lives beside it in ``signature.sig``.
    """
    result: dict = {
        "kind": "manifest",
        "package": {
            "format": "tck",
            "format_version": manifest_dict["package"]["format_version"],
            "testlab": manifest_dict["package"]["testlab"],
            "checksum": manifest_dict["package"]["checksum"],
            "encrypted": True,
            "allow_asset_override": False,
        },
        "tck": manifest_dict.get("tck", {}),
        "compilation": {
            "compiled_at": manifest_dict["compilation"]["compiled_at"],
            "compiler_version": manifest_dict["compilation"]["compiler_version"],
            "fingerprint": manifest_dict["compilation"]["fingerprint"],
        },
        "security": {
            "algorithm": "AES-256-GCM",
            "key_derivation": "RSA-OAEP-SHA256",
            "compiler_id": compiler_id,
            "authorized_players": authorized_players,
        },
    }
    return result


def write_encrypted_tck(
    tck_path: Path,
    manifest_bytes: bytes,
    payload_b64: str,
    signature_b64: str,
) -> None:
    """Write the encrypted .tck ZIP archive to *tck_path*.

    Takes the manifest as bytes, not a dict: the signature is over these exact
    bytes, and re-serializing here could write different ones.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.yaml", manifest_bytes)
        zf.writestr("payload.enc", payload_b64)
        zf.writestr("signature.sig", signature_b64)
    tck_path.parent.mkdir(parents=True, exist_ok=True)
    tck_path.write_bytes(buf.getvalue())


def _seal_and_encrypt(
    manifest: Path,
    compiler_keys: Path,
    player_pub: list[Path],
    version: str | None,
    compiler: Compiler,
) -> tuple[dict, dict, bytes, str, str]:
    """Compile, seal, encrypt and sign *manifest* for the listed players.

    Returns ``(sealed_manifest, redacted_manifest, manifest_bytes, payload_b64,
    signature_b64)``. The payload is sealed so the loader verifies the decrypted
    entries exactly as it verifies a readable package. The signature is over the
    readable manifest *and* the encrypted payload (ADR-0012), so neither half of
    the archive can change without the other's signature failing.
    """
    compiler_identity = PlayerIdentity.load(compiler_keys)
    recipient_keys: dict[str, bytes] = {}
    for pub_path in player_pub:
        pub_bytes = pub_path.read_bytes()
        fp = _fingerprint(pub_bytes)
        recipient_keys[fp] = pub_bytes
        typer.echo(f"  Authorized player: {pub_path.name} ({fp[:16]}...)")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            compiler.compile_plain(manifest_path=manifest, output_path=tmp_path, version=version)
        except (ValueError, FileNotFoundError) as exc:
            typer.echo(f"Compilation failed: {exc}", err=True)
            raise typer.Exit(1) from exc
        embed_bundle_yaml(manifest, tmp_path)
        entries = sealed_entries(tmp_path)

    sealed_manifest = yaml.safe_load(entries[package_digest.MANIFEST_ENTRY])
    payload_b64, authorized_players = build_encrypted_payload(
        create_tar_bytes(entries), recipient_keys
    )
    redacted = build_redacted_manifest(
        sealed_manifest, compiler_identity.signing.fingerprint, authorized_players
    )
    manifest_bytes = yaml.dump(redacted, default_flow_style=False, sort_keys=False).encode()
    signature = sign_bytes(
        package_signing_message(manifest_bytes, payload_b64.encode()),
        compiler_identity.signing.private_bytes,
    )
    sig_b64 = base64.b64encode(signature).decode()
    return sealed_manifest, redacted, manifest_bytes, payload_b64, sig_b64


def compile_encrypted_plain(
    manifest: Path,
    compiler_keys: Path,
    player_pub: list[Path],
    out: Path,
    version: str | None,
    compiler: Compiler,
) -> None:
    """Compile into encrypted loose files (manifest.yaml + payload.enc + signature.sig)."""
    _, redacted, manifest_bytes, payload_b64, sig_b64 = _seal_and_encrypt(
        manifest, compiler_keys, player_pub, version, compiler
    )

    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.yaml").write_bytes(manifest_bytes)
    (out / "payload.enc").write_text(payload_b64, encoding="utf-8")
    (out / "signature.sig").write_text(sig_b64, encoding="utf-8")

    typer.echo(f"\nCompiled (encrypted plain) → {out}/manifest.yaml")
    typer.echo(f"                           → {out}/payload.enc")
    typer.echo(f"                           → {out}/signature.sig")
    typer.echo(f"  Checksum : {redacted['package']['checksum'][:32]}...")
    typer.echo(f"  Players  : {len(redacted['security']['authorized_players'])}")


def resolve_tck_output_path(
    manifest: Path,
    manifest_dict: dict,
    output: Path | None,
) -> Path:
    """Resolve the output .tck path from CLI options."""
    tck_id = manifest_dict["tck"]["id"]
    if output:
        if output.suffix == "" or output.is_dir():
            output.mkdir(parents=True, exist_ok=True)
            return output / f"{tck_id}.tck"
        return output if output.suffix == ".tck" else output.with_suffix(".tck")
    return manifest.parent / f"{tck_id}.tck"


def compile_encrypted_tck(
    manifest: Path,
    compiler_keys: Path,
    player_pub: list[Path],
    output: Path | None,
    version: str | None,
    compiler: Compiler,
) -> None:
    """Compile a TCK manifest into a .tck with AES-256-GCM encrypted payload.enc."""
    sealed_manifest, redacted, manifest_bytes, payload_b64, sig_b64 = _seal_and_encrypt(
        manifest, compiler_keys, player_pub, version, compiler
    )
    tck_path = resolve_tck_output_path(manifest, sealed_manifest, output)
    write_encrypted_tck(tck_path, manifest_bytes, payload_b64, sig_b64)

    typer.echo(f"\nCompiled (encrypted .tck) → {tck_path}")
    typer.echo(f"  Checksum : {redacted['package']['checksum'][:32]}...")
    typer.echo(f"  Signed by: {redacted['security']['compiler_id'][:32]}...")
    typer.echo(f"  Players  : {len(redacted['security']['authorized_players'])}")
