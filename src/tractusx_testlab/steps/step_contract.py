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

"""Abstract base class for all steps and the @step auto-registration decorator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError

from tractusx_testlab.models import (
    HttpRequest,
    HttpResponse,
    StepDefinition,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class StepParams(BaseModel):
    """Declared input contract of a step — one field per accepted ``with:`` key.

    Unknown keys are rejected.  A ``with:`` key the step does not declare is a
    mistake in the script — a typo, or a name from a revision that no longer
    exists — and silently dropping it is how a script comes to look like it
    configured something it never configured.  Rejecting it surfaces the
    mistake at validation time, where the author can still see it.

    This is why the engine and the IDE have to agree on parameter names down to
    the spelling: there is no longer a spelling that is merely ignored.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StepPayload(BaseModel):
    """Declared output contract of a step — one field per key of ``StepOutput.value``.

    Assertions and ``returns:`` navigate the output by dot-path, so every field
    declared here is part of the step's public surface: renaming one breaks the
    scripts that read it.
    """

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def of(cls, document: Any) -> Self | None:
        """Bind a document a counterpart sent, keeping "nothing" as nothing.

        Steps whose output *is* a document defined elsewhere — a DCAT catalog,
        an AAS descriptor, an EDR data address — return it through here.  An
        absent document stays ``None`` rather than becoming an empty object,
        which is the difference between "the provider answered with nothing"
        and "the provider answered with {}".

        Typed as ``Self`` so ``DataAddressPayload.of(...)`` is a data address and
        not a bare :class:`StepPayload` — the field it lands in declares the
        specific type, and every call site was quietly wider than its target.
        """
        return None if document is None else cls.model_validate(document)


RootT = TypeVar("RootT")


class StepValue[RootT](RootModel[RootT]):
    """Declared output contract of a step whose value is a bare value, not an object.

    ``util/base64`` returns a string and ``util/json_path_extract`` returns
    whatever the path pointed at.  Wrapping those in an object to satisfy
    :class:`StepPayload` would change the shape every existing script reads, so
    they declare the type of the bare value instead::

        class Base64Output(StepValue[str]):
            \"\"\"The encoded or decoded string.\"\"\"

    The docstring is the field description — there is only one value to
    describe, so there is nowhere else to put it.
    """


class StepContract(BaseModel):
    """Machine-readable description of a step's declared interface.

    Produced by :meth:`BaseStep.describe` for documentation generation and
    script validation.  Both schemas are always present, because every step
    declares its inputs and its output.
    """

    step_type: str = ""
    description: str = ""
    params_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)


ParamsT = TypeVar("ParamsT")
PayloadT = TypeVar("PayloadT")


class StepOutput[PayloadT]:
    """Structured output of a step execution.

    ``value`` is what assertions and ``returns:`` read, and it is also what the
    step publishes into the run context: every top-level field of the output is
    written as a context variable after the step runs, so a step's return value
    is the whole of its interface — there is no separate export channel.
    """

    __slots__ = ("request", "response", "value")

    def __init__(
        self,
        value: Any = None,
        request: HttpRequest | None = None,
        response: HttpResponse | None = None,
    ):
        self.value = value
        self.request = request
        self.response = response


