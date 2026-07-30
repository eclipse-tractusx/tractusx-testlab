#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Variable export/import steps for cross-script variable propagation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_EXPORT_NAMESPACE = "!"


@step("util/export_env")
class ExportVariableStep(BaseStep):
    """Mark a context variable for export to downstream scripts.

    Stores the variable under ``!{script_name}:{var_name}`` so that
    ``import_variable`` steps in later scripts can retrieve it.

    Params:
        name (str): The variable name to export from the current context.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition
    ) -> StepOutput:
        var_name: str = params["name"]
        value = context.get_variable(var_name)

        script_name = context.job.current_script or "unknown"
        export_key = f"{_EXPORT_NAMESPACE}{script_name}:{var_name}"
        context.set_variable(export_key, value)

        logger.info("Exported variable %s as %s", var_name, export_key)
        return StepOutput(value=value)


@step("util/import_env")
class ImportVariableStep(BaseStep):
    """Import a variable exported by a previous script.

    Looks up ``!{test}:{select}`` in the shared context and stores
    it under ``store_in_variable`` (defaults to ``select``).

    Params:
        test (str): Name of the source script that exported the variable.
        select (str): Name of the exported variable.
        store_in_variable (str, optional): Local variable name to store as.
            Defaults to the value of ``select``.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition
    ) -> StepOutput:
        source_test: str = params["test"]
        select: str = params["select"]
        store_as: str = params.get("store_in_variable", select)

        export_key = f"{_EXPORT_NAMESPACE}{source_test}:{select}"
        value = context.get_variable(export_key)

        if value is None:
            logger.warning(
                "Variable %s not found in exports from script '%s'",
                select, source_test,
            )

        context.set_variable(store_as, value)
        logger.info(
            "Imported %s from script '%s' as '%s'",
            select, source_test, store_as,
        )
        return StepOutput(value=value)
