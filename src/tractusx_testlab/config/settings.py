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

"""Testlab configuration model — resolves settings from YAML, env vars, CLI flags."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
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
    #: The mock server's address as the system under test reaches it — origin
    #: only, no path: ``https://testlab.example.com`` or ``http://engine:8100``.
    #: ``mock/api`` publishes every callback URL under this root, behind the
    #: run's own ``/runs/<run id>`` unless the root names the run already (an
    #: engine's ``<origin>/mock/<job id>``). Left unset,
    #: it is ``http://localhost:<server_port>``, which is right only while the
    #: SUT shares the host; a connector in another container, or the engine
    #: behind an ingress, needs the address it can actually dial.
    mock_public_url: str | None = Field(default=None)
    #: Which routes the in-process server mounts (``server.app.ServerMode``):
    #: ``full`` — the package, compile and job API besides the mocks, what
    #: ``testlab serve`` offers — or ``mock``, only what a running job needs for
    #: inbound calls. Unset, ``testlab serve`` is ``full`` and the server the
    #: player starts for a run is ``mock``. A host whose mock server is
    #: reachable by the systems it tests sets ``mock``.
    server_mode: Literal["full", "mock"] | None = Field(default=None)
    max_upload_bytes: int = Field(default=52_428_800, gt=0)  # 50 MB
    default_timeout_s: float = Field(default=600.0, gt=0)
    #: The deployment this engine drives — its own connector, registry and
    #: submodel server, and the system under test it talks to. Held here so an
    #: engine is configured once, at startup, rather than per test.
    infrastructure: Infrastructure = Field(default_factory=Infrastructure)
    vault: VaultConfig | None = None
    library_path: Path | None = None
    #: The sides of the topology whose bound credentials a test may put on the
    #: wire itself — as a header of ``http/http_request``, to the binding's own
    #: origin. Both by default. A host running TCKs it did not author sets
    #: ``{"sut"}``, so a test can never send the engine's own management key
    #: anywhere; the connector and registry steps keep working either way,
    #: because they are handed the credential by the binding, not by the test.
    credential_release: frozenset[Literal["engine", "sut"]] = Field(
        default=frozenset({"engine", "sut"})
    )
    #: The sides of the topology a run's own inputs may re-point — an
    #: ``infrastructure.<side>.<capability>.<field>`` among the run variables,
    #: as ``--var`` or a run-config supplies it. Both by default, for an
    #: operator driving TestLab from the CLI. A host that binds the deployment
    #: itself and runs inputs it did not write sets an empty set: the run then
    #: targets exactly what the host bound. Values a TCK carries (``env``,
    #: shared variables, test data) never re-point a binding, whatever this says.
    binding_overrides: frozenset[Literal["engine", "sut"]] = Field(
        default=frozenset({"engine", "sut"})
    )

    @field_validator("mock_public_url")
    @classmethod
    def _origin_only(cls, value: str | None) -> str | None:
        """An origin, not a page: scheme and host, no trailing slash.

        The step joins the mock's path straight onto it, so a trailing slash
        would double up and a bare hostname would produce a relative URL the
        SUT cannot dial.
        """
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError("mock_public_url must start with http:// or https://")
        return value.rstrip("/")

    @property
    def mock_base_url(self) -> str:
        """Root URL the mock server is published under, resolved."""
        return self.mock_public_url or f"http://localhost:{self.server_port}"
