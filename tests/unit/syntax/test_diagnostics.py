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

"""What an author is told when a script does not hold up.

These are assertions about wording, which is unusual and deliberate: the message
*is* the feature. A regression here does not break a run — it quietly puts the
author back to counting list items in their own file to find out which of eight
identical-looking blocks the compiler meant.
"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from tractusx_testlab.models import ScriptDefinition
from tractusx_testlab.syntax import diagnostics
from tractusx_testlab.syntax.yaml_marks import line_index, nearest

_SCRIPT = """
kind: test
syntax: v1-alpha
id: example
namespace: example-tck
metadata:
  name: Example
execution:
  - id: pull_dtr
    uses: connector/consumer/pull_data_filtered
    with: {counter_party_address: "http://x"}
    returns:
      edr_token:
        type: string
    validate:
      - uses: validate/assert
        nmae: "an EDR token is obtained"
        with: {input: edr_token, operator: not_null}
"""


def _line_of(line: str) -> int:
    """The 1-based line *line* sits on in the script under test."""
    return _SCRIPT.splitlines().index(line) + 1


def _findings(text: str) -> list[diagnostics.Diagnostic]:
    data = yaml.safe_load(text)
    with pytest.raises(ValidationError) as caught:
        ScriptDefinition.model_validate(data)
    return diagnostics.explain(caught.value, model=ScriptDefinition, data=data, text=text)


class TestARejectedKey:
    """The case the whole module exists for: a key that is not in the contract."""

    @pytest.fixture
    def finding(self) -> diagnostics.Diagnostic:
        found = _findings(_SCRIPT)
        assert len(found) == 1
        return found[0]

    def test_the_step_is_named_not_counted(self, finding: diagnostics.Diagnostic) -> None:
        """``execution.1`` sent the author counting; the step has an id."""
        assert "execution[0] 'pull_dtr'" in finding.location

    def test_the_line_it_was_written_on_is_given(self, finding: diagnostics.Diagnostic) -> None:
        assert finding.line == _line_of('        nmae: "an EDR token is obtained"')

    def test_the_block_is_named_in_the_syntax_own_words(
        self, finding: diagnostics.Diagnostic
    ) -> None:
        assert finding.message == "'nmae' is not a key of an assertion"

    def test_the_keys_that_would_have_worked_are_listed(
        self, finding: diagnostics.Diagnostic
    ) -> None:
        assert finding.hint is not None
        assert "name, uses, with" in finding.hint

    def test_a_near_miss_is_named_as_the_likely_typo(self, finding: diagnostics.Diagnostic) -> None:
        assert finding.hint is not None
        assert "did you mean 'name'?" in finding.hint

    def test_nothing_of_pydantic_leaks_into_it(self, finding: diagnostics.Diagnostic) -> None:
        """The author has never heard of Pydantic and cannot act on its docs."""
        rendered = str(finding)
        assert "errors.pydantic.dev" not in rendered
        assert "Extra inputs are not permitted" not in rendered
        assert "type=extra_forbidden" not in rendered


class TestOtherFailures:
    def test_a_missing_required_key_names_the_block_it_belongs_to(self) -> None:
        found = _findings(_SCRIPT.replace("    uses: connector/consumer/pull_data_filtered\n", ""))
        assert str(found[0]).startswith(
            "execution[0] 'pull_dtr' → uses (line 9): required key 'uses' is missing from a step"
        )

    def test_a_value_outside_the_vocabulary_lists_the_vocabulary(self) -> None:
        found = _findings(_SCRIPT.replace("syntax: v1-alpha", "syntax: v2-alpha"))
        assert found[0].message == "'v2-alpha' is not allowed here — expected 'v1-alpha'"

    def test_an_id_that_breaks_the_naming_rule_shows_the_rule(self) -> None:
        found = _findings(_SCRIPT.replace("id: example\n", "id: Example\n"))
        assert "does not have the required form" in found[0].message

    def test_findings_come_out_in_file_order(self) -> None:
        """An author fixes a file downwards; Pydantic reports declared fields first."""
        broken = _SCRIPT.replace("syntax: v1-alpha", "syntax: v2-alpha").replace(
            "  - id: pull_dtr", "  - id: pull_dtr\n    unknown_step_key: 1"
        )
        lines = [finding.line for finding in _findings(broken)]
        assert lines == sorted(lines)

    def test_a_bulky_value_is_summarised_not_echoed_back(self) -> None:
        """The whole `validate:` list used to be printed back at the author."""
        found = _findings(_SCRIPT.replace("    validate:", "    timeout_s:"))
        assert "a list" in found[0].message
        assert len(str(found[0])) < 200


class TestADocumentThatDoesNotParse:
    """The worst of the old renderings: 29 KB of our own call stack."""

    @pytest.fixture
    def finding(self, tmp_path) -> diagnostics.Diagnostic:
        path = tmp_path / "broken.yaml"
        path.write_text("tests:\n  - id: a.yaml\n   - id: b.yaml\n", encoding="utf-8")
        with pytest.raises(yaml.YAMLError) as caught:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        return diagnostics.unparseable(caught.value, path)

    def test_the_file_and_the_position_are_given(self, finding: diagnostics.Diagnostic) -> None:
        assert finding.location == "broken.yaml (line 3, column 4)"

    def test_the_parser_own_complaint_survives(self, finding: diagnostics.Diagnostic) -> None:
        assert "not valid YAML" in finding.message
        assert "expected <block end>" in finding.message

    def test_it_stays_short_enough_to_read(self, finding: diagnostics.Diagnostic) -> None:
        assert len(str(finding)) < 200
        assert "Traceback" not in str(finding)


class TestAnAssertionMayBeNamed:
    def test_a_named_assertion_is_accepted(self) -> None:
        """Optional, and report-only — the check itself is `uses` and `with`."""
        named = _SCRIPT.replace("        nmae:", "        name:")
        script = ScriptDefinition.model_validate(yaml.safe_load(named))
        assert script.execution[0].assertions is not None
        assert script.execution[0].assertions[0].name == "an EDR token is obtained"

    def test_an_unnamed_assertion_is_still_accepted(self) -> None:
        without = _SCRIPT.replace('        nmae: "an EDR token is obtained"\n', "")
        script = ScriptDefinition.model_validate(yaml.safe_load(without))
        assert script.execution[0].assertions is not None
        assert script.execution[0].assertions[0].name is None


class TestLineIndex:
    def test_a_key_is_indexed_at_its_own_line_not_its_value_block(self) -> None:
        index = line_index(_SCRIPT)
        assert index[("execution", 0, "validate")] == _line_of("    validate:")
        assert index[("execution", 0, "id")] == _line_of("  - id: pull_dtr")

    def test_an_unparseable_document_yields_no_positions(self) -> None:
        assert line_index("a: [1, 2\nb: }") == {}

    def test_a_path_with_no_line_falls_back_to_its_container(self) -> None:
        index = line_index(_SCRIPT)
        assert nearest(index, ("execution", 0, "never_written")) == index[("execution", 0)]
