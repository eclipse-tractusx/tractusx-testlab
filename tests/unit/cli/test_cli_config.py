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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""``testlab config`` says which credentials are set, never what they are.

Its output is what an operator pastes into a ticket or a chat when asking why a
run went where it went; it used to carry the connectors' management API keys
and the vault token as they were. Both forms — ``--json`` and the table — now
read ``***`` for every credential that is set, and still show everything else.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tractusx_testlab.cli import app

_ENGINE_KEY = "engine-management-key-0123456789"
_SUT_KEY = "sut-management-key-9876543210"
_VAULT_TOKEN = "hvs.vault-token-abcdefghijklmnop"

_CONFIG = f"""\
server_port: 8123
vault:
  vault_url: https://vault.example.com
  vault_token: {_VAULT_TOKEN}
infrastructure:
  engine:
    connector:
      management_url: https://engine.example.com/management
      api_key: {_ENGINE_KEY}
  sut:
    connector:
      management_url: https://sut.example.com/management
      api_key: {_SUT_KEY}
"""

runner = CliRunner()


@pytest.fixture()
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Only the file: nothing set in the environment of whoever runs the tests.
    for name in [name for name in os.environ if name.startswith("TESTLAB_")]:
        monkeypatch.delenv(name)
    path = tmp_path / "testlab.config.yaml"
    path.write_text(_CONFIG, encoding="utf-8")
    return path


def _secrets_in(output: str) -> list[str]:
    return [secret for secret in (_ENGINE_KEY, _SUT_KEY, _VAULT_TOKEN) if secret in output]


class TestTheJsonForm:
    def test_reads_every_credential_as_masked(self, config_file: Path) -> None:
        result = runner.invoke(app, ["config", "--config", str(config_file), "--json"])

        assert result.exit_code == 0, result.output
        assert _secrets_in(result.output) == []
        shown = json.loads(result.output)
        assert shown["vault"]["vault_token"] == "***"
        assert shown["infrastructure"]["engine"]["connector"]["api_key"] == "***"
        assert shown["infrastructure"]["sut"]["connector"]["api_key"] == "***"

    def test_still_shows_everything_else(self, config_file: Path) -> None:
        result = runner.invoke(app, ["config", "--config", str(config_file), "--json"])

        shown = json.loads(result.output)
        assert shown["server_port"] == 8123
        assert shown["vault"]["vault_url"] == "https://vault.example.com"
        engine = shown["infrastructure"]["engine"]["connector"]
        assert engine["management_url"] == "https://engine.example.com/management"


class TestTheTable:
    def test_reads_every_credential_as_masked(self, config_file: Path) -> None:
        result = runner.invoke(app, ["config", "--config", str(config_file)])

        assert result.exit_code == 0, result.output
        assert _secrets_in(result.output) == []
        assert '"vault_token": "***"' in result.output
        assert "infrastructure.engine.connector.api_key" in result.output

    def test_an_unset_credential_stays_empty(self, config_file: Path) -> None:
        """Masking an empty value would claim a credential that was never configured."""
        config_file.write_text(_CONFIG.replace(_VAULT_TOKEN, '""'), encoding="utf-8")

        result = runner.invoke(app, ["config", "--config", str(config_file), "--json"])

        assert json.loads(result.output)["vault"]["vault_token"] == ""
