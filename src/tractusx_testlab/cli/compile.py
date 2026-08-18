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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""The ``testlab compile`` command — YAML in, a ``.tck`` package out."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import typer

from tractusx_testlab.cli import app
from tractusx_testlab.compiler import package_digest

# Archive entry name for the bundled authoring YAML
TCK_BUNDLE_ENTRY = "tck-bundle.yaml"


def _create_tck_archive(source_dir: Path, archive_path: Path) -> str:
    """Create a ``.tck`` ZIP from *source_dir*, sealing it with a digest of itself.

    The digest is stamped here rather than in the IR builder because here is
    where the archive's contents finally exist. The builder ran before the test
    files were copied in, so its digest covered a subset of the package and the
    executed files sat outside it.

    Returns the checksum the archive carries, so the caller reports the number
    the package actually holds. ``compile`` used to echo the builder's
    pre-sealing checksum, which no longer matched anything once the archive was
    sealed — ``testlab inspect --manifest`` on the file just written showed a
    different digest than the compile that wrote it.
    """
    import yaml

    entries = {
        path.relative_to(source_dir).as_posix(): path.read_bytes()
        for path in sorted(source_dir.rglob("*"))
        if path.is_file()
    }

    if package_digest.MANIFEST_ENTRY in entries:
        entries = package_digest.seal(entries)

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(entries):
            zf.writestr(name, entries[name])

    sealed = yaml.safe_load(entries[package_digest.MANIFEST_ENTRY])
    return str(sealed.get("package", {}).get("checksum", ""))


def _embed_bundle_yaml(manifest_path: Path, output_dir: Path) -> None:
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


@app.command()
def compile(
    script: Path = typer.Argument(..., help="Path to the YAML test script to compile."),
    compiler_keys: Path | None = typer.Option(
        None, "--compiler-keys", "-c",
        help="Directory containing the compiler identity (signing.pem, encryption.*).",
    ),
    player_pub: list[Path] | None = typer.Option(
        None, "--player-pub", "-p",
        help="Path(s) to player RSA public key(s) (encryption.pub). Can be repeated.",
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Output path. Directory for --plain, .tck file otherwise.",
    ),
    version: str | None = typer.Option(
        None, "--version", "-v",
        help="Connector version for version-specific validation.",
    ),
    plain: bool = typer.Option(
        False, "--plain",
        help="Write loose files to a directory instead of a .tck archive.",
    ),
) -> None:
    """Compile a YAML test script into a ``.tck`` package.

    Two independent choices, and no third way to spell either:

    * ``--plain`` writes loose files to a directory; without it, one ``.tck``.
    * Supplying **both** ``--compiler-keys`` and ``--player-pub`` signs and
      encrypts the result; supplying neither leaves it readable.

    There used to be a separate ``--encrypt`` flag that wrote a ``.stck``, so
    the same stated intent produced two different formats depending on which
    spelling the caller reached for. ``.tck`` is the distribution and execution
    format; it is now the only one.
    """
    from tractusx_testlab.compiler.compiler import Compiler

    if bool(compiler_keys) != bool(player_pub):
        missing = "--player-pub" if compiler_keys else "--compiler-keys"
        typer.echo(
            f"Error: {missing} is required to encrypt a package. Supply both "
            f"--compiler-keys and --player-pub, or neither.",
            err=True,
        )
        raise typer.Exit(1)

    compiler = Compiler()

    if plain:
        out = output or script.parent / "plain"
        if compiler_keys and player_pub:
            _compile_encrypted_plain(script, compiler_keys, player_pub, out, version, compiler)
        else:
            try:
                manifest_dict, _ = compiler.compile_plain(manifest_path=script, output_path=out, version=version)
            except (ValueError, FileNotFoundError) as exc:
                typer.echo(f"Compilation failed: {exc}", err=True)
                raise typer.Exit(1) from exc
            typer.echo(f"\nCompiled (plain) → {out}/manifest.yaml")
            typer.echo(f"                 → {out}/tck-execution.json")
            typer.echo(f"                 → {out}/assets/")
            typer.echo("")
            typer.echo(f"  Package checksum : {manifest_dict['package']['checksum']}")
            typer.echo(f"  Fingerprint digest: {manifest_dict['compilation']['fingerprint']['digest']}")
        return

    # Both keys, or neither — checked above.
    if compiler_keys and player_pub:
        _compile_encrypted_tck(script, compiler_keys, player_pub, output, version, compiler)
        return

    # Default: unencrypted .tck ZIP archive
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            manifest_dict, _ = compiler.compile_plain(manifest_path=script, output_path=tmp_path, version=version)
        except (ValueError, FileNotFoundError) as exc:
            typer.echo(f"Compilation failed: {exc}", err=True)
            raise typer.Exit(1) from exc

        _embed_bundle_yaml(script, tmp_path)

        tck_id = manifest_dict["tck"]["id"]
        if output:
            if output.suffix == "" or output.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                tck_path = output / f"{tck_id}.tck"
            else:
                tck_path = output if output.suffix == ".tck" else output.with_suffix(".tck")
        else:
            tck_path = script.parent / f"{tck_id}.tck"
        tck_path.parent.mkdir(parents=True, exist_ok=True)
        checksum = _create_tck_archive(tmp_path, tck_path)

    typer.echo(f"\nCompiled → {tck_path}")
    typer.echo(f"  Package checksum : {checksum}")
    typer.echo(f"  Fingerprint digest: {manifest_dict['compilation']['fingerprint']['digest']}")


