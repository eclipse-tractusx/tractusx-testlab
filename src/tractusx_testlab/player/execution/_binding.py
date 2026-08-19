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

"""Settling which deployment a run targets, before the run starts.

A run is pointed at infrastructure from four directions — a registered profile,
a config file, the environment, and the run's own ``--var`` overrides — and the
TCK states what it needs from all of it. Reconciling those is one job with one
place to look, kept beside the other two things a run settles before its first
step: the variables it was seeded with (``_context_seeder``) and the tests it
was told to skip (``_skip``).
"""

from __future__ import annotations

from tractusx_testlab.infrastructure.mapping import collect_overrides, flatten
from tractusx_testlab.infrastructure.profiles import InfrastructureManager
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.scripting._infrastructure import collect_infrastructure_requirements
from tractusx_testlab.scripting.script import Tck
from tractusx_testlab.syntax import defaults


def bind_infrastructure(
    manager: InfrastructureManager,
    context: StepContext,
    tck: Tck,
) -> None:
    """Settle which deployment this run targets, and refuse one it cannot reach.

    The active deployment is the starting point and the run's own variables
    are written over it, so an operator overrides a single address for one
    run — ``--var infrastructure.sut.dtr.base_url=…`` — without touching the
    registered deployment or the next run.

    What the TCK requires is then checked against what is bound, before the
    first step: a capability declared ``required: true`` with nothing behind
    it fails here, naming the key the operator owes, rather than surfacing
    as an empty URL somewhere in the middle of the run.

    What the TCK certifies against — its ecosystem release and its per-
    capability standards — is then carried onto the bindings, so the SDK
    builds Saturn or Jupiter services because the TCK says so and not
    because a config file repeated it.

    The resolved bindings are published back into the variable namespace so
    ``${{ infrastructure.sut.connector.dsp_url }}`` resolves the same
    whether the value came from a profile, the environment, or the CLI, and
    the requirements reach the override reader so a typo is answered with
    the keys this TCK needs rather than with the whole model.
    """
    requirements = collect_infrastructure_requirements(tck)
    release, release_stated = _target_release(tck)

    resolved = manager.resolve(collect_overrides(context.variables, requirements))
    manager.validate(requirements, resolved)
    resolved = manager.align(
        requirements,
        release,
        release_stated=release_stated,
        infrastructure=resolved,
    )

    context.bind_infrastructure(resolved)
    for key, value in flatten(resolved).items():
        context.set_variable(key, value)


def _target_release(tck: Tck) -> tuple[str, bool]:
    """Return the ecosystem release a TCK targets, and whether it said so itself.

    ``dataspace.version`` (ADR-0019) is the only source. The flat
    ``dataspace_version`` field was an older spelling of the same thing and is
    gone: while both existed, the player read it off the definition — where it
    had never lived — so a TCK stating one release was run as another, and
    reported the release as unstated, which suppressed the conflict check that
    would have caught it.

    Whether it was stated at all matters: a release nobody declared is a
    default, and a default must never be held against an operator who bound a
    deployment of a different one.
    """
    definition = tck.definition
    dataspace = definition.dataspace if definition is not None else None
    if dataspace is not None and dataspace.version:
        return dataspace.version, True
    return defaults.DATASPACE_VERSION, False
