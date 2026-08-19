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

"""Everything a TCK declares survives compilation into ``tck-execution.json``.

The IR is the form the player is meant to execute — the YAML is the authoring
surface, the IR is what runs. That only holds if compiling is lossless: a field
the author writes and the compiler drops is a field the run silently ignores,
and the author has no way to tell.

These tests compare the compiled output against the *models*, not against a
hand-written list, so a field added to ``StepDefinition`` or ``ScriptDefinition``
without the builder learning to carry it fails here rather than going missing at
run time.

That failure mode is not hypothetical. Before these tests existed the IR dropped
``infrastructure`` (the required-capability check), ``dataspace_version`` (which
decides the connector dialect), ``if`` (conditional steps), ``expects`` (negative
tests) and ``timeout_s`` — five ways for a run to do something other than what
the TCK said.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from tractusx_testlab.compiler.ir._compilation import build_compiled_tests
from tractusx_testlab.compiler.ir._symbols import build_global_symbols
from tractusx_testlab.compiler.ir.builder import build_ir
from tractusx_testlab.models.authoring.definitions import (
    Assertion,
    ScriptDefinition,
    StepDefinition,
    TckTestEntry,
)

# ---------------------------------------------------------------------------
# Fixtures — a TCK that exercises every declarable field
# ---------------------------------------------------------------------------

#: Fields that describe the document rather than the run, and are therefore
#: carried by the manifest instead of the compiled test. ``namespace`` is among
#: them: it is required to equal the TCK id, which the manifest states, so it is
#: derivable rather than dropped.
_DOCUMENT_FIELDS = frozenset({"kind", "syntax", "metadata", "id", "namespace"})

#: Phase lists are flattened into one ``instructions`` array, each entry tagged
#: with the phase it came from. Nothing is lost — the shape changes.
_FLATTENED_INTO_INSTRUCTIONS = frozenset({"setup", "execution", "teardown"})


def _step_keys() -> set[str]:
    """The keys a step is written with in YAML.

    Field names and YAML keys are not the same set: ``with_`` is written
    ``with``, ``if_condition`` is written ``if``, and ``assertions`` is written
    ``validate`` — each because the YAML spelling is not a legal Python name or
    would shadow something on ``BaseModel``. Comparing against the aliases is
    comparing against what an author actually types.
    """
    return {
        field.validation_alias or field.alias or name
        for name, field in StepDefinition.model_fields.items()
    }


def _manifest() -> dict:
    return {
        "syntax": "v1-alpha",
        "kind": "tck",
        "id": "lossless-tck",
        "metadata": {
            "name": "Lossless",
            "description": "Every declarable field, once.",
            "version": "1.0",
            "authors": [],
            "license": "Apache-2.0",
            "standards": [],
        },
        "env": {
            "variables": [
                {
                    "id": "sut_bpn",
                    "uses": "variable/type/string",
                    "with": {"source": "value", "value": "BPNL000000000001"},
                }
            ],
            "schemas": [{"id": "cert_schema", "source": "cert.json"}],
            "testdata": [{"id": "body", "source": "body.json"}],
        },
        "tests": [{"id": "everything.yaml", "name": "Everything", "skippable": True}],
    }


def _script() -> dict:
    return {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "everything",
        "namespace": "lossless-tck",
        "metadata": {"name": "Everything", "description": "d", "version": "1.0"},
        "dataspace": {"ecosystem": "Catena-X", "version": "jupiter"},
        "infrastructure": {"sut": {"connector": {"required": True}}},
        "setup": [
            {
                "id": "seed",
                "name": "Seed",
                "uses": "util/generate_uuid",
                "returns": {"value": {"type": "string"}},
            }
        ],
        "execution": [
            {
                "id": "act",
                "name": "Act",
                "uses": "util/log",
                "with": {"message": "${{ env.sut_bpn }}"},
                "returns": {"value": {"type": "string"}},
                "if": "success()",
                "expects": "fail",
                "timeout_s": 30.0,
                "validate": [
                    {
                        "uses": "validate/assert/not_null",
                        "name": "the step produced a value",
                        "with": {"input": "value"},
                    }
                ],
            }
        ],
        "teardown": [
            {"id": "clean", "name": "Clean", "uses": "util/log", "with": {"message": "bye"}}
        ],
    }


def _compile(tmp_path) -> tuple[dict, list[dict]]:
    """Write the fixture TCK and return (global_symbols, compiled_tests)."""
    _write_tck(tmp_path)
    manifest = _manifest()
    return build_global_symbols(manifest["env"]), build_compiled_tests(manifest, tmp_path)


def _write_tck(tmp_path) -> Path:
    """Write the fixture TCK to disk and return the manifest path."""
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "everything.yaml").write_text(yaml.dump(_script()), encoding="utf-8")
    for asset in ("schemas/cert.json", "testdata/body.json"):
        path = tmp_path / asset
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "index.yaml"
    manifest_path.write_text(yaml.dump(_manifest()), encoding="utf-8")
    return manifest_path


def _compile_package(tmp_path) -> tuple[dict, dict]:
    """Compile the fixture into (manifest_dict, execution_dict)."""
    return build_ir(_write_tck(tmp_path))


# ---------------------------------------------------------------------------
# The fixture must itself be complete, or the tests below prove nothing
# ---------------------------------------------------------------------------


class TestTheFixtureIsComplete:
    """A losslessness test is only as good as the document it compiles."""

    def test_the_script_declares_every_script_field(self) -> None:
        declared = set(_script())
        missing = set(ScriptDefinition.model_fields) - declared
        assert not missing, (
            f"The fixture does not exercise {sorted(missing)}, so the tests below "
            f"cannot detect those being dropped. Add them to _script()."
        )

    def test_the_step_declares_every_step_field(self) -> None:
        step = _script()["execution"][0]
        missing = _step_keys() - set(step)
        assert not missing, (
            f"The fixture step does not exercise {sorted(missing)}. Add them to _script()."
        )

    def test_the_assertion_declares_every_assertion_field(self) -> None:
        assertion = _script()["execution"][0]["validate"][0]
        missing = {
            field.validation_alias or field.alias or name
            for name, field in Assertion.model_fields.items()
        } - set(assertion)
        assert not missing, (
            f"The fixture assertion does not exercise {sorted(missing)}. Add them to _script()."
        )

    def test_the_test_entry_declares_every_manifest_entry_field(self) -> None:
        entry = _manifest()["tests"][0]
        missing = set(TckTestEntry.model_fields) - set(entry)
        assert not missing, (
            f"The fixture test entry does not exercise {sorted(missing)}. Add them to _manifest()."
        )

    def test_the_fixture_is_a_valid_script(self) -> None:
        """It must be something the engine would actually accept."""
        ScriptDefinition.model_validate(_script())


# ---------------------------------------------------------------------------
# Losslessness
# ---------------------------------------------------------------------------


class TestEveryStepFieldSurvives:
    """A step's declared fields all reach the compiled instruction."""

    def test_no_step_field_is_dropped(self, tmp_path) -> None:
        _, compiled = _compile(tmp_path)
        instruction = next(i for i in compiled[0]["instructions"] if i["id"] == "act")

        dropped = {
            name
            for name in _step_keys()
            if name not in instruction and _script()["execution"][0].get(name) is not None
        }
        assert not dropped, (
            f"The compiler dropped {sorted(dropped)} from the compiled instruction. "
            f"A field the author wrote and the IR does not carry is a field the run "
            f"will ignore without saying so."
        )

    def test_the_values_survive_and_not_only_the_keys(self, tmp_path) -> None:
        """Carrying a key with the wrong value is not carrying it."""
        _, compiled = _compile(tmp_path)
        instruction = next(i for i in compiled[0]["instructions"] if i["id"] == "act")

        assert instruction.get("expects") == "fail"
        assert instruction.get("if") == "success()"
        assert instruction.get("timeout_s") == 30.0

    def test_an_assertion_keeps_the_name_the_author_gave_it(self, tmp_path) -> None:
        """It is what the report calls the check; dropped here it is gone for good."""
        _, compiled = _compile(tmp_path)
        instruction = next(i for i in compiled[0]["instructions"] if i["id"] == "act")
        assert instruction["validate"][0]["name"] == "the step produced a value"


