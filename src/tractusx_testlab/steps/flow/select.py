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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""``flow/select`` — the run stops and the operator chooses one of the options.

:class:`SelectionStep` is the shared half: it puts a list of options to the
operator, waits, and hands the chosen one to the step that asked. ``flow/select``
takes its options as they are written under ``with: options``; a step built on
it (``connector/datasets/select``) derives them from what an earlier step
returned and says how a host should show them (``presentation``).
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import StepDefinition, StepExecutionError, WaitAction
from tractusx_testlab.models.runtime.selection import (
    Selection,
    SelectionOption,
    SelectionPresentation,
)
from tractusx_testlab.steps.flow._selection_wait import await_choice
from tractusx_testlab.steps.step_contract import (
    BaseStep,
    StepOutput,
    StepParams,
    StepPayload,
    StepValue,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

SelectedBy = Literal["operator", "single"]


class SelectionParams(StepParams):
    """What every selection step accepts besides its options."""

    auto_select_single: bool = Field(
        default=True,
        description=(
            "Take the only option without asking when there is just one. "
            "False asks the operator even then."
        ),
    )
    timeout_s: float = Field(
        default=300.0, gt=0, description="Seconds to wait for the choice before failing."
    )
    action: WaitAction | None = Field(
        default=None,
        description=(
            "What the choice is for, shown to the operator with the options: 'label', "
            "'description', 'recommendation' and 'fields'."
        ),
    )


class SelectionOutput(StepPayload):
    """What every selection step returns besides the chosen option."""

    selected_by: SelectedBy = Field(
        description="'operator' when the operator chose, 'single' when it was the only option."
    )


class SelectionStep[P: SelectionParams, O: SelectionOutput](BaseStep[P, O]):
    """Put options to the operator and go on with the one chosen.

    No option fails the step. One is taken without asking while
    ``auto_select_single`` holds. Otherwise the run waits up to ``timeout_s``
    for the answer — the clock stopped while paused.
    """

    params_model: ClassVar[type[StepParams]] = SelectionParams
    output_model: ClassVar[type[StepPayload | StepValue]] = SelectionOutput
    #: How a host shows the options.
    presentation: ClassVar[SelectionPresentation] = "dropdown"

    @abstractmethod
    def options(self, params: P) -> list[SelectionOption]:
        """The options to put to the operator; each ``id`` unique."""

    @abstractmethod
    def chosen(self, params: P, option: SelectionOption, selected_by: SelectedBy) -> O:
        """The step's output for *option*."""

    async def execute(
        self, params: P, context: StepContext, definition: StepDefinition
    ) -> StepOutput[O]:
        options = self.options(params)
        if not options:
            raise StepExecutionError(self.step_type, "there is nothing to choose from.")
        if len(options) == 1 and params.auto_select_single:
            return StepOutput(value=self.chosen(params, options[0], "single"))
        selection = Selection(presentation=self.presentation, options=options, action=params.action)
        logger.info("Asking the operator to choose 1 of %d options", len(options))
        option, _ = await await_choice(context, definition, selection, params.timeout_s)
        return StepOutput(value=self.chosen(params, option, "operator"))


class SelectOption(BaseModel):
    """One option of ``flow/select``."""

    value: str = Field(min_length=1, description="What the step returns when chosen; unique.")
    label: str | None = Field(default=None, description="What the operator sees; 'value' if unset.")
    description: str | None = Field(default=None, description="A line more about the option.")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Anything else to show beside it, and to return."
    )


class SelectParams(SelectionParams):
    """Input contract of ``flow/select``."""

    options: list[SelectOption] = Field(
        min_length=1,
        description="The options, as plain values or as {value, label, description, details}.",
    )

    @field_validator("options", mode="before")
    @classmethod
    def _plain_values(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [{"value": entry} if isinstance(entry, str) else entry for entry in value]
        return value

    @model_validator(mode="after")
    def _unique_values(self) -> SelectParams:
        values = [option.value for option in self.options]
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise ValueError(f"option values have to be unique: {', '.join(duplicates)}")
        return self


class SelectOutput(SelectionOutput):
    """Output contract of ``flow/select``."""

    value: str = Field(description="The chosen option's value.")
    label: str = Field(description="The chosen option's label.")
    details: dict[str, Any] = Field(
        default_factory=dict, description="The chosen option's details."
    )


@step("flow/select")
class SelectStep(SelectionStep[SelectParams, SelectOutput]):
    """Let the operator choose one of a list of values — a dropdown in the host's UI."""

    params_model = SelectParams
    output_model = SelectOutput

    def options(self, params: SelectParams) -> list[SelectionOption]:
        return [
            SelectionOption(
                id=option.value,
                label=option.label or option.value,
                description=option.description,
                details=option.details,
            )
            for option in params.options
        ]

    def chosen(
        self, params: SelectParams, option: SelectionOption, selected_by: SelectedBy
    ) -> SelectOutput:
        return SelectOutput(
            value=option.id, label=option.label, details=option.details, selected_by=selected_by
        )
