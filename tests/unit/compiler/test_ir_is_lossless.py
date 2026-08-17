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

import yaml

from tractusx_testlab.compiler.ir._compilation import build_compiled_tests
from tractusx_testlab.compiler.ir._symbols import build_global_symbols
from tractusx_testlab.models.authoring.definitions import (
    ScriptDefinition,
    StepDefinition,
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
        "tests": [{"id": "everything.yaml"}],
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
            {"id": "seed", "name": "Seed", "uses": "util/generate_uuid",
             "returns": {"value": {"type": "string"}}}
        ],
        "execution": [
            {
                "id": "act",
                "name": "Act",
                "uses": "util/log",
                "with": {"message": "${{ env.sut_bpn.value }}"},
                "returns": {"value": {"type": "string"}},
                "if": "success()",
                "expects": "fail",
                "timeout_s": 30.0,
                "validate": [
                    {"uses": "validate/assert/not_null", "with": {"input": "value"}}
                ],
            }
        ],
        "teardown": [
            {"id": "clean", "name": "Clean", "uses": "util/log", "with": {"message": "bye"}}
        ],
    }


def _compile(tmp_path) -> tuple[dict, list[dict]]:
    """Write the fixture TCK and return (global_symbols, compiled_tests)."""
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "everything.yaml").write_text(
        yaml.dump(_script()), encoding="utf-8"
    )
    manifest = _manifest()
    return build_global_symbols(manifest["env"]), build_compiled_tests(manifest, tmp_path)


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
        aliased = {
            field.alias or name for name, field in StepDefinition.model_fields.items()
        }
        missing = aliased - set(step)
        assert not missing, (
            f"The fixture step does not exercise {sorted(missing)}. Add them to _script()."
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
        instruction = next(
            i for i in compiled[0]["instructions"] if i["id"] == "act"
        )

        aliased = {
            field.alias or name for name, field in StepDefinition.model_fields.items()
        }
        dropped = {
            name for name in aliased
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


class TestEveryScriptFieldSurvives:
    """A script's own declarations reach the compiled test."""

    def test_no_script_field_is_dropped(self, tmp_path) -> None:
        _, compiled = _compile(tmp_path)
        test = compiled[0]

        expected = (
            set(ScriptDefinition.model_fields)
            - _DOCUMENT_FIELDS
            - _FLATTENED_INTO_INSTRUCTIONS
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
