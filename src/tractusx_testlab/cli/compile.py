#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""CLI commands for compiling, decompiling, and inspecting .tck archives."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

import typer

from tractusx_testlab.cli import app
from tractusx_testlab.compiler import package_digest

# Archive entry name for the bundled authoring YAML
TCK_BUNDLE_ENTRY = "tck-bundle.yaml"


def _create_tck_archive(source_dir: Path, archive_path: Path) -> None:
    """Create a ``.tck`` ZIP from *source_dir*, sealing it with a digest of itself.

    The digest is stamped here rather than in the IR builder because here is
    where the archive's contents finally exist. The builder ran before the test
    files were copied in, so its digest covered a subset of the package and the
    executed files sat outside it.
    """
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
        help="Output loose files to a directory (no ZIP). With --compiler-keys/--player-pub outputs encrypted loose files.",
    ),
    encrypt: bool = typer.Option(
        False, "--encrypt",
        help="Encrypt the .tck package. Requires --compiler-keys and --player-pub.",
    ),
) -> None:
    """Compile a YAML test script into a .tck archive."""
    from tractusx_testlab.compiler.compiler import Compiler

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

    if encrypt:
        # Encrypted mode requires keys
        if not compiler_keys:
            typer.echo("Error: --compiler-keys is required for encrypted compilation.", err=True)
            raise typer.Exit(1)
        if not player_pub:
            typer.echo("Error: --player-pub is required for encrypted compilation.", err=True)
            raise typer.Exit(1)

        _compile_encrypted(script, compiler_keys, player_pub, output, version, compiler)
        return

    # Auto-encrypt when both compiler and player keys are provided
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
        _create_tck_archive(tmp_path, tck_path)

    typer.echo(f"\nCompiled → {tck_path}")
    typer.echo(f"  Package checksum : {manifest_dict['package']['checksum']}")
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


def _compile_encrypted(
    script: Path,
    compiler_keys: Path,
    player_pub: list[Path],
    output: Path | None,
    version: str | None,
    compiler: object,
) -> None:
    """Run encrypted .stck compilation with signing and encryption."""
    from tractusx_testlab.security.crypto.keygen import _fingerprint
    from tractusx_testlab.security.trust.identity import PlayerIdentity

    # Load compiler identity
    compiler_identity = PlayerIdentity.load(compiler_keys)

    # Load recipient public keys
    recipient_keys: dict[str, bytes] = {}
    for pub_path in player_pub:
        pub_bytes = pub_path.read_bytes()
        fingerprint = _fingerprint(pub_bytes)
        recipient_keys[fingerprint] = pub_bytes
        typer.echo(f"  Authorized player: {pub_path.name} ({fingerprint[:16]}...)")

    out = output or script.with_suffix(".stck")

    # Detect whether input is a TCK manifest or a single test
    import yaml as _yaml

    from tractusx_testlab.models.primitives.enums import ScriptKind
    from tractusx_testlab.player.loading.loader import _detect_kind
    with open(script, encoding="utf-8") as script_handle:
        raw = _yaml.safe_load(script_handle)
    is_tck = isinstance(raw, dict) and _detect_kind(raw) == ScriptKind.TCK

    try:
        if is_tck:
            manifest, validation = compiler.compile_tck(
                manifest_path=script,
                compiler_identity=compiler_identity,
                recipient_keys=recipient_keys,
                output_path=out,
                version=version,
            )
        else:
            manifest, validation = compiler.compile(
                script_path=script,
                compiler_identity=compiler_identity,
                recipient_keys=recipient_keys,
                output_path=out,
                version=version,
            )
    except (ValueError, FileNotFoundError) as exc:
        typer.echo(f"Compilation failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"\nCompiled (encrypted) → {out}")
    typer.echo(f"  Checksum : {manifest.checksum[:32]}...")
    typer.echo(f"  Signed by: {manifest.security.compiler_id[:32]}...")
    typer.echo(f"  Players  : {len(manifest.security.authorized_players)}")

    if validation.issues:
        for issue in validation.issues:
            prefix = "WARN " if issue.level == "warning" else "ERROR"
            typer.echo(f"  [{prefix}] {issue.message}")


@app.command()
def info(
    package: Path = typer.Argument(..., help="Path to a .tck archive."),
) -> None:
    """Display the manifest of a compiled .tck package."""
    from tractusx_testlab.compiler.packager import Packager

    manifest = Packager.read_manifest(package)
    typer.echo(json.dumps(json.loads(manifest.model_dump_json()), indent=2))


@app.command()
def decompile(
    package: Path = typer.Argument(..., help="Path to the .tck archive to decompile."),
    player_keys: Path = typer.Option(
        ..., "--player-keys", "-k",
        help="Directory containing the player identity (encryption.pem).",
    ),
    compiler_pub: Path = typer.Option(
        ..., "--compiler-pub", "-c",
        help="Path to the compiler's signing public key (signing.pub).",
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Output path for the decrypted YAML. Defaults to <package_name>.yaml.",
    ),
    stdout: bool = typer.Option(
        False, "--stdout",
        help="Print decrypted YAML to stdout instead of writing a file.",
    ),
) -> None:
    """Decrypt and verify an encrypted .stck, extracting the original YAML."""
    from tractusx_testlab.compiler.packager import Packager
    from tractusx_testlab.security.crypto.keygen import load_private_key, load_public_key

    priv_key_path = player_keys / "encryption.pem"
    if not priv_key_path.exists():
        typer.echo(f"Error: player private key not found: {priv_key_path}", err=True)
        raise typer.Exit(1)

    if not compiler_pub.exists():
        typer.echo(f"Error: compiler public key not found: {compiler_pub}", err=True)
        raise typer.Exit(1)

    priv_key = load_private_key(priv_key_path)
    pub_key = load_public_key(compiler_pub)

    try:
        plaintext = Packager.extract_and_verify(package, priv_key, pub_key)
    except ValueError as exc:
        typer.echo(f"Decompilation failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    if stdout:
        typer.echo(plaintext.decode("utf-8"))
    else:
        out_path = output or package.with_suffix(".yaml")
        out_path.write_bytes(plaintext)
        manifest = Packager.read_manifest(package)
        typer.echo(f"Decompiled → {out_path}")
        typer.echo(f"  Package  : {manifest.name} v{manifest.version}")
        typer.echo(f"  Checksum : {manifest.checksum[:32]}...")
        typer.echo("  Verified : signature OK")
