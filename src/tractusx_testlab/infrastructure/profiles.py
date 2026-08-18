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

"""InfrastructureManager — the deployments an engine can run against.

The manager holds one or more named :class:`Infrastructure` combinations in
memory and knows which of them the next run uses. An adopter embedding the
player builds one directly and hands it over, so the deployment a run targets
is a typed object passed at construction rather than a set of strings the
engine hopes to find in its variables::

    from tractusx_testlab import (
        ConnectorBinding,
        DtrBinding,
        EngineBindings,
        EngineDtrBinding,
        Infrastructure,
        InfrastructureManager,
        SutBindings,
        TestlabPlayer,
    )

    integration = Infrastructure(
        engine=EngineBindings(
            connector=ConnectorBinding(
                management_url="https://engine.example.com/management",
                api_key="…",
                participant_id="BPNL000000000TLB",
            ),
            dtr=EngineDtrBinding(
                base_url="https://engine.example.com/semantics/registry",
                submodel_base_url="https://backend.example.com",
            ),
        ),
        sut=SutBindings(
            connector=ConnectorBinding(
                management_url="https://sut.example.com/management",
                participant_id="BPNL000000000001",
                dsp_url="https://sut.example.com/api/v1/dsp",
            ),
            dtr=DtrBinding(base_url="https://sut.example.com/semantics/registry"),
        ),
    )

    infrastructure = InfrastructureManager(integration, name="integration")
    infrastructure.register("staging", staging_deployment)

    player = TestlabPlayer(infrastructure=infrastructure)

Registering several deployments is the point of the registry: an adopter that
runs the same TCKs against local, integration and staging keeps all three side
by side and switches with :meth:`activate` instead of rebuilding the player.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from tractusx_testlab.infrastructure.mapping import (
    apply_overrides,
    capabilities,
    context_key,
    flatten,
    merge,
    overrides_from_env,
)
from tractusx_testlab.infrastructure.standards import (
    KNOWN_RELEASES,
    default_standard,
    is_known_release,
    release_or_default,
)
from tractusx_testlab.models.authoring.infrastructure import InfrastructureConfig
from tractusx_testlab.models.domain.infrastructure import Infrastructure
from tractusx_testlab.models.primitives.exceptions import (
    InfrastructureError,
    MissingBindingError,
    StandardConflictError,
)

logger = logging.getLogger(__name__)

#: Name a manager built from a single deployment files it under.
DEFAULT_PROFILE = "default"


class InfrastructureManager:
    """Registry of named infrastructure combinations, one of them active."""

    __slots__ = ("_active", "_profiles")

    def __init__(
        self,
        infrastructure: Infrastructure | None = None,
        *,
        name: str = DEFAULT_PROFILE,
    ) -> None:
        """Hold *infrastructure* under *name* and make it the active deployment.

        A manager built with nothing is a valid one — an engine bound to no
        deployment can still run a TCK that requires none, and one that
        requires something says which capability was never bound.
        """
        self._profiles: dict[str, Infrastructure] = {name: infrastructure or Infrastructure()}
        self._active: str = name

    # ------------------------------------------------------------------
    # Construction from the engine's own configuration
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: object, *, name: str = DEFAULT_PROFILE) -> InfrastructureManager:
        """Build a manager from the ``infrastructure`` block of a loaded config."""
        infrastructure = getattr(config, "infrastructure", None)
        if not isinstance(infrastructure, Infrastructure):
            infrastructure = Infrastructure()
        return cls(infrastructure, name=name)

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        base: Infrastructure | None = None,
        name: str = DEFAULT_PROFILE,
    ) -> InfrastructureManager:
        """Build a manager from ``TESTLAB_<SIDE>_<CAPABILITY>_<FIELD>`` variables.

        *base* is the deployment the environment is read on top of, for a
        container that ships a profile and overrides a URL or two.
        """
        starting_point = base or Infrastructure()
        return cls(
            apply_overrides(starting_point, overrides_from_env(environ)),
            name=name,
        )

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        infrastructure: Infrastructure,
        *,
        activate: bool = False,
    ) -> None:
        """Add or replace the deployment held under *name*."""
        self._profiles[name] = infrastructure
        if activate:
            self._active = name

    def get(self, name: str) -> Infrastructure:
        """Return the deployment held under *name*."""
        if name not in self._profiles:
            known = ", ".join(sorted(self._profiles)) or "none"
            raise InfrastructureError(
                f"No infrastructure registered under '{name}'. Registered: {known}"
            )
        return self._profiles[name]

    def activate(self, name: str) -> None:
        """Make the deployment held under *name* the one the next run uses."""
        self.get(name)
        self._active = name

    @property
    def names(self) -> list[str]:
        """Names of every registered deployment."""
        return sorted(self._profiles)

    @property
    def active_name(self) -> str:
        """Name of the deployment the next run uses."""
        return self._active

    @property
    def active(self) -> Infrastructure:
        """The deployment the next run uses."""
        return self._profiles[self._active]

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def overlay(self, infrastructure: Infrastructure) -> None:
        """Write everything *infrastructure* states over the active deployment.

        Used by the doors that layer a second source onto a profile — a
        config file over a registered deployment — where the second source
        states only what it changes.
        """
        self._profiles[self._active] = merge(self.active, infrastructure)

    def resolve(self, overrides: Mapping[str, object] | None = None) -> Infrastructure:
        """Return the active deployment with the run's *overrides* applied.

        Overrides are context-keyed (``infrastructure.sut.dtr.base_url``), which
        is the form they arrive in from ``--var``, a run-config, and the HTTP
        API alike. The registered deployment is not modified: a value supplied
        for one run does not leak into the next.
        """
        return apply_overrides(self.active, overrides or {})

    def validate(
        self,
        requirements: InfrastructureConfig,
        infrastructure: Infrastructure | None = None,
    ) -> None:
        """Check every required capability against what is bound, and say what is missing.

        Reports all unbound capabilities at once rather than the first, so an
        operator learns everything they owe from a single run. Requirements
        marked ``required: false`` are optional by definition and are not
        checked.
        """
        resolved = self.active if infrastructure is None else infrastructure
        missing: list[tuple[str, str, str]] = []

        for side, capability, binding_type in capabilities():
            requirement = getattr(requirements, side, {}).get(capability)
            if requirement is None or not requirement.required:
                continue
            if not resolved.bound(side, capability):
                missing.append(
                    (side, capability, context_key(side, capability, binding_type.identity_field))
                )

        if missing:
            raise MissingBindingError(missing)

    def align(
        self,
        requirements: InfrastructureConfig,
        release: str,
        *,
        release_stated: bool = True,
        infrastructure: Infrastructure | None = None,
    ) -> Infrastructure:
        """Return a deployment carrying the standard and release the TCK certifies against.

        A TCK states which ecosystem release it targets (``dataspace.version``)
        and, per capability, which standard it certifies (``standard.id`` and
        ``standard.version``). An operator binds addresses, not standards, so
        those three travel from the TCK onto every bound capability here —
        which is what makes ``saturn`` or ``jupiter`` decide the connector
        dialect the SDK builds without anyone repeating it in a config file.

        A binding that states one of the three keeps it: an operator who knows
        their connector speaks a different release has said so deliberately.
        When it contradicts something the TCK actually stated, that is a run
        which cannot prove what it claims, and it is refused with both values
        named.
        """
        resolved = self.active if infrastructure is None else infrastructure
        release = release_or_default(release)

        if release_stated and not is_known_release(release):
            logger.warning(
                "TCK targets ecosystem release '%s', which is not one the engine knows (%s) — "
                "the SDK will decide whether it can build services for it",
                release,
                ", ".join(KNOWN_RELEASES),
            )

        conflicts: list[tuple[str, str, str, str, str]] = []
        fills: dict[str, str] = {}

        for side, capability, _ in capabilities():
            binding = resolved.binding(side, capability)
            if binding is None or not binding.is_bound():
                continue

            requirement = getattr(requirements, side, {}).get(capability)
            standard = requirement.standard if requirement is not None else None

            # (field, what the TCK certifies, what the engine falls back to)
            stated: list[tuple[str, str, str]] = [
                ("version", release if release_stated else "", release),
                (
                    "standard",
                    standard.id if standard is not None else "",
                    default_standard(capability),
                ),
                (
                    "standard_version",
                    standard.version if standard is not None else "",
                    standard.effective_version(release) if standard is not None else "",
                ),
            ]

            for field, certified, fallback in stated:
                bound = str(getattr(binding, field, "") or "")
                if not bound:
                    if certified or fallback:
                        fills[context_key(side, capability, field)] = certified or fallback
                elif certified and bound != certified:
                    conflicts.append((side, capability, field, bound, certified))

        if conflicts:
            raise StandardConflictError(conflicts)

        return apply_overrides(resolved, fills)

    def flatten(self, infrastructure: Infrastructure | None = None) -> dict[str, str]:
        """Project a deployment onto the context keys a test can reference."""
        return flatten(self.active if infrastructure is None else infrastructure)
