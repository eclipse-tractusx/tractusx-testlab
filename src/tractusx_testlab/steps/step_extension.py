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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Step parameter extensions — experimental ``with:`` keys added to an existing step.

**Experimental.** An extension can give a core step extra ``with:`` parameters
without touching the step. They are written exactly like a step's own
parameters, but the model and the behaviour behind them live in the
extension's package::

    # tractusx_testlab/extensions/<name>/<what_it_adds>.py — see labs/dataplane_retry.py
    class RetryOnParams(ExtensionParams):
        retry_on: list[int] = Field(default_factory=list, description="…")


    @extends("connector/dataplane/http_request", extension="<name>")
    class RetryOn(StepExtension[RetryOnParams]):
        params_model = RetryOnParams

        async def around(self, params, context, definition, proceed):
            ...
            return await proceed()

A test then writes ``retry_on:`` under the step's ``with:`` like any other key.
The runner takes the extension's keys out before the step binds its own
parameters, binds them to ``params_model``, and runs the step through
``around``. An extension whose keys the test did not write does not run.

The compiler refuses the keys in a TCK that did not enable the extension
(``extensions: [<name>]``); see :mod:`tractusx_testlab.compiler.validation._extension_gate`.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import ValidationError

from tractusx_testlab.extensions import EXTENSIONS
from tractusx_testlab.models.primitives.exceptions import EngineError
from tractusx_testlab.steps.step_contract import StepOutput, StepParams
from tractusx_testlab.syntax import diagnostics

if TYPE_CHECKING:
    from tractusx_testlab.models import StepDefinition
    from tractusx_testlab.player.execution.context import StepContext
    from tractusx_testlab.steps.step_contract import BaseStep

#: Runs the step — and every extension nearer to it — and returns its output.
Proceed = Callable[[], Awaitable[StepOutput[Any]]]

#: Step id -> the parameter extensions registered for it, in registration order.
_BY_STEP: dict[str, list[type[StepExtension[Any]]]] = {}


class ExtensionParams(StepParams):
    """The ``with:`` keys an extension adds to a step. Unknown keys are rejected."""


class StepExtension[ParamsT: ExtensionParams](ABC):
    """Experimental parameters and behaviour added to one existing step.

    ``around`` receives the bound parameters and ``proceed``, which runs the
    step and returns its output (already published). It may do work before or
    after, call ``proceed`` again to retry, raise to fail the step, or inspect
    the output. It must not replace the output: the step has published it by
    the time ``proceed`` returns.
    """

    #: The step id this extends, stamped by :func:`extends`.
    step_type: ClassVar[str] = ""
    #: The extension the keys belong to, stamped by :func:`extends`.
    extension: ClassVar[str] = ""
    #: The ``with:`` keys this adds, one field each.
    params_model: ClassVar[type[ExtensionParams]]

    async def around(
        self,
        params: ParamsT,
        context: StepContext,
        definition: StepDefinition,
        proceed: Proceed,
    ) -> StepOutput[Any]:
        """Run the step. Override to add behaviour; the default only passes through."""
        return await proceed()

    @classmethod
    def param_keys(cls) -> frozenset[str]:
        """Every spelling a test may write one of this extension's keys with."""
        return frozenset(
            key
            for name, field in cls.params_model.model_fields.items()
            for key in (name, field.alias)
            if key
        )

    @classmethod
    def bind_params(cls, written: dict[str, Any]) -> ExtensionParams:
        try:
            return cls.params_model.model_validate(written)
        except ValidationError as exc:
            raise ValueError(
                f"Invalid parameters of the experimental extension '{cls.extension}' on "
                f"step '{cls.step_type}':\n"
                f"{diagnostics.render(exc, model=cls.params_model, data=written)}"
            ) from exc


def extends(
    step_type: str, *, extension: str
) -> Callable[[type[StepExtension[Any]]], type[StepExtension[Any]]]:
    """Register a :class:`StepExtension` for *step_type* under *extension*.

    Refused at import when *extension* is not a registered extension, or when
    the class declares no ``params_model`` — there is no such thing as an
    extension parameter that is not documented.
    """

    def decorator(cls: type[StepExtension[Any]]) -> type[StepExtension[Any]]:
        if extension not in EXTENSIONS:
            raise TypeError(
                f"{cls.__name__} extends '{step_type}' for extension '{extension}', which is "
                f"not registered in tractusx_testlab.extensions.EXTENSIONS."
            )
        params_model = getattr(cls, "params_model", None)
        if not (isinstance(params_model, type) and issubclass(params_model, ExtensionParams)):
            raise TypeError(f"{cls.__name__} must set params_model to an ExtensionParams subclass.")
        cls.step_type, cls.extension = step_type, extension
        _BY_STEP.setdefault(step_type, []).append(cls)
        return cls

    return decorator


def extensions_for(step_type: str) -> list[type[StepExtension[Any]]]:
    """The parameter extensions registered for *step_type*."""
    return list(_BY_STEP.get(step_type, ()))


def unregister(cls: type[StepExtension[Any]]) -> None:
    """Remove *cls* from the registry — for tests that register a throwaway extension."""
    registered = _BY_STEP.get(cls.step_type, [])
    if cls in registered:
        registered.remove(cls)


def colliding_keys(step_cls: type[BaseStep[Any, Any]]) -> set[str]:
    """Keys an extension adds that the step, or another extension, already declares."""
    seen = {
        key
        for name, f in step_cls.params_model.model_fields.items()
        for key in (name, f.alias)
        if key
    }
    collisions: set[str] = set()
    for extension_cls in extensions_for(step_cls.step_type):
        collisions |= seen & extension_cls.param_keys()
        seen |= extension_cls.param_keys()
    return collisions


async def invoke_extended(
    step: BaseStep[Any, Any],
    raw_params: dict[str, Any],
    context: StepContext,
    definition: StepDefinition,
) -> StepOutput[Any]:
    """Run *step* with the parameter extensions whose keys *raw_params* contains.

    Each extension's keys are taken out before the step binds its own, so the
    step never sees them; the extensions then wrap the step, the first
    registered outermost.
    """
    extensions = extensions_for(step.step_type)
    if not extensions:
        return await step.invoke(raw_params, context, definition)
    if colliding := colliding_keys(type(step)):
        raise EngineError(
            f"Extensions on step '{step.step_type}' declare keys it already has: "
            f"{', '.join(sorted(colliding))}."
        )

    core = dict(raw_params)
    bound: list[tuple[StepExtension[Any], ExtensionParams]] = []
    for extension_cls in extensions:
        written = {key: core.pop(key) for key in extension_cls.param_keys() & core.keys()}
        if written:
            bound.append((extension_cls(), extension_cls.bind_params(written)))

    async def run_step() -> StepOutput[Any]:
        return await step.invoke(core, context, definition)

    proceed: Proceed = run_step
    for instance, params in reversed(bound):
        proceed = _wrap(instance, params, context, definition, proceed)
    return await proceed()


def _wrap(
    instance: StepExtension[Any],
    params: ExtensionParams,
    context: StepContext,
    definition: StepDefinition,
    inner: Proceed,
) -> Proceed:
    async def proceed() -> StepOutput[Any]:
        return await instance.around(params, context, definition, inner)

    return proceed