class TestEveryScriptFieldSurvives:
    """A script's own declarations reach the compiled test."""

    def test_no_script_field_is_dropped(self, tmp_path) -> None:
        _, compiled = _compile(tmp_path)
        test = compiled[0]

        expected = (
            set(ScriptDefinition.model_fields) - _DOCUMENT_FIELDS - _FLATTENED_INTO_INSTRUCTIONS
        )
        dropped = expected - set(test)
        assert not dropped, (
            f"The compiler dropped {sorted(dropped)} from the compiled test. "
            f"`infrastructure` decides which capabilities the run demands and "
            f"`dataspace` decides the connector dialect — a run missing either "
            f"does something other than what the TCK asked for."
        )

    def test_every_phase_reaches_the_instructions(self, tmp_path) -> None:
        """Flattening is not dropping — each phase must still be identifiable."""
        _, compiled = _compile(tmp_path)
        phases = {i["phase"] for i in compiled[0]["instructions"]}
        assert phases == {"setup", "main", "teardown"}


class TestTheSymbolTableNamesThingsTheRuntimeUses:
    """Compiled symbol names must be the names a script actually writes."""

    def test_env_assets_are_named_by_id(self, tmp_path) -> None:
        """Not by the repr of the entry that declared them."""
        symbols, _ = _compile(tmp_path)
        assert "env.schemas.cert_schema" in symbols
        assert "env.testdata.body" in symbols

    def test_main_phase_outputs_use_the_execution_namespace(self, tmp_path) -> None:
        """``${{ execution.<id>.<field> }}`` is what TCKs and the IDE write."""
        _, compiled = _compile(tmp_path)
        table = compiled[0]["symbol_table"]
        assert "execution.act.value" in table
        assert not [key for key in table if key.startswith("steps.")]