class BaseStep[ParamsT, PayloadT](ABC):
    """Abstract base class for all testlab steps.

    Subclasses implement ``execute`` and are registered via the ``@step``
    decorator from ``scripting.registry``.

    A step declares its interface by parameterising the base class and pointing
    the two model attributes at the declaring models::

        class ExtractDatasetParams(StepParams):
            datasets: list[dict]
            dct_type: str

        class ExtractDatasetOutput(StepPayload):
            dataset: dict | None = None
            asset_id: str | None = None

        @step("connector/consumer/extract_dataset")
        class ExtractDatasetStep(BaseStep[ExtractDatasetParams, ExtractDatasetOutput]):
            params_model = ExtractDatasetParams
            output_model = ExtractDatasetOutput

    The runner calls :meth:`invoke`, which validates the raw ``with:`` mapping
    into ``params_model`` before ``execute`` runs and serialises the payload
    back to plain JSON data afterwards.

    Both models are mandatory, and the class body is where that is checked: a
    subclass that does not set them fails at import, not at registration or on
    the first run.  There is therefore no such thing as a step whose interface
    is undocumented.  A step that produces nothing declares that too, with
    ``output_model = NoOutput``.
    """

    #: Canonical step key from the ``@step`` decorator (e.g. ``util/generate_uuid``).
    step_type: ClassVar[str] = ""
    #: Input contract — the keys this step accepts under ``with:``.
    params_model: ClassVar[type[StepParams]]
    #: Output contract — a :class:`StepPayload` for an object, a
    #: :class:`StepValue` for a bare value.
    output_model: ClassVar[type[StepPayload | StepValue]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Refuse to define a step that does not say what comes in and what goes out.

        Enforcing here rather than in ``@step`` means the two ways of getting a
        step into the registry — the decorator and a direct
        ``StepRegistry.register`` call — cannot diverge, and an undeclared step
        never gets far enough to be imported.
        """
        super().__init_subclass__(**kwargs)
        _require_declared_contract(cls)

    @abstractmethod
    async def execute(
        self,
        params: ParamsT,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[PayloadT]:
        """Run the step logic.

        Args:
            params: Validated ``params_model`` instance.
            context: Runtime context providing services, variables, job memory.
            definition: The raw step definition.

        Returns:
            StepOutput with optional value, request, and response.
        """
        raise NotImplementedError

    async def invoke(
        self,
        raw_params: dict,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[Any]:
        """Bind *raw_params* to the input contract, run the step, bind the output.

        This is the entry point the runner uses; ``execute`` is the part a step
        implements.
        """
        output = self.bind_output(
            await self.execute(self.bind_params(raw_params), context, definition)
        )
        self.publish_output(output, context)
        return output

    @classmethod
    def bind_params(cls, raw_params: dict) -> Any:
        """Validate the resolved YAML parameters against ``params_model``."""
        try:
            return cls.params_model.model_validate(raw_params)
        except ValidationError as exc:
            raise ValueError(
                f"Invalid parameters for step '{cls.step_type or cls.__name__}': "
                f"{_format_validation_errors(exc)}"
            ) from exc

    @classmethod
    def bind_output(cls, output: StepOutput[Any]) -> StepOutput[Any]:
        """Serialise the declared payload back to plain data.

        Assertions, ``returns:`` extraction, and the JSON report all navigate
        ``StepOutput.value`` as nested dicts/lists, so the model is dumped here
        rather than leaking a Pydantic instance downstream.

        ``execute`` must return the declared model, not raw data that happens to
        fit it — a step whose output is a document from a counterpart binds it
        with :meth:`StepPayload.of`.  ``None`` stays ``None``: that is a step
        reporting it produced nothing on this path, which is different from
        producing an empty payload.

        Only what the step actually produced is serialised — see
        :func:`_dump_payload`.
        """
        value = output.value
        if value is None:
            return output
        if not isinstance(value, cls.output_model):
            raise TypeError(
                f"Step '{cls.step_type or cls.__name__}' returned "
                f"{type(value).__name__}, but declares output_model="
                f"{cls.output_model.__name__}. Build the declared model — "
                f"{cls.output_model.__name__}.of(document) binds a document that "
                f"came from a counterpart."
            )
        output.value = _dump_payload(value)
        return output

    @classmethod
    def publish_output(cls, output: StepOutput[Any], context: StepContext) -> None:
        """Write every top-level field of the step's output into the run context.

        A step publishes all of its return outputs, always: each key of the
        serialised output value becomes a context variable of the same name, so
        a later step reads a field exactly as the producing step declared it.
        Keys whose value is ``None`` are skipped — a field a step could not
        derive leaves the variable unset rather than nulling out what an
        earlier step published.

        A bare value (:class:`StepValue`) that is not an object has no field
        names to publish under; it stays reachable through assertions and
        ``returns:``.
        """
        value = output.value
        if not isinstance(value, dict):
            return
        for name, item in value.items():
            if item is not None:
                context.set_variable(name, item)

    @classmethod
    def describe(cls) -> StepContract:
        """Return this step's interface as JSON Schema, for docs and validation."""
        return StepContract(
            step_type=cls.step_type,
            description=(cls.__doc__ or "").strip(),
            params_schema=cls.params_model.model_json_schema(),
            output_schema=cls.output_model.model_json_schema(),
        )

    async def cleanup(self, context: StepContext) -> None:  # noqa: B027
        """Release anything this step holds, after its script finishes.

        Deliberately concrete and empty rather than abstract: most steps have
        nothing to release, and making every one of them write an empty override
        would be noise that hides the few that do.
        """


def _require_declared_contract(cls: type[BaseStep]) -> None:
    """Check that *cls* declares both halves of its interface, with the right kinds.

    The message names the fix rather than the rule: whoever hits this is part
    way through writing a step, not auditing the architecture.
    """
    params_model = getattr(cls, "params_model", None)
    output_model = getattr(cls, "output_model", None)

    if not (isinstance(params_model, type) and issubclass(params_model, StepParams)):
        raise TypeError(
            f"Step '{cls.__name__}' must set params_model to a StepParams subclass "
            f"declaring the keys it accepts under 'with:'."
        )
    if not (
        isinstance(output_model, type)
        and issubclass(output_model, (StepPayload, StepValue))
    ):
        raise TypeError(
            f"Step '{cls.__name__}' must set output_model to a StepPayload subclass "
            f"(an object) or a StepValue subclass (a bare value, NoOutput for none)."
        )


def _dump_payload(payload: StepPayload | StepValue) -> Any:
    """Serialise a declared payload to the plain JSON data the rest of the run sees.

    ``exclude_unset`` is the rule: the output carries exactly what the step
    produced.  A pass-through document like a provider's catalog keeps the keys
    the provider sent and gains no ``"@type": null`` for the ones it omitted,
    while a field a step deliberately set to ``None`` still shows up as null
    because the step said so.  The cost is that a payload must pass every field
    it means to publish — a field left to its default is absent from the output.
    """
    if isinstance(payload, StepValue):
        # A bare value has no fields to filter, and its content is already the
        # plain data a script reads — dumping it in JSON mode would coerce
        # whatever a provider sent.
        return payload.root
    return payload.model_dump(mode="json", by_alias=True, exclude_unset=True)


def _format_validation_errors(exc: ValidationError) -> str:
    """Render Pydantic errors as a compact ``field: message`` list."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
        for error in exc.errors()
    )
