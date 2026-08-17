#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################

"""Testlab configuration model — resolves settings from YAML, env vars, CLI flags."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from tractusx_testlab.models import VaultConfig
from tractusx_testlab.models.domain.infrastructure import Infrastructure

_DEFAULT_BASE = Path.home() / ".testlab"


class TestlabConfig(BaseModel):
    """Engine settings, resolved from ``testlab.config.yaml``, env and CLI.

    Unknown keys are rejected. A misspelled setting used to be discarded in
    silence and the operator got the default they did not ask for — a
    ``storage_dir`` typo meant packages quietly landed under ``~/.testlab``
    while the config file said otherwise.
    """

    model_config = ConfigDict(extra="forbid")

    keys_dir: Path = Field(default=_DEFAULT_BASE / "keys")
    trust_store_dir: Path = Field(default=_DEFAULT_BASE / "trusted_compilers")
    storage_dir: Path = Field(default=_DEFAULT_BASE / "packages")
    logs_dir: Path = Field(default=_DEFAULT_BASE / "logs")
    server_port: int = 8100
    max_upload_bytes: int = 52_428_800  # 50 MB
    default_timeout_s: float = 600.0
    #: The deployment this engine drives — its own connector, registry and
    #: submodel server, and the system under test it talks to. Held here so an
    #: engine is configured once, at startup, rather than per script.
    infrastructure: Infrastructure = Field(default_factory=Infrastructure)
    vault: VaultConfig | None = None
    library_path: Path | None = None