def _compile_encrypted_plain(
    script: Path,
    compiler_keys: Path,
    player_pub: list[Path],
    out: Path,
    version: str | None,
    compiler: object,
) -> None:
    """Compile into encrypted loose files (manifest.yaml + payload.enc + signature.sig)."""
    import base64
    import tempfile

    import yaml as _yaml

    from tractusx_testlab.cli._tck_packager import (
        build_encrypted_payload,
        build_redacted_manifest,
        create_tar_bytes,
    )
    from tractusx_testlab.security.crypto.keygen import _fingerprint
    from tractusx_testlab.security.crypto.signing import sign_bytes
    from tractusx_testlab.security.trust.identity import PlayerIdentity

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
            manifest_dict, _ = compiler.compile_plain(
                manifest_path=script, output_path=tmp_path, version=version,
            )
        except (ValueError, FileNotFoundError) as exc:
            typer.echo(f"Compilation failed: {exc}", err=True)
            raise typer.Exit(1) from exc
        _embed_bundle_yaml(script, tmp_path)
        tar_bytes = create_tar_bytes(tmp_path)

    signature = sign_bytes(tar_bytes, compiler_identity.signing.private_bytes)
    sig_b64 = base64.b64encode(signature).decode()
    payload_b64, authorized_players = build_encrypted_payload(tar_bytes, recipient_keys)
    redacted = build_redacted_manifest(
        manifest_dict, compiler_identity.signing.fingerprint, authorized_players, sig_b64,
    )

    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.yaml").write_text(
        _yaml.dump(redacted, default_flow_style=False, sort_keys=False), encoding="utf-8",
    )
    (out / "payload.enc").write_text(payload_b64, encoding="utf-8")
    (out / "signature.sig").write_text(sig_b64, encoding="utf-8")

    typer.echo(f"\nCompiled (encrypted plain) → {out}/manifest.yaml")
    typer.echo(f"                           → {out}/payload.enc")
    typer.echo(f"                           → {out}/signature.sig")
    typer.echo(f"  Checksum : {redacted['package']['checksum'][:32]}...")
    typer.echo(f"  Players  : {len(authorized_players)}")


def _resolve_tck_output_path(
    script: Path,
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
    return script.parent / f"{tck_id}.tck"


def _compile_encrypted_tck(
    script: Path,
    compiler_keys: Path,
    player_pub: list[Path],
    output: Path | None,
    version: str | None,
    compiler: object,
) -> None:
    """Compile a TCK manifest into a .tck with AES-256-GCM encrypted payload.enc."""
    import base64
    import tempfile

    from tractusx_testlab.cli._tck_packager import (
        build_encrypted_payload,
        build_redacted_manifest,
        create_tar_bytes,
        write_encrypted_tck,
    )
    from tractusx_testlab.security.crypto.keygen import _fingerprint
    from tractusx_testlab.security.crypto.signing import sign_bytes
    from tractusx_testlab.security.trust.identity import PlayerIdentity

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
            manifest_dict, _ = compiler.compile_plain(
                manifest_path=script, output_path=tmp_path, version=version,
            )
        except (ValueError, FileNotFoundError) as exc:
            typer.echo(f"Compilation failed: {exc}", err=True)
            raise typer.Exit(1) from exc
        _embed_bundle_yaml(script, tmp_path)
        tar_bytes = create_tar_bytes(tmp_path)

    signature = sign_bytes(tar_bytes, compiler_identity.signing.private_bytes)
    sig_b64 = base64.b64encode(signature).decode()
    payload_b64, authorized_players = build_encrypted_payload(tar_bytes, recipient_keys)
    redacted = build_redacted_manifest(
        manifest_dict, compiler_identity.signing.fingerprint, authorized_players, sig_b64,
    )
    tck_path = _resolve_tck_output_path(script, manifest_dict, output)
    write_encrypted_tck(tck_path, redacted, payload_b64, sig_b64)

    typer.echo(f"\nCompiled (encrypted .tck) → {tck_path}")
    typer.echo(f"  Checksum : {redacted['package']['checksum'][:32]}...")
    typer.echo(f"  Signed by: {compiler_identity.signing.fingerprint[:32]}...")
    typer.echo(f"  Players  : {len(authorized_players)}")
