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

"""The ``testlab inspect`` command — everything you can learn without running.

There used to be three commands here. ``compile info`` printed the manifest,
``compile decompile`` wrote the payload back out, and ``inspect`` reported the
tests — three verbs for one question ("what is in this package?"), each
accepting a different subset of the options and each having to grow its own
copy of the decrypt-and-verify dance. They are sections of one command now.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from tractusx_testlab.cli import app
from tractusx_testlab.cli._inspect_report import (
    print_infrastructure,
    print_inspection,
    print_manifest,
    print_variables,
)


@app.command()
def inspect(
    package: Path = typer.Argument(..., help="Path to a .tck package."),
    player_keys: Path | None = typer.Option(
        None, "--player-keys", "-k",
        help="Directory with the player identity (encryption.pem). Required if encrypted.",
    ),
    compiler_pub: Path | None = typer.Option(
        None, "--compiler-pub", "-c",
        help="The compiler's signing public key (signing.pub). Required if encrypted.",
    ),
    show_variables: bool = typer.Option(
        False, "--variables",
        help="Show declared variables with their source and scope.",
    ),
    show_infrastructure: bool = typer.Option(
        False, "--infrastructure",
        help="Show infrastructure capability requirements (engine and SUT sides).",
    ),
    show_manifest: bool = typer.Option(
        False, "--manifest",
        help="Show the package manifest: identity, checksum, signer, players.",
    ),
    extract: Path | None = typer.Option(
        None, "--extract",
        help="Write the package's verified contents to this directory.",
    ),
    as_json: bool = typer.Option(
        False, "--json",
        help="Output as JSON. Combines all requested sections into one object.",
    ),
) -> None:
    """Report what a ``.tck`` package contains, without executing it.

    The package is verified first — checksum, and signature where the package
    carries one — so every section below describes a package that has been
    shown to be the one its compiler built. Reporting on unverified contents
    would make this command a way to read a tampered package's own account of
    itself.
    """
    if not package.exists():
        typer.echo(f"Error: package not found: {package}", err=True)
        raise typer.Exit(1)

    try:
        tck, verified_dir = _load_tck(package, player_keys, compiler_pub)
    except ValueError as exc:
        typer.echo(f"\nRefused to inspect {package.name}:\n  {exc}", err=True)
        raise typer.Exit(1) from exc

    # Extraction writes files and reports what it wrote; every other section
    # reports. Done first so `--extract --json` still emits exactly one object.
    if extract is not None:
        _extract_package(package, verified_dir, extract, quiet=as_json)

    sections = _gather(tck, verified_dir, show_variables, show_infrastructure, show_manifest)

    if as_json:
        typer.echo(json.dumps(sections, indent=2, default=_jsonable))
        return

    print_inspection(package, sections["inspection"])
    if show_variables:
        print_variables(tck)
    if show_infrastructure:
        print_infrastructure(tck)
    if show_manifest:
        print_manifest(sections["manifest"])


def _load_tck(
    package: Path,
    player_keys: Path | None,
    compiler_pub: Path | None,
) -> tuple[object, Path]:
    """Load and verify a package, returning it and the verified bytes on disk.

    The keys are passed whenever they were given; the loader refuses an
    encrypted package that arrives without them, and refuses a signed one whose
    signature it was given no key to check. Every section of this command reads
    the directory the loader wrote *after* those checks, never the archive — so
    there is no path here that reports on bytes nothing verified.
    """
    from tractusx_testlab.player.loading.loader import Loader

    priv = pub = None
    if player_keys is not None:
        from tractusx_testlab.security.crypto.keygen import load_private_key

        priv = load_private_key(player_keys / "encryption.pem")
    if compiler_pub is not None:
        from tractusx_testlab.security.crypto.keygen import load_public_key

        pub = load_public_key(compiler_pub)

    tck = Loader().load(package, player_private_key=priv, compiler_public_key=pub)
    return tck, Path(tck.base_dir)


def _jsonable(value: object) -> object:
    """Serialize the models :func:`_gather` collects.

    Every section is one object under its own key, whichever flags were passed.
    ``--json`` used to emit the bare inspection result when no section flag was
    given and an envelope when one was, so a consumer had to know the argv to
    know the shape.
    """
    from pydantic import BaseModel

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return str(value)


def _gather(
    tck: object,
    verified_dir: Path,
    show_variables: bool,
    show_infrastructure: bool,
    show_manifest: bool,
) -> dict:
    """Collect the requested sections once, for either output format.

    One reader for both renderings: the JSON a machine consumes and the table a
    person reads describe the same package, because they are the same data.
    """
    sections: dict = {"inspection": tck.inspect()}  # type: ignore[attr-defined]
    if show_variables:
        sections["variables"] = {
            name: {
                "type": var.type,
                "source": var.source.value,
                "scope": var.scope.value if var.scope else None,
                "default": var.default,
                "description": var.description,
            }
            for name, var in tck.all_variables().items()  # type: ignore[attr-defined]
        }
    if show_infrastructure:
        sections["infrastructure"] = tck.infrastructure_requirements()  # type: ignore[attr-defined]
    if show_manifest:
        sections["manifest"] = _read_manifest(verified_dir)
    return sections


def _read_manifest(verified_dir: Path) -> dict:
    """Read the manifest out of the verified contents."""
    import yaml

    manifest_file = verified_dir / "manifest.yaml"
    if not manifest_file.exists():
        typer.echo("Error: package carries no manifest.yaml.", err=True)
        raise typer.Exit(1)
    return yaml.safe_load(manifest_file.read_text(encoding="utf-8"))


def _extract_package(
    package: Path, verified_dir: Path, destination: Path, quiet: bool = False
) -> None:
    """Write the verified package contents out — what ``compile decompile`` did.

    ``decompile`` wrote back only the authoring YAML, and only for encrypted
    packages. A package is its tests, its assets and its compiled instructions
    too, so all of it is written, and a plain package extracts the same way.
    """
    import shutil

    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(verified_dir, destination, dirs_exist_ok=True)
    if quiet:
        return

    written = sorted(
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    )
    typer.echo(f"\nExtracted {package.name} -> {destination}/")
    for name in written:
        typer.echo(f"  {name}")
    typer.echo()
