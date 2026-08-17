################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Unit tests for Tck.inspect() and build_inspection_result()."""

from __future__ import annotations

import zipfile

import pytest
import yaml

from tractusx_testlab.compiler import package_digest
from tractusx_testlab.models.primitives.enums import StepPhase
from tractusx_testlab.models.runtime.inspection import TckInspectionResult
from tractusx_testlab.player.loading._parser import _SCRIPT_ADAPTER
from tractusx_testlab.player.loading.loader import _TCK_BUNDLE_ENTRY, Loader
from tractusx_testlab.scripting.script import Tck

_SINGLE_SCRIPT_YAML = """\
syntax: v1-alpha
kind: test
id: test-inspect-single
namespace: testlab.test
metadata:
  name: Single Script Test
  version: "1.0"
setup:
  - id: setup_step
    uses: util/generate_uuid
    name: Generate Asset ID
execution:
  - id: exec_step_one
    uses: connector/request_catalog
    name: Request Catalog
    validate:
      - uses: validate/assert/equals
        with: {input: status_code, value: 200}
      - uses: validate/assert/not_empty
        with: {input: datasets}
  - id: exec_step_two
    uses: http/http_request
    name: HTTP Call
teardown:
  - id: teardown_step
    uses: connector/provider/delete_asset
    name: Delete Asset
    validate:
      - uses: validate/assert/equals
        with: {input: status_code, value: 204}
"""

_TCK_WITH_TWO_SCRIPTS = """\
syntax: v1-alpha
kind: tck
id: tck-inspect
metadata:
  name: Multi-Script TCK
  version: "1.0"
tests:
  - id: script-a.yaml
    name: Script A
  - id: script-b.yaml
    name: Script B
"""

_SCRIPT_A_YAML = """\
syntax: v1-alpha
kind: test
id: script-a
namespace: testlab.test
metadata:
  name: Script A
  version: "1.0"
execution:
  - uses: util/generate_uuid
    name: Step One
"""

_SCRIPT_B_YAML = """\
syntax: v1-alpha
kind: test
id: script-b
namespace: testlab.test
metadata:
  name: Script B
  version: "1.0"
execution:
  - uses: http/http_request
    name: Step Two
  - uses: http/http_request
    name: Step Three
"""


@pytest.fixture()
def single_script_tck() -> object:
    """A Tck loaded from a single-script YAML with setup, execution, and teardown."""
    import yaml
    data = yaml.safe_load(_SINGLE_SCRIPT_YAML)
    script_def = _SCRIPT_ADAPTER.validate_python(data)
    from tractusx_testlab.scripting.script import Tck
    return Tck.from_single_script(script_def)


@pytest.fixture()
def multi_script_tck(tmp_path) -> object:
    """A Tck loaded from a TCK manifest with two scripts."""


    archive = tmp_path / "inspect.tck"
    sealed = package_digest.seal({
        "manifest.yaml": b"kind: manifest\n",
        _TCK_BUNDLE_ENTRY: _TCK_WITH_TWO_SCRIPTS.encode(),
        "tests/script-a.yaml": _SCRIPT_A_YAML.encode(),
        "tests/script-b.yaml": _SCRIPT_B_YAML.encode(),
    })
    with zipfile.ZipFile(archive, "w") as zf:
        for name in sorted(sealed):
            zf.writestr(name, sealed[name])

    return Loader().load(archive)


class TestTckInspectSingleScript:
    """Tests for Tck.inspect() on a single-script Tck."""

    def test_inspect_returns_correct_type(self, single_script_tck) -> None:
        result = single_script_tck.inspect()
        assert isinstance(result, TckInspectionResult)

    def test_inspect_name_matches_script(self, single_script_tck) -> None:
        result = single_script_tck.inspect()
        assert result.name == "Single Script Test"

    def test_inspect_counts_all_phases_in_total_steps(self, single_script_tck) -> None:
        # setup(1) + execution(2) + teardown(1) = 4
        result = single_script_tck.inspect()
        assert result.total_steps == 4

    def test_inspect_counts_validations_across_all_phases(self, single_script_tck) -> None:
        # exec_step_one(2) + teardown_step(1) = 3
        result = single_script_tck.inspect()
        assert result.total_validations == 3

    def test_inspect_extracts_correct_step_phases(self, single_script_tck) -> None:
        result = single_script_tck.inspect()
        steps = result.scripts[0].steps
        phases = [s.phase for s in steps]
        assert phases == [StepPhase.SETUP, StepPhase.EXECUTION, StepPhase.EXECUTION, StepPhase.TEARDOWN]

    def test_inspect_extracts_uses_identifier(self, single_script_tck) -> None:
        result = single_script_tck.inspect()
        steps = result.scripts[0].steps
        assert steps[0].uses == "util/generate_uuid"
        assert steps[1].uses == "connector/request_catalog"
        assert steps[3].uses == "connector/provider/delete_asset"

    def test_inspect_uses_name_field_when_present(self, single_script_tck) -> None:
        result = single_script_tck.inspect()
        steps = result.scripts[0].steps
        assert steps[0].step_name == "Generate Asset ID"
        assert steps[1].step_name == "Request Catalog"

    def test_inspect_falls_back_to_uses_when_name_absent(self) -> None:
        yaml_no_name = _SINGLE_SCRIPT_YAML.replace("    name: HTTP Call\n", "")
        data = yaml.safe_load(yaml_no_name)
        script_def = _SCRIPT_ADAPTER.validate_python(data)
        tck = Tck.from_single_script(script_def)
        result = tck.inspect()
        http_step = next(s for s in result.scripts[0].steps if s.uses == "http/http_request")
        assert http_step.step_name == "http/http_request"

    def test_inspect_per_step_validation_count(self, single_script_tck) -> None:
        result = single_script_tck.inspect()
        steps = {s.uses: s for s in result.scripts[0].steps}
        assert steps["util/generate_uuid"].validation_count == 0
        assert steps["connector/request_catalog"].validation_count == 2
        assert steps["http/http_request"].validation_count == 0
        assert steps["connector/provider/delete_asset"].validation_count == 1

    def test_inspect_result_is_frozen(self, single_script_tck) -> None:
        result = single_script_tck.inspect()
        with pytest.raises(Exception):
            result.name = "mutated"  # type: ignore[misc]


class TestTckInspectMultiScript:
    """Tests for Tck.inspect() on a multi-script TCK."""

    def test_inspect_aggregates_total_steps_across_scripts(self, multi_script_tck) -> None:
        # script-a(1) + script-b(2) = 3
        result = multi_script_tck.inspect()
        assert result.total_steps == 3

    def test_inspect_has_one_script_inspection_per_script(self, multi_script_tck) -> None:
        result = multi_script_tck.inspect()
        assert len(result.scripts) == 2

    def test_inspect_zero_validations_when_none_declared(self, multi_script_tck) -> None:
        result = multi_script_tck.inspect()
        assert result.total_validations == 0
