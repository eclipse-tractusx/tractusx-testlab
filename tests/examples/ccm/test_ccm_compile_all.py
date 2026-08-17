###############################################################
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
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Smoke tests: every CCM example YAML file parses and compiles without error."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.paths import CCM_RAW_DIR
from tractusx_testlab.scripting.parser import YamlParser

CCM_TESTS_DIR = CCM_RAW_DIR / "tests"

_CCM_YAML_FILES = sorted(CCM_TESTS_DIR.glob("*.yaml"))


@pytest.mark.parametrize(
    "yaml_path",
    _CCM_YAML_FILES,
    ids=[p.name for p in _CCM_YAML_FILES],
)
class TestCcmCompileAll:
    """Each CCM YAML file must parse into a valid ScriptDefinition."""

    def test_parses_without_error(self, yaml_path: Path) -> None:
        script = YamlParser.parse_script(yaml_path)

        assert script is not None, f"Failed to parse {yaml_path.name}"

    def test_has_steps(self, yaml_path: Path) -> None:
        script = YamlParser.parse_script(yaml_path)

        assert len(script.execution) > 0, f"{yaml_path.name} must have at least one step"

    def test_has_name(self, yaml_path: Path) -> None:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        metadata_name = (data.get("metadata") or {}).get("name")

        assert metadata_name, f"{yaml_path.name} must carry a human-readable metadata.name"
