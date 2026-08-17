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

"""The engine must never report PASS for a run that did not earn it.

TestLab certifies connectors against Catena-X standards, so the one property it
cannot trade away is that a run which should fail, fails.  These are the tests
for that property, written against the two failures reproduced in the
architecture review: a TCK whose mistakes were absorbed in silence, and a
compiled package whose executed content sits outside its own integrity envelope.

Every test here asserts the *correct* behaviour and is marked ``xfail(strict)``
against the finding it belongs to.  When the fix lands the test XPASSes, strict
mode turns that into a build failure, and whoever fixed it removes the marker.
A finding therefore cannot be closed quietly, and cannot be re-opened quietly
either.

Cross-package by nature — validation, execution and packaging each participate —
so this sits at the ``tests/unit`` root rather than under one package, per the
layout rule in AGENTS.md.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
import yaml

from tractusx_testlab.compiler.compiler import Compiler

# ---------------------------------------------------------------------------
# Fixtures — a TCK that is valid today, so each test isolates one defect
# ---------------------------------------------------------------------------

#: The manifest fields the committed JSON Schema requires.  They are wider than
#: what the Pydantic model requires (F-B01); supplying all of them keeps these
#: tests measuring the defect under test rather than that disagreement.
_MANIFEST: dict = {
    "syntax": "v1-alpha",
    "kind": "tck",
    "id": "probe-tck",
    "metadata": {
        "name": "Probe TCK",
        "description": "Fixture for the false-positive regression tests.",
        "version": "1.0",
        "authors": [],
        "license": "Apache-2.0",
        "standards": [],
    },
    "env": {"variables": []},
    "tests": [{"id": "probe.yaml"}],
}


def _test_script(*steps: dict) -> dict:
    """A schema-valid test script wrapping *steps* as its execution phase."""
    return {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "probe",
        "namespace": "probe-tck",
        "metadata": {
            "name": "Probe test",
            "description": "Fixture.",
            "version": "1.0",
        },
        "execution": list(steps),
    }


def _write_tck(root: Path, *steps: dict) -> Path:
    """Write a TCK rooted at *root* whose single test runs *steps*.

    Returns the manifest path, which is what every entry point takes.
    """
    (root / "tests").mkdir(parents=True, exist_ok=True)
    manifest_path = root / "index.yaml"
    manifest_path.write_text(yaml.dump(_MANIFEST), encoding="utf-8")
    (root / "tests" / "probe.yaml").write_text(
        yaml.dump(_test_script(*steps)), encoding="utf-8"
    )
    return manifest_path


def _compile(manifest_path: Path, out_dir: Path) -> Path:
    """Compile *manifest_path* to a plain ``.tck`` and return the archive path.

    Goes through the CLI command rather than the compiler API because the
    archive layout — which is what F-A09 is about — is assembled in the command,
    not in ``Compiler``.
    """
    from tractusx_testlab.cli.compile import compile as compile_command

    compile_command(
        script=manifest_path,
        compiler_keys=None,
        player_pub=None,
        output=out_dir,
        version=None,
        plain=False,
        encrypt=False,
    )
    archives = list(out_dir.glob("*.tck"))
    assert len(archives) == 1, f"expected one .tck, got {archives}"
    return archives[0]


# ---------------------------------------------------------------------------
# F-A01 — a misspelled key must not be discarded
# ---------------------------------------------------------------------------


def test_validation_rejects_a_misspelled_step_key(tmp_path: Path) -> None:
    """``validte:`` is not ``validate:`` and must be reported, not ignored.

    This is the reproduction from the review.  The assertion the author wrote
    compares a fresh UUID against a literal that cannot match — it exists to
    fail.  Dropping the block turns a failing check into no check at all, and
    the run then certifies on the strength of an assertion that never ran.
    """
    manifest_path = _write_tck(
        tmp_path,
        {
            "id": "gen",
            "name": "Generate",
            "uses": "util/generate_uuid",
            "returns": {"value": {"type": "string"}},
            "validte": [  # ← the typo under test
                {
                    "uses": "validate/assert",
                    "with": {
                        "input": "value",
                        "operator": "equals",
                        "value": "never-matches",
                    },
                }
            ],
        },
    )

    result = Compiler().validate(manifest_path)

    assert not result.valid, (
        "A step carrying an unknown key 'validte' was accepted. The assertion "
        "the author wrote will never run, and the run will report PASS."
    )
    assert any(
        "validte" in issue.message for issue in result.issues
    ), f"Rejected, but without naming the offending key: {[i.message for i in result.issues]}"


def test_validation_rejects_an_unknown_key_on_a_step(tmp_path: Path) -> None:
    """A key that names no field of any model is an authoring mistake."""
    manifest_path = _write_tck(
        tmp_path,
        {
            "id": "logit",
            "name": "Log",
            "uses": "util/log",
            "with": {"message": "hello"},
            "unknown_key_here": 42,  # ← names no field of StepDefinition
        },
    )

    result = Compiler().validate(manifest_path)

    assert not result.valid, "A step carrying 'unknown_key_here' was accepted."


# ---------------------------------------------------------------------------
# F-A02 — an unresolved reference must not become its own literal text
# ---------------------------------------------------------------------------


async def test_an_unresolvable_reference_fails_the_run(tmp_path: Path) -> None:
    """``${{ env.does_not_exist }}`` must stop the run, not become a string.

    A URL built from an unresolved reference is requested verbatim; a BPN
    compared against one compares as text containing braces.  Either way the
    step runs against data nobody wrote, and reports on what it found there.
    """
    from tractusx_testlab.player.execution.player import TestlabPlayer

    manifest_path = _write_tck(
        tmp_path,
        {
            "id": "logit",
            "name": "Log",
            "uses": "util/log",
            "with": {"message": "hello ${{ env.does_not_exist }}"},
        },
    )

    player = TestlabPlayer()
    result = await player.run(manifest_path)

    assert result.status.value != "COMPLETED", (
        "A run referencing an undefined variable completed successfully. The "
        "step received the literal text '${{ env.does_not_exist }}' as its value."
    )


# ---------------------------------------------------------------------------
# F-A05 — an assertion must not silently weaken to not_null
# ---------------------------------------------------------------------------


def test_an_assertion_without_an_operator_is_rejected(tmp_path: Path) -> None:
    """Supplying ``value:`` with no ``operator:`` reads as a comparison.

    The engine instead checks the subject is not null and discards ``value``
    entirely, so a mis-authored equality check passes against any non-null
    result.  The author cannot tell from the YAML that this happened.
    """
    manifest_path = _write_tck(
        tmp_path,
        {
            "id": "gen",
            "name": "Generate",
            "uses": "util/generate_uuid",
            "returns": {"value": {"type": "string"}},
            "validate": [
                {
                    "uses": "validate/assert",
                    "with": {
                        "input": "value",
                        # no 'operator' — but a 'value' to compare against
                        "value": "never-matches",
                    },
                }
            ],
        },
    )

    result = Compiler().validate(manifest_path)

    assert not result.valid, (
        "An assertion supplying 'value' with no 'operator' was accepted. It "
        "will run as not_null and pass, ignoring the value entirely."
    )


# ---------------------------------------------------------------------------
# F-A06 — declared assertions must actually execute
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="F-A06: nothing compares declared assertions against executed ones, "
    "so a run that executed none still reports PASS.",
)
async def test_a_run_that_executed_no_declared_assertion_fails(tmp_path: Path) -> None:
    """Declared and executed assertion counts must agree.

    This is the hole every other finding in Theme A ultimately reaches the
    operator through.  It is deliberately *not* "a TCK with no assertions is
    invalid" — a provisioning-only TCK is legitimate.  The rule is narrower and
    unambiguous: a step that declared checks must have run them.
    """
    from tractusx_testlab.player.execution.player import TestlabPlayer

    manifest_path = _write_tck(
        tmp_path,
        {
            "id": "gen",
            "name": "Generate",
            "uses": "util/generate_uuid",
            "returns": {"value": {"type": "string"}},
            "validte": [  # dropped by F-A01, so nothing executes
                {"uses": "validate/assert", "with": {"input": "value"}}
            ],
        },
    )

    player = TestlabPlayer()
    result = await player.run(manifest_path)

    summary = result.scripts[0].assertion_summary
    assert summary is not None, "The script produced no assertion summary at all."
    assert summary.total > 0, (
        "The script declared an assertion and executed none, yet the run "
        f"reported {result.status.value}."
    )


# ---------------------------------------------------------------------------
# F-A09 — integrity verification must cover what is executed
# ---------------------------------------------------------------------------


def test_a_compiled_package_carries_one_executable_representation(
    tmp_path: Path,
) -> None:
    """Document what the archive contains today, so a change to it is visible.

    Not marked xfail: this is a characterisation test.  It records that the
    format ships the executed tests separately from the fingerprinted IR, which
    is the condition F-A09 depends on.  When P3 collapses the format to one
    artefact this test is what tells you the shape changed, and it should then
    be rewritten to assert the new single-representation layout.
    """
    manifest_path = _write_tck(
        tmp_path / "src",
        {"id": "gen", "name": "Generate", "uses": "util/generate_uuid"},
    )
    archive = _compile(manifest_path, tmp_path / "out")

    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())

    assert "manifest.yaml" in names
    assert "tck-execution.json" in names, "the fingerprinted IR"
    assert "tests/probe.yaml" in names, "the file the player actually executes"


def test_a_tampered_test_file_is_refused(tmp_path: Path) -> None:
    """Editing the executed test inside a compiled package must be detected.

    A TCK is a certification instrument that travels between organisations.  If
    a step can be appended to it in transit and still run, the signature and the
    checksum are certifying something other than what executes.
    """
    from tractusx_testlab.player.loading.loader import Loader

    manifest_path = _write_tck(
        tmp_path / "src",
        {"id": "gen", "name": "Generate", "uses": "util/generate_uuid"},
    )
    archive = _compile(manifest_path, tmp_path / "out")

    # Rewrite only the executed test; leave manifest.yaml and the IR untouched.
    with zipfile.ZipFile(archive) as zf:
        entries = {name: zf.read(name) for name in zf.namelist()}

    script = yaml.safe_load(entries["tests/probe.yaml"])
    script["execution"].append(
        {
            "id": "injected",
            "name": "Injected",
            "uses": "util/log",
            "with": {"message": "not authored, not signed"},
        }
    )
    entries["tests/probe.yaml"] = yaml.dump(script).encode("utf-8")

    tampered = tmp_path / "tampered.tck"
    with zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)

    with pytest.raises(ValueError, match=r"(?i)checksum|integrity|digest|tamper"):
        Loader().load(tampered)


def test_a_package_missing_its_digest_target_is_refused(tmp_path: Path) -> None:
    """Deleting the fingerprinted file must fail verification, not skip it.

    An integrity check that passes when its input is missing is worse than no
    check: it reports success, and the caller records the package as verified.
    """
    from tractusx_testlab.player.loading.loader import Loader

    manifest_path = _write_tck(
        tmp_path / "src",
        {"id": "gen", "name": "Generate", "uses": "util/generate_uuid"},
    )
    archive = _compile(manifest_path, tmp_path / "out")

    with zipfile.ZipFile(archive) as zf:
        entries = {
            name: zf.read(name)
            for name in zf.namelist()
            if name != "tck-execution.json"  # ← the file the digest covers
        }

    stripped = tmp_path / "stripped.tck"
    with zipfile.ZipFile(stripped, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)

    with pytest.raises(ValueError, match=r"(?i)checksum|integrity|digest|missing"):
        Loader().load(stripped)
