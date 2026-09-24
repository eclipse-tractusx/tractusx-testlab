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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""An experimental extension is in effect only for a TCK that enables it.

The models accept every extension's keys, so the IDE schema can describe them;
these pin that the compiler refuses them anywhere they were not asked for, says
how to ask, and warns everyone who did.
"""

from __future__ import annotations

import inspect

import pytest
import yaml
from pydantic import ValidationError

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.compiler.validation.validator import TestValidator
from tractusx_testlab.extensions import EXTENSIONS
from tractusx_testlab.models import TckDefinition

_CAC = ["CX-0135:v3.1.0:CAC-014"]


def _issues(tmp_path, step: dict, extensions: list[str], **test_keys) -> list:
    manifest = {
        "syntax": "v1-alpha",
        "kind": "tck",
        "id": "gate-tck",
        "metadata": {"name": "Gate", "standards": [{"id": "CX-0135", "version": "v3.1.0"}]},
        "extensions": extensions,
        "tests": [{"id": "t.yaml"}],
    }
    test = {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "t",
        "namespace": "gate-tck",
        "metadata": {"name": "t"},
        "execution": [step],
        **test_keys,
    }
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.yaml").write_text(yaml.dump(test), encoding="utf-8")
    return TestValidator().validate_tck(TckDefinition.model_validate(manifest), tmp_path).issues


def _log(**extra) -> dict:
    return {"id": "act", "name": "Act", "uses": "util/log", "with": {"message": "hi"}, **extra}


class TestAKeyNeedsItsExtension:
    def test_a_step_key_is_refused_without_it(self, tmp_path) -> None:
        (error,) = [i for i in _issues(tmp_path, _log(cac=_CAC), []) if i.level == "error"]
        assert "experimental extension 'cac'" in error.message
        assert "extensions: [cac]" in error.message
        assert error.field == "cac"

    def test_a_test_key_is_refused_without_it(self, tmp_path) -> None:
        issues = _issues(tmp_path, _log(), [], cac=_CAC)
        (error,) = [i for i in issues if i.level == "error"]
        assert "'cac:' on the test" in error.message
        assert "experimental extension 'cac'" in error.message
        assert "extensions: [cac]" in error.message
        assert error.field == "cac"
        assert error.step_index is None
        assert error.phase is None

    def test_a_test_key_is_accepted_with_it(self, tmp_path) -> None:
        issues = _issues(tmp_path, _log(), ["cac"], cac=_CAC)
        assert [i for i in issues if i.level == "error"] == []

    def test_a_validation_key_is_refused_without_it(self, tmp_path) -> None:
        check = {"uses": "validate/assert", "cac": _CAC, "with": {"input": "value"}}
        (error,) = [i for i in _issues(tmp_path, _log(validate=[check]), []) if i.level == "error"]
        assert error.field == "validate.cac"

    def test_a_key_inside_a_flow_branch_is_refused_without_it(self, tmp_path) -> None:
        branch = {
            "id": "flow",
            "name": "Branch",
            "uses": "flow/if",
            "with": {
                "conditions": [{"input": 1, "operator": "equals", "value": 1}],
                "then": [_log(cac=_CAC)],
            },
        }
        errors = [i for i in _issues(tmp_path, branch, []) if i.level == "error"]
        assert any("'cac'" in e.message for e in errors)

    def test_the_key_is_accepted_once_enabled(self, tmp_path) -> None:
        assert [i for i in _issues(tmp_path, _log(cac=_CAC), ["cac"]) if i.level == "error"] == []


class TestEnablingOneIsNeverSilent:
    def test_an_enabled_extension_is_reported_as_experimental(self, tmp_path) -> None:
        (warning,) = [i for i in _issues(tmp_path, _log(), ["cac"]) if i.level == "warning"]
        assert "experimental extension 'cac'" in warning.message

    def test_a_tck_enabling_nothing_gets_no_warning(self, tmp_path) -> None:
        assert [i for i in _issues(tmp_path, _log(), []) if i.level == "warning"] == []


class TestLabsSteps:
    def test_a_labs_step_is_refused_without_the_extension(self, tmp_path) -> None:
        step = {"id": "try_it", "name": "Try", "uses": "labs/example/try_it"}
        errors = [i.message for i in _issues(tmp_path, step, []) if i.level == "error"]
        assert any("'labs/example/try_it'" in e and "extensions: [labs]" in e for e in errors)

    def test_every_labs_step_lives_in_the_labs_package(self) -> None:
        """And nothing in that package escapes the prefix — the id says it is experimental."""
        for step_type in StepRegistry.list_step_types():
            module = inspect.getmodule(StepRegistry.get_any(step_type)).__name__
            in_labs = module.startswith("tractusx_testlab.extensions.labs")
            assert step_type.startswith("labs/") == in_labs, (step_type, module)


class TestTheCatalogue:
    def test_every_extension_is_experimental_and_named_by_its_key(self) -> None:
        for name, extension in EXTENSIONS.items():
            assert extension.name == name
            assert extension.stability == "experimental"

    def test_an_unknown_extension_is_refused_by_name(self) -> None:
        with pytest.raises(ValidationError):
            TckDefinition.model_validate(
                {"syntax": "v1-alpha", "id": "x", "metadata": {"name": "x"}, "extensions": ["nope"]}
            )
