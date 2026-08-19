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

"""Testlab configuration model — resolves settings from YAML, env vars, CLI flags."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from tractusx_testlab.models import VaultConfig
from tractusx_testlab.models.domain.infrastructure import Infrastructure

_DEFAULT_BASE = Path.home() / ".testlab"


class TestlabConfig(BaseSettings):
    """Engine settings, resolved from ``testlab.config.yaml``, env and CLI.

    Every field is settable as ``TESTLAB_<FIELD>``, derived from the model rather
    than listed by hand. The loader used to keep a literal dict of seven names
    against eleven fields, so ``logs_dir`` — a real setting — had no environment
    variable at all, for no stated reason. Deriving the names is the same
    principle ``infrastructure/mapping.py`` already applies to bindings: one
    declaration, every surface generated from it.

    Unknown keys are rejected. A misspelled setting used to be discarded in
    silence and the operator got the default they did not ask for — a
    ``storage_dir`` typo meant packages quietly landed under ``~/.testlab``
    while the config file said otherwise.
    """

    model_config = SettingsConfigDict(
        extra="forbid",
        env_prefix="TESTLAB_",
        env_nested_delimiter="__",
    )

    keys_dir: Path = Field(default=_DEFAULT_BASE / "keys")
    trust_store_dir: Path = Field(default=_DEFAULT_BASE / "trusted_compilers")
    storage_dir: Path = Field(default=_DEFAULT_BASE / "packages")
    #: Where the console transcript of a run is written — the same lines the
    #: operator watches go by, kept as text.
    logs_dir: Path = Field(default=_DEFAULT_BASE / "logs")
    #: Where the CloudEvents execution trace is written (ADR-0016). Separate from
    #: ``logs_dir`` on purpose: the log is for a person, the trace is the
    #: machine-readable evidence — every step's outputs, checks, and the full
    #: request/response of every call it made — and one file cannot serve both
    #: without the transcript becoming unreadable.
    data_dir: Path = Field(default=_DEFAULT_BASE / "data")
    server_port: int = Field(default=8100, ge=1, le=65535)
    max_upload_bytes: int = Field(default=52_428_800, gt=0)  # 50 MB
    default_timeout_s: float = Field(default=600.0, gt=0)
    #: The deployment this engine drives — its own connector, registry and
    #: submodel server, and the system under test it talks to. Held here so an
    #: engine is configured once, at startup, rather than per script.
    infrastructure: Infrastructure = Field(default_factory=Infrastructure)
    vault: VaultConfig | None = None
    library_path: Path | None = None
