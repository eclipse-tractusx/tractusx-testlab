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

"""Every step must declare what comes in and what comes out.

There is no opt-out and no allowlist.  Defining a ``BaseStep`` subclass without
``params_model`` and ``output_model`` raises at class-definition time, so an
undeclared step cannot be imported, let alone registered.  These tests check the
shape of what every step declared, and that the refusal actually bites — both on
the way in (a class that declares nothing) and on the way out (a step that
returns raw data instead of its declared model).
"""

from __future__ import annotations

import pytest

from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps.shared_models import NoOutput
from tractusx_testlab.steps.step_contract import (
    BaseStep,
    StepOutput,
    StepParams,
    StepPayload,
    StepValue,
)

_ALL_STEP_TYPES = sorted(StepRegistry.list_step_types())


def _step_class(step_type: str) -> type[BaseStep]:
    step_cls = StepRegistry.get_any(step_type)
    assert step_cls is not None, f"'{step_type}' is listed but not resolvable"
    return step_cls


class TestDeclaredSteps:
    """Rules every step obeys."""

    @pytest.mark.parametrize("step_type", _ALL_STEP_TYPES)
    def test_step_declares_its_inputs(self, step_type: str) -> None:
        params_model = _step_class(step_type).params_model
        assert issubclass(params_model, StepParams)

    @pytest.mark.parametrize("step_type", _ALL_STEP_TYPES)
    def test_step_declares_its_output(self, step_type: str) -> None:
        output_model = _step_class(step_type).output_model
        assert issubclass(output_model, (StepPayload, StepValue))

    @pytest.mark.parametrize("step_type", _ALL_STEP_TYPES)
    def test_contract_is_describable(self, step_type: str) -> None:
        contract = _step_class(step_type).describe()
        assert contract.step_type == step_type
        assert contract.description
        assert contract.params_schema
        assert contract.output_schema

    @pytest.mark.parametrize("step_type", _ALL_STEP_TYPES)
    def test_registry_stamps_the_canonical_step_type(self, step_type: str) -> None:
        assert _step_class(step_type).step_type == step_type

    @pytest.mark.parametrize("step_type", _ALL_STEP_TYPES)
    def test_step_rejects_a_with_key_it_did_not_declare(self, step_type: str) -> None:
        """C47 — an undeclared ``with:`` key is a script mistake, not a no-op.

        A step that loosened this back to ``extra="allow"`` would silently drop
        the key, and the script would read as if it had configured something it
        never configured.
        """
        assert _step_class(step_type).params_model.model_config["extra"] == "forbid"

    def test_the_registry_is_not_empty(self) -> None:
        assert _ALL_STEP_TYPES


class _Params(StepParams):
    """Inputs of the throwaway steps below."""


class _Output(StepPayload):
    """Output of the throwaway steps below."""

    ok: bool = True


class TestDeclarationIsMandatory:
    """A step that does not declare its interface cannot be defined at all."""

    def test_a_step_without_params_is_refused(self) -> None:
        with pytest.raises(TypeError, match="must set params_model"):

            class _NoParams(BaseStep):
                output_model = _Output

                async def execute(self, params, context, definition) -> StepOutput:
                    return StepOutput()

    def test_a_step_without_an_output_is_refused(self) -> None:
        with pytest.raises(TypeError, match="must set output_model"):

            class _NoOutput(BaseStep):
                params_model = _Params

                async def execute(self, params, context, definition) -> StepOutput:
                    return StepOutput()

    def test_a_model_of_the_wrong_kind_is_refused(self) -> None:
        with pytest.raises(TypeError, match="must set output_model"):

            class _WrongOutput(BaseStep):
                params_model = _Params
                output_model = _Params  # inputs are not an output contract

                async def execute(self, params, context, definition) -> StepOutput:
                    return StepOutput()

    def test_producing_nothing_is_a_declaration_too(self) -> None:
        """``NoOutput`` says "this step produces nothing" — it is not a missing model."""

        class _NoValue(BaseStep[_Params, NoOutput]):
            """A step that acts and returns nothing."""

            params_model = _Params
            output_model = NoOutput

            async def execute(self, params, context, definition) -> StepOutput:
                return StepOutput(value=NoOutput(None))

        assert _NoValue.describe().output_schema

    def test_a_subclass_inherits_its_parents_declaration(self) -> None:
        """Specialising a step is still declaring one — the models come along."""

        class _Base(BaseStep[_Params, _Output]):
            """A declared step."""

            params_model = _Params
            output_model = _Output

            async def execute(self, params, context, definition) -> StepOutput:
                return StepOutput(value=_Output(ok=True))

        class _Specialised(_Base):
            """Narrows the behaviour, keeps the contract."""

        assert _Specialised.output_model is _Output


class _DeclaredStep(BaseStep[_Params, _Output]):
    """A step used to exercise output binding."""

    params_model = _Params
    output_model = _Output

    async def execute(self, params, context, definition) -> StepOutput:
        return StepOutput()


class TestOutputMustBeTheDeclaredModel:
    """``execute`` returns the declared model, not raw data that happens to fit."""

    def test_raw_data_is_refused_even_when_it_would_validate(self) -> None:
        with pytest.raises(TypeError, match="declares output_model=_Output"):
            _DeclaredStep.bind_output(StepOutput(value={"ok": True}))

    def test_the_declared_model_is_dumped_to_plain_data(self) -> None:
        bound = _DeclaredStep.bind_output(StepOutput(value=_Output(ok=False)))
        assert bound.value == {"ok": False}

    def test_none_stays_none(self) -> None:
        """ "Produced nothing on this path" is not the same as an empty payload."""
        assert _DeclaredStep.bind_output(StepOutput(value=None)).value is None

    def test_of_binds_a_counterparts_document(self) -> None:
        assert _Output.of({"ok": False}) == _Output(ok=False)

    def test_of_keeps_an_absent_document_absent(self) -> None:
        assert _Output.of(None) is None
