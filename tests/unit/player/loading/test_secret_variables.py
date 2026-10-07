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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""An embedder reads ``secret: true`` off a variable, from the sources and from the package."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tests.paths import TESTS_DIR
from tractusx_testlab.authoring.parser import YamlParser
from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.cli.compile import compile as compile_command
from tractusx_testlab.player.loading.loader import Loader

_SMOKE = TESTS_DIR / "e2e" / "connector-dtr-smoke"


def _sources(tmp_path: Path) -> Path:
    source = tmp_path / "src"
    shutil.copytree(_SMOKE, source)
    manifest = source / "index.yaml"
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    data["env"]["variables"].append(
        {
            "id": "sut_bearer",
            "uses": "variable/type/string",
            "name": "Bearer token the SUT's API expects",
            "secret": True,
            "with": {"source": "input", "scope": "sut"},
            "returns": {"value": {"type": "string"}},
        }
    )
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return manifest


def test_the_uncompiled_manifest_says_which_input_is_secret(tmp_path: Path) -> None:
    manifest = _sources(tmp_path)
    variables = Tck(YamlParser.parse_tck(manifest), manifest.parent).all_variables()
    assert variables["sut_bearer"].secret is True
    assert not any(var.secret for name, var in variables.items() if name != "sut_bearer")


def test_the_compiled_package_carries_the_flag(tmp_path: Path) -> None:
    manifest = _sources(tmp_path)
    compile_command(
        manifest=manifest,
        compiler_keys=None,
        player_pub=None,
        output=tmp_path / "dist",
        version=None,
        plain=False,
    )
    package = next((tmp_path / "dist").glob("*.tck"))

    assert Loader().load(package).all_variables()["sut_bearer"].secret is True
