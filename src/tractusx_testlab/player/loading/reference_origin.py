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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Which variable a ``${{ ... }}`` reference reads, and whose fault it is when
it reads nothing (``errors[].origin``).

Kept apart from :mod:`tractusx_testlab.player.loading.resolver` only for
length; the resolver re-exports :func:`origin_of`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models.primitives.exceptions import AuthoringError
from tractusx_testlab.syntax import call_scope

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

__all__ = ["origin_of"]


def _name_of(expr: str) -> str:
    """The context variable *expr* reads.

    Resolution rules:
    - ``env.X`` → context variable ``X``
    - ``execution.ID.FIELD``, ``setup.ID.FIELD``, ``teardown.ID.FIELD``,
      ``infrastructure.X.Y…`` → flat context lookup of the full dotted path
      (set by store_step_outputs or seeded by the player).
    - Anything else → flat context lookup as-is.
    """
    return expr[4:] if expr.startswith("env.") else expr


#: Where a step publishes its ``returns:``, and how many segments name the step:
#: ``<phase>.<step id>.<name>``, and ``*.process.<step id>.<name>`` for a
#: dynamic mock's steps.
_STEP_NAMESPACES: tuple[tuple[str, int], ...] = (
    ("execution.", 2),
    ("setup.", 2),
    ("teardown.", 2),
    (f"{call_scope.PROCESS}.", 3),
)


def _step_of(name: str) -> str | None:
    """The step (``<phase>.<id>``) whose output *name* reads, if it reads one."""
    for namespace, segments in _STEP_NAMESPACES:
        if name.startswith(namespace):
            return ".".join(name.split(".")[:segments])
    return None


def origin_of(expr: str, context: StepContext) -> str:
    """Who a reference that resolved to nothing belongs to (``errors[].origin``).

    The compiler checks a reference's root against what the TCK declares, not
    the rest, so one that names nothing at run time is usually the author's: a
    path into a published value, a name the step's ``returns:`` does not
    declare, the output of a step that has no ``returns:`` or was skipped. Two
    are not:

    - What the SUT's call to a mock did not carry (``*.request.body.<field>``):
      the caller — the system under test — did not send it. ``sut``.
    - The output of a step that failed before publishing anything, or never ran
      because a failure stopped the test first: this reference only follows
      from that failure, and carries its origin — a teardown that withdraws
      what setup never created, after setup was refused on an asset id the TCK
      reused, is the TCK's to fix like the refusal itself.

    Whether a step failed is what the runner recorded
    (``StepContext.steps``), not inferred from what it published: a
    step with no ``returns:`` publishes nothing and passed.
    """
    name = _name_of(expr)
    if name.startswith(f"{call_scope.REQUEST}."):
        return "sut"
    step = _step_of(name)
    if step is None or any(variable.startswith(f"{step}.") for variable in context.variables):
        return AuthoringError.origin
    outcome = context.steps.outcome_of(step)
    if outcome is None:
        return context.steps.stopped_by or AuthoringError.origin
    return outcome.origin or AuthoringError.origin
