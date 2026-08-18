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

"""StepContext — the execution context passed to every step.

Provides access to services, variables, job memory, and configuration.
"""

from __future__ import annotations

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.contracts import StepInvoker
from tractusx_testlab.models import Job
from tractusx_testlab.models.domain.infrastructure import Infrastructure
from tractusx_testlab.player.execution.dataspace_access import DataspaceAccess
from tractusx_testlab.services.instances import ServiceManager


class StepContext:
    """Mutable execution context shared across steps within a single script run."""

    __slots__ = (
        "_config",
        "_infrastructure",
        "_invoker",
        "_job",
        "_services",
        "_variables",
    )

    def __init__(
        self,
        services: ServiceManager,
        job: Job,
        config: TestlabConfig,
        infrastructure: Infrastructure | None = None,
    ) -> None:
        self._services = services
        self._job = job
        self._config = config
        self._infrastructure = config.infrastructure if infrastructure is None else infrastructure
        self._variables: dict[str, object] = {}
        self._invoker: StepInvoker | None = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def config(self) -> TestlabConfig:
        return self._config

    @property
    def infrastructure(self) -> Infrastructure:
        """The deployment this run targets, after the run's own overrides.

        A step reads an engine-side address from here rather than from a
        variable a script supplied, because where the engine's own
        infrastructure lives is the operator's decision and not the test's.
        """
        return self._infrastructure

    def bind_infrastructure(self, infrastructure: Infrastructure) -> None:
        """Fix the deployment for this run — called once, before the first step."""
        self._infrastructure = infrastructure

    @property
    def services(self) -> ServiceManager:
        return self._services

    @property
    def dataspace(self) -> DataspaceAccess:
        """The connector, registry and notification services this run reaches.

        Held apart from the context rather than on it: a ``util/log`` step and a
        DSP negotiation step get the same context, and only one of them has any
        business knowing what a catalog is.
        """
        return DataspaceAccess(self._services)

    # ------------------------------------------------------------------
    # Running a nested step
    # ------------------------------------------------------------------

    def bind_invoker(self, invoker: StepInvoker) -> None:
        """Give this context the means to run a step — called once, by the runner."""
        self._invoker = invoker

    @property
    def invoke_step(self) -> StepInvoker:
        """Run one step, for the flow steps that contain other steps.

        Handed over by the runner rather than imported from it: the player
        imports the steps package to register the steps, so a step importing the
        player closes a cycle. ``flow/if`` and ``flow/retry`` used to reach for
        ``run_step`` from inside their ``execute`` bodies, which hid the cycle
        instead of removing it.
        """
        if self._invoker is None:
            raise RuntimeError(
                "This context cannot run nested steps — no invoker was bound. "
                "A flow step reached one built outside the player."
            )
        return self._invoker

    # ------------------------------------------------------------------
    # Job / Memory
    # ------------------------------------------------------------------

    @property
    def job(self) -> Job:
        return self._job

    # ------------------------------------------------------------------
    # Variables (script-scoped, resolved from step params with ${...})
    # ------------------------------------------------------------------

    def set_variable(self, name: str, value: object) -> None:
        self._variables[name] = value

    def get_variable(self, name: str, default: object = None) -> object:
        return self._variables.get(name, default)

    def get_str(self, name: str, default: str = "") -> str:
        """Read a variable that a step is going to use as text.

        Variables hold whatever a step published, so :meth:`get_variable`
        returns ``object`` and every caller that wanted a URL or a token had to
        narrow it — or, more often, not narrow it and pass ``object`` into
        ``.rstrip()`` or an HTTP header. Narrowed once, here, with the
        conversion made explicit rather than implied by use.
        """
        value = self._variables.get(name, default)
        if value is None:
            return default
        return value if isinstance(value, str) else str(value)

    def has_variable(self, name: str) -> bool:
        return name in self._variables

    @property
    def variables(self) -> dict[str, object]:
        return dict(self._variables)
