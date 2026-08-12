#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). 
## It was reviewed and tested by a human committer.

"""Abstract base class for all steps and the @step auto-registration decorator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Optional, TypeVar, Union

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
    def of(cls, document: Any) -> Optional["StepPayload"]:
        """Bind a document a counterpart sent, keeping "nothing" as nothing.

        Steps whose output *is* a document defined elsewhere — a DCAT catalog,
        an AAS descriptor, an EDR data address — return it through here.  An
        absent document stays ``None`` rather than becoming an empty object,
        which is the difference between "the provider answered with nothing"
        and "the provider answered with {}".
        """
        return None if document is None else cls.model_validate(document)


RootT = TypeVar("RootT")


class StepValue(RootModel[RootT], Generic[RootT]):
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


class StepExports(BaseModel):
    """Context variables a step publishes for later steps to read.

    A step's return value is only half of what it produces: steps also hand
    data to the rest of the script through context variables, and until those
    are declared here that half of the interface is invisible.  Field names are
    the variable names, so they must match the constants in
    ``syntax.context_vars``.

    A field left ``None`` is not published, which is how a best-effort export
    stays absent rather than being written as null.

    Variables are published under each field's alias when it has one, so a
    field can carry ``alias=SOME_CONTEXT_VAR`` and let the constant stay the
    single source of truth for the name.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StepContract(BaseModel):
    """Machine-readable description of a step's declared interface.

    Produced by :meth:`BaseStep.describe` for documentation generation and
    script validation.  ``exports_schema`` is ``None`` when the step publishes
    no context variables; the other two are always present, because every step
    declares its inputs and its output.
    """

    step_type: str = ""
    description: str = ""
    params_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    exports_schema: Optional[dict] = None


ParamsT = TypeVar("ParamsT")
PayloadT = TypeVar("PayloadT")


class StepOutput(Generic[PayloadT]):
    """Structured output of a step execution.

    ``value`` is what assertions and ``returns:`` read; ``exports`` is what the
    step publishes into the run context for later steps.  Returning exports
    here — rather than calling ``context.set_variable`` inside ``execute`` — is
    what keeps them part of the declared contract.
    """

    __slots__ = ("value", "request", "response", "exports")

    def __init__(
        self,
        value: Any = None,
        request: Optional[HttpRequest] = None,
        response: Optional[HttpResponse] = None,
        exports: Optional[StepExports] = None,
    ):
        self.value = value
        self.request = request
        self.response = response
        self.exports = exports


class BaseStep(ABC, Generic[ParamsT, PayloadT]):
    """Abstract base class for all testlab steps.

    Subclasses implement ``execute`` and are registered via the ``@step``
    decorator from ``scripting.registry``.

    A step declares its interface by parameterising the base class and pointing
    the two model attributes at the declaring models::

        class GenerateBpnParams(StepParams):
            prefix: Literal["BPNL", "BPNS", "BPNA"] = "BPNL"

        class GenerateBpnOutput(StepPayload):
            bpn: str

        @step("util/generate_bpn")
        class GenerateBpnStep(BaseStep[GenerateBpnParams, GenerateBpnOutput]):
            params_model = GenerateBpnParams
            output_model = GenerateBpnOutput

    The runner calls :meth:`invoke`, which validates the raw ``with:`` mapping
    into ``params_model`` before ``execute`` runs and serialises the payload
    back to plain JSON data afterwards.

    Both models are mandatory, and the class body is where that is checked: a
    subclass that does not set them fails at import, not at registration or on
    the first run.  There is therefore no such thing as a step whose interface
    is undocumented.  A step that produces nothing declares that too, with
    ``output_model = NoOutput``.
    """

    #: Canonical step key from the ``@step`` decorator (e.g. ``util/generate_bpn``).
    step_type: ClassVar[str] = ""
    #: Input contract — the keys this step accepts under ``with:``.
    params_model: ClassVar[type[StepParams]]
    #: Output contract — a :class:`StepPayload` for an object, a
    #: :class:`StepValue` for a bare value.
    output_model: ClassVar[type[Union[StepPayload, StepValue]]]
    #: Context variables published by this step; ``None`` means it publishes none.
    exports_model: ClassVar[Optional[type[StepExports]]] = None

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
        context: "StepContext",
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
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[Any]:
        """Bind *raw_params* to the input contract, run the step, bind the output.

        This is the entry point the runner uses; ``execute`` is the part a step
        implements.
        """
        output = await self.execute(self.bind_params(raw_params), context, definition)
        self.publish_exports(output, context)
        return self.bind_output(output)

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
    def publish_exports(cls, output: StepOutput[Any], context: "StepContext") -> None:
        """Write the step's declared exports into the run context.

        Fields that are ``None`` are skipped, so a best-effort export that could
        not be derived leaves the variable unset rather than nulled.
        """
        exports = output.exports
        if exports is None:
            return
        if cls.exports_model is not None and not isinstance(exports, cls.exports_model):
            exports = cls.exports_model.model_validate(exports)
        for name, value in exports.model_dump(by_alias=True).items():
            if value is not None:
                context.set_variable(name, value)

    @classmethod
    def describe(cls) -> StepContract:
        """Return this step's interface as JSON Schema, for docs and validation."""
        return StepContract(
            step_type=cls.step_type,
            description=(cls.__doc__ or "").strip(),
            params_schema=cls.params_model.model_json_schema(),
            output_schema=cls.output_model.model_json_schema(),
            exports_schema=cls.exports_model.model_json_schema() if cls.exports_model else None,
        )

    async def cleanup(self, context: "StepContext") -> None:
        """Optional cleanup hook executed after the step's script finishes."""


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


def _dump_payload(payload: Union[StepPayload, StepValue]) -> Any:
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