class TestEveryManifestEntryFieldSurvives:
    """What the manifest says about a test reaches the compiled package.

    The compiled package is what an operator, a catalog or the IDE reads when
    the sources are not at hand. ``skippable`` decides whether the player will
    accept that test in ``skip_tests``, so a package that does not carry it
    cannot answer the one question a runner has to ask before offering the
    choice — and ``name`` is what the report calls the test.
    """

    def test_no_manifest_entry_field_is_dropped(self, tmp_path) -> None:
        _, execution = _compile_package(tmp_path)
        entry = execution["tests"][0]

        declared = _manifest()["tests"][0]
        # ``id`` is the file name in the manifest and the test document's own id
        # in the compiled entry, so the file name is carried as ``test_id`` —
        # the same string ``skip_tests`` names.
        dropped = {name for name in declared if name != "id" and name not in entry}
        assert not dropped, (
            f"The compiler dropped {sorted(dropped)} from the compiled test entry. "
            f"A package that cannot say which of its tests may be skipped leaves "
            f"every runner to guess, or to re-read the sources it was compiled from."
        )
        assert entry["test_id"] == "everything.yaml"

    def test_the_values_survive_and_not_only_the_keys(self, tmp_path) -> None:
        _, execution = _compile_package(tmp_path)
        entry = execution["tests"][0]

        assert entry["skippable"] is True
        assert entry["name"] == "Everything"

    def test_the_manifest_carries_the_same_entries(self, tmp_path) -> None:
        """``manifest.yaml`` is the section read without unpacking the IR."""
        manifest, execution = _compile_package(tmp_path)
        assert manifest["tests"] == execution["tests"]

    def test_a_test_no_one_marked_is_not_skippable(self, tmp_path) -> None:
        """The default travels too — silence means the test must run."""
        _write_tck(tmp_path)
        manifest_data = _manifest()
        manifest_data["tests"] = [{"id": "everything.yaml"}]
        manifest_path = tmp_path / "index.yaml"
        manifest_path.write_text(yaml.dump(manifest_data), encoding="utf-8")

        _, execution = build_ir(manifest_path)
        assert execution["tests"][0]["skippable"] is False
