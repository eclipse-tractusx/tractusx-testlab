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

"""A step's ``checkpoint:`` mark that the run could not honour as written (ADR-0028).

A step type that declares a checkpoint fixes its direction and how its call
travels: a mark may relabel it or switch it off, not turn a wait into a call.
And an ``internal`` checkpoint calls nothing, so it has no ``via``. Steps a flow
step carries are checked too, reported against the flow step.
"""

from __future__ import annotations

from collections.abc import Iterator

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.models.authoring.checkpoint_mark import CheckpointMark
from tractusx_testlab.models.authoring.definitions import StepDefinition, TestDefinition
from tractusx_testlab.models.primitives.checkpoint import Checkpoint, Direction

#: (phase, step index, field, message)
Finding = tuple[str, int, str, str]


def checkpoint_findings(test: TestDefinition) -> Iterator[Finding]:
    """Every ``checkpoint:`` mark of *test* that contradicts its step, or itself."""
    for phase in ("setup", "execution", "teardown"):
        for index, definition in enumerate(getattr(test, phase)):
            for problem in _problems(definition):
                yield phase, index, "checkpoint", problem


def _problems(definition: StepDefinition) -> Iterator[str]:
    mark = definition.checkpoint
    step_cls = StepRegistry.get_any(definition.uses)
    declared = getattr(step_cls, "checkpoint", None)
    if isinstance(mark, CheckpointMark):
        if isinstance(declared, Checkpoint) and (mark.direction or mark.via):
            yield (
                f"'{definition.uses}' is a {declared.direction} checkpoint by its type; "
                "'checkpoint:' may give it a label and a description, or switch it off "
                "with 'checkpoint: false', but not change its direction or 'via'."
            )
        elif mark.direction is Direction.INTERNAL and mark.via is not None:
            yield "An internal checkpoint calls nothing: drop 'via', or give another direction."
    for key in getattr(step_cls, "nested_steps", None) or {}:
        children = (definition.with_ or {}).get(key)
        for child in children if isinstance(children, list) else []:
            if isinstance(child, dict) and "uses" in child:
                try:
                    nested = StepDefinition.model_validate(child)
                except ValueError:  # the step's own checks report it
                    continue
                yield from _problems(nested)
