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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Discovers and merges configuration from YAML file, env vars, and CLI flags."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.infrastructure.mapping import (
    apply_overrides,
    merge,
    overrides_from_env,
)
from tractusx_testlab.models import VaultConfig
from tractusx_testlab.models.domain.infrastructure import Infrastructure

_CONFIG_FILENAME = "testlab.config.yaml"
_ENV_PREFIX = "TESTLAB_"


def _as_infrastructure(declared: object) -> Infrastructure:
    """Read one config layer's ``infrastructure`` block as the model it describes."""
    if isinstance(declared, Infrastructure):
        return declared
    if isinstance(declared, dict):
        return Infrastructure.model_validate(declared)
    return Infrastructure()


class ConfigLoader:
    """Merges config sources with precedence: CLI > env > file > defaults."""

    @staticmethod
    def load(
        config_path: Path | None = None,
        cli_overrides: dict | None = None,
    ) -> TestlabConfig:
        file_data = ConfigLoader._load_file(config_path)
        env_data = ConfigLoader._load_env()

        merged = {**file_data, **env_data}
        if cli_overrides:
            merged.update({key: value for key, value in cli_overrides.items() if value is not None})

        if "vault" in merged and isinstance(merged["vault"], dict):
            merged["vault"] = VaultConfig(**merged["vault"])

        merged["infrastructure"] = ConfigLoader._load_infrastructure(
            file_data.get("infrastructure"),
            (cli_overrides or {}).get("infrastructure"),
        )

        return TestlabConfig(**merged)

    @staticmethod
    def _load_infrastructure(declared: object, cli_declared: object) -> Infrastructure:
        """Build the infrastructure block from file, environment and caller, in that order.

        The file states a whole deployment, the environment adjusts single
        fields of it — which is how one container image is pointed at a
        different connector per stage — and a caller constructing the config
        itself has the last word. The layers meet rather than replace one
        another, so setting one URL in the environment does not erase the rest
        of the block.
        """
        resolved = apply_overrides(_as_infrastructure(declared), overrides_from_env())
        if cli_declared is None:
            return resolved
        return merge(resolved, _as_infrastructure(cli_declared))

    @staticmethod
    def _load_file(config_path: Path | None = None) -> dict:
        candidates = (
            [config_path]
            if config_path
            else [
                Path.cwd() / _CONFIG_FILENAME,
                Path.home() / ".testlab" / _CONFIG_FILENAME,
            ]
        )
        for path in candidates:
            if path and path.is_file():
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        return {}

    @staticmethod
    def _load_env() -> dict:
        """No longer reads anything.

        Every ``TESTLAB_*`` name is derived from :class:`TestlabConfig` by
        pydantic-settings, so a hand-written mapping here could only ever fall
        behind the model — which it had: seven names against eleven fields, with
        ``logs_dir`` missing entirely.

        The vault block is the one exception, kept because it arrives as a
        nested object assembled from three separate variables.
        """
        vault_url = os.environ.get(f"{_ENV_PREFIX}VAULT_URL")
        if not vault_url:
            return {}
        return {
            "vault": {
                "vault_url": vault_url,
                "vault_token": os.environ.get(f"{_ENV_PREFIX}VAULT_TOKEN", ""),
                "vault_secret_path": os.environ.get(
                    f"{_ENV_PREFIX}VAULT_SECRET_PATH", "secret/data/testlab"
                ),
            }
        }
