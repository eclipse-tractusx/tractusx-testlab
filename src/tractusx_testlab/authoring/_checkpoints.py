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

"""A package's checkpoints, in run order, without running it (ADR-0022, ADR-0027).

A step is a checkpoint when its type declares one on its ``@step`` decorator,
or when its test marks it with ``checkpoint:`` — and not when the test says
``checkpoint: false``. The steps a flow step carries are walked too, depth
first, under the ``with:`` keys the flow step declares (``nested_steps``): one
in a ``flow/if`` branch is ``conditional``, one a ``flow/retry`` or a loop runs
is ``repeated``.

The player plans a run with the same function (``player.checkpoints``), so the
list a briefing shows before the run is the list the run reports on.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.models.authoring.checkpoint_mark import CheckpointMark
from tractusx_testlab.models.authoring.definitions import StepDefinition
from tractusx_testlab.models.primitives.checkpoint import Checkpoint, Direction, NestedRun
from tractusx_testlab.models.runtime.checkpoints import CheckpointEntry

if TYPE_CHECKING:
    from tractusx_testlab.authoring.test import Tck, Test

_TEMPLATE = "${{"
_PHASES = (("setup", "setup"), ("execution", "steps"), ("teardown", "teardown"))
#: The checkpoints whose step says itself when it asks and when it is answered.
_ASKING = frozenset({Direction.INBOUND, Direction.INTERNAL})


@dataclass(frozen=True)
class PlannedCheckpoint:
    """A checkpoint as the run follows it: the entry, and where its step sits.

    ``path`` is the position as the runner walks it — ``("execution", 2,
    "then", 0)``. ``asks`` is whether the step reports its own question and
    answer (a declared inbound wait or internal choice); any other checkpoint
    is asked when its step starts and answered when it completes.
    """

    entry: CheckpointEntry
    path: tuple[str | int, ...]
    asks: bool


def collect_checkpoints(tck: Tck, skip_tests: Collection[str] = ()) -> list[PlannedCheckpoint]:
    """Every checkpoint of the tests a run of *tck* executes, less *skip_tests*, in run order.

    *skip_tests* names tests by their manifest entry (``push.yaml``) or their id.
    """

    skipped = set(skip_tests)
    return [
        planned
        for test in tck.tests
        if not skipped & {test.test_id, test.definition.id}
        for planned in _of_test(test)
    ]


def effective_checkpoint(definition: StepDefinition) -> tuple[Checkpoint, bool] | None:
    """The checkpoint *definition* is, and whether its step asks for itself; ``None`` if none.

    The step type's declaration holds unless the test says ``checkpoint: false``.
    A step type that declares none is a checkpoint only when the test marks it,
    ``outbound`` unless the mark gives another direction.
    """
    mark = definition.checkpoint
    if mark is False:
        return None
    step_cls = StepRegistry.get_any(definition.uses)
    declared = getattr(step_cls, "checkpoint", None)
    if isinstance(declared, Checkpoint):
        return declared, declared.direction in _ASKING
    if mark is None:
        return None
    if isinstance(mark, CheckpointMark):
        try:
            return Checkpoint(direction=mark.direction or Direction.OUTBOUND, via=mark.via), False
        except ValidationError:  # the compiler reports it; the run takes it without 'via'
            return Checkpoint(direction=mark.direction or Direction.OUTBOUND), False
    return Checkpoint(direction=Direction.OUTBOUND), False


def _of_test(test: Test) -> Iterator[PlannedCheckpoint]:
    for phase, attribute in _PHASES:
        for index, definition in enumerate(getattr(test, attribute) or []):
            yield from _walk(test, definition, (phase, index), conditional=False, repeated=False)


def _walk(
    test: Test,
    definition: StepDefinition,
    path: tuple[str | int, ...],
    *,
    conditional: bool,
    repeated: bool,
) -> Iterator[PlannedCheckpoint]:
    """This step if it is a checkpoint, then the ones it carries, depth first."""
    found = effective_checkpoint(definition)
    if found is not None:
        checkpoint, asks = found
        entry = _entry(test, definition, path, checkpoint, conditional, repeated)
        yield PlannedCheckpoint(entry=entry, path=path, asks=asks)
    step_cls = StepRegistry.get_any(definition.uses)
    carried: dict[str, NestedRun] = getattr(step_cls, "nested_steps", None) or {}
    for key, run in carried.items():
        children = (definition.with_ or {}).get(key)
        for index, child in enumerate(children if isinstance(children, list) else []):
            nested = _definition(child)
            if nested is not None:
                yield from _walk(
                    test,
                    nested,
                    (*path, key, index),
                    conditional=conditional or run is NestedRun.CONDITIONAL,
                    repeated=repeated or run is NestedRun.REPEATED,
                )


def _entry(
    test: Test,
    definition: StepDefinition,
    path: tuple[str | int, ...],
    checkpoint: Checkpoint,
    conditional: bool,
    repeated: bool,
) -> CheckpointEntry:
    params = definition.with_ or {}
    found = params.get("action")
    action: dict[str, Any] = found if isinstance(found, dict) else {}
    mark = definition.checkpoint if isinstance(definition.checkpoint, CheckpointMark) else None
    return CheckpointEntry(
        test_id=test.definition.id,
        test_name=test.name,
        phase=str(path[0]),
        position="/".join(str(segment) for segment in path),
        step_id=definition.id,
        uses=definition.uses,
        direction=checkpoint.direction,
        kind=checkpoint.kind,
        via=checkpoint.via,
        name=_text(definition.name),
        label=_text(mark.label if mark else None) or _text(action.get("label")),
        description=_text(mark.description if mark else None) or _text(action.get("description")),
        timeout_s=_seconds(params.get("timeout_s", _default_timeout(definition.uses))),
        conditional=conditional,
        repeated=repeated,
    )


def _definition(raw: Any) -> StepDefinition | None:
    """A carried step as a definition; ``None`` for one that is not a step at all."""
    if isinstance(raw, StepDefinition):
        return raw
    try:
        return StepDefinition.model_validate(raw)
    except ValidationError:
        return None


def _default_timeout(uses: str) -> Any:
    """The step's own default ``timeout_s``, for a test that gives none."""
    params_model = getattr(StepRegistry.get_any(uses), "params_model", None)
    field = getattr(params_model, "model_fields", {}).get("timeout_s")
    return None if field is None else field.default


def _text(value: Any) -> str | None:
    """A string to show, or ``None`` when there is none or it is still a template."""
    if not isinstance(value, str) or not value or _TEMPLATE in value:
        return None
    return value


def _seconds(value: Any) -> int | None:
    """Whole seconds from a number or a number-like string; ``None`` otherwise."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            return None
    if isinstance(value, int | float) and float(value).is_integer():
        return int(value)
    return None
