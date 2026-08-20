################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""A whole test document — the YAML an author exports — parsed, checked, run.

The other files here assemble steps as dicts, which skips the two things that
happen to a real TCK before it runs: the parser turning the document into
definitions, and the validator refusing it. A step chain can be perfectly wired
and still be rejected on the way in, or accepted and then not run.

So this is the same journey written as YAML: three phases, cross-phase
references, an inline assertion block, and every ``returns`` name checked
against what the step declares.
"""

from __future__ import annotations

import textwrap

import pytest
import yaml

from combinations.harness import Harness
from combinations.http_double import HttpDouble
from tractusx_testlab.compiler.validation.validator import ScriptValidator
from tractusx_testlab.scripting.parser import YamlParser

pytestmark = pytest.mark.asyncio


def _script(base_url: str) -> str:
    """A test document in the syntax an authored TCK is written in."""
    return textwrap.dedent(
        f"""
        syntax: v1-alpha
        kind: test
        id: combination-smoke
        namespace: combination-tck
        metadata:
          name: Combination smoke

        setup:
          - id: seed_id
            uses: util/generate_uuid
            returns:
              value:
                type: string

        execution:
          - id: register
            uses: http/http_request
            with:
              method: POST
              url: {base_url}/parts
              body:
                partner: "${{{{ setup.seed_id.value }}}}"
            returns:
              status_code:
                type: integer
              response_body:
                type: object
            validate:
              - uses: validate/assert/equals
                with:
                  input: status_code
                  value: 201
              - uses: validate/field/not_empty
                with:
                  input: response_body
                  path: id

          - id: part_id
            uses: util/json_path_extract
            with:
              input: "${{{{ execution.register.response_body }}}}"
              path: id
            returns:
              value:
                type: string

          - id: read_back
            uses: http/http_request
            with:
              method: GET
              url: "{base_url}/parts/${{{{ execution.part_id.value }}}}"
            returns:
              response_body:
                type: object
            validate:
              - uses: validate/field/equals
                with:
                  input: response_body
                  path: id
                  value: "${{{{ env.expected_part_id }}}}"

        teardown:
          - id: drop
            uses: http/http_request
            with:
              method: DELETE
              url: "{base_url}/parts/${{{{ execution.part_id.value }}}}"
            returns:
              status_code:
                type: integer
        """
    ).strip()


@pytest.fixture()
def parts_api(http: HttpDouble, harness: Harness) -> HttpDouble:
    """A tiny parts API that answers the document's four calls.

    ``expected_part_id`` stands in for a manifest variable: the read-back
    assertion compares against it, which is the only way to prove a
    ``${{ … }}`` reference inside a ``validate:`` block is resolved at all.
    """
    http.json_route("POST", "/parts", {"id": "part-1"}, status=201)
    http.json_route("GET", "/parts/part-1", {"id": "part-1", "partner": "any"})
    http.json_route("DELETE", "/parts/part-1", {"deleted": True}, status=200)
    harness.seed(expected_part_id="part-1")
    return http


class TestTheDocumentIsAccepted:
    """The parser and the validator, before anything runs."""

    async def test_the_document_parses(self, parts_api: HttpDouble) -> None:
        base = parts_api.start()
        script = YamlParser.parse_script_from_dict(yaml.safe_load(_script(base)))

        assert [step.id for step in script.execution] == [
            "register",
            "part_id",
            "read_back",
        ]
        assert [step.id for step in script.setup] == ["seed_id"]
        assert [step.id for step in script.teardown] == ["drop"]

    async def test_the_validator_reports_nothing(self, parts_api: HttpDouble) -> None:
        base = parts_api.start()
        script = YamlParser.parse_script_from_dict(yaml.safe_load(_script(base)))

        result = ScriptValidator().validate(script)

        assert result.valid, [i.message for i in result.issues if i.level == "error"]

    async def test_a_returns_name_the_step_does_not_publish_is_refused(
        self, parts_api: HttpDouble
    ) -> None:
        """The check that turns a typo into a compile error, on a real document."""
        base = parts_api.start()
        raw = yaml.safe_load(_script(base))
        raw["execution"][0]["returns"]["statuscode"] = {"type": "integer"}

        result = ScriptValidator().validate(YamlParser.parse_script_from_dict(raw))

        errors = [i.message for i in result.issues if i.level == "error"]
        assert any("statuscode" in message for message in errors)

    async def test_an_assertion_naming_no_known_check_is_refused(
        self, parts_api: HttpDouble
    ) -> None:
        base = parts_api.start()
        raw = yaml.safe_load(_script(base))
        raw["execution"][0]["validate"][0]["uses"] = "assert/status_code"

        result = ScriptValidator().validate(YamlParser.parse_script_from_dict(raw))

        errors = [i.message for i in result.issues if i.level == "error"]
        assert any("validate/assert" in message for message in errors)


class TestTheDocumentRuns:
    """Parsed definitions, run phase by phase, as the player runs them."""

    @staticmethod
    async def _run(harness: Harness, base: str) -> dict:
        script = YamlParser.parse_script_from_dict(yaml.safe_load(_script(base)))
        outcomes = {}
        for phase, steps in (
            ("setup", script.setup),
            ("execution", script.execution),
            ("teardown", script.teardown),
        ):
            outcomes[phase] = await harness.run(
                *[step.model_dump(by_alias=True, exclude_none=True) for step in steps],
                phase=phase,
            )
        return outcomes

    async def test_every_phase_passes(self, harness: Harness, parts_api: HttpDouble) -> None:
        base = parts_api.start()
        # The read-back asserts the partner it was registered with, so the
        # double has to answer with whatever the setup phase minted.
        outcomes = await self._run(harness, base)
        for phase, outcome in outcomes.items():
            assert outcome.passed, (
                phase,
                [(r.step_name, r.error, r.assertions) for r in outcome.failures],
            )

    async def test_the_setup_value_reaches_the_first_request(
        self, harness: Harness, parts_api: HttpDouble
    ) -> None:
        base = parts_api.start()
        outcomes = await self._run(harness, base)

        minted = outcomes["setup"].output("seed_id")
        assert parts_api.calls_to("POST", "/parts")[0].body == {"partner": minted}

    async def test_teardown_deletes_what_execution_created(
        self, harness: Harness, parts_api: HttpDouble
    ) -> None:
        base = parts_api.start()
        outcomes = await self._run(harness, base)

        assert parts_api.calls_to("DELETE", "/parts/part-1")
        assert outcomes["teardown"].variables["status_code"] == 200
