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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4).
## It was reviewed and tested by a human committer.

"""JSON path extraction step — extracts a value from a nested dict using dot-notation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


def _extract_by_path(data: object, path: str) -> object:
    """Walk a dot-separated path through nested dicts/lists.

    Supports ``key.0.nested`` where numeric segments index into lists.

    Raises:
        KeyError: When a dict key is missing.
        IndexError: When a list index is out of range.
        TypeError: When traversal hits a non-subscriptable value.
    """
    current = data
    for segment in path.split("."):
        # Handle bracket notation: [0], [1], etc.
        if segment.startswith("[") and segment.endswith("]"):
            segment = segment[1:-1]
        if isinstance(current, dict):
            current = current[segment]
        elif isinstance(current, (list, tuple)):
            current = current[int(segment)]
        else:
            raise TypeError(
                f"Cannot traverse into {type(current).__name__} with key '{segment}'"
            )
    return current


@step("util/json_path_extract")
class JsonPathExtractStep(BaseStep):
    """Extract a value from a context variable using dot-notation path.

    Params:
        source (str): Name of the context variable containing the JSON/dict data.
        path (str): Dot-notation path to the desired value (e.g. ``datasets.0.id``).

    Output:
        The extracted value (stored via ``store_in_memory``).
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition
    ) -> StepOutput:
        source_name = params.get("source") or params.get("variable")
        if source_name is None:
            raise KeyError("json_path_extract requires either 'source' or 'variable' param")
        path = params["path"]

        data = context.get_variable(source_name)
        if data is None:
            raise KeyError(f"Context variable '{source_name}' not found")

        extracted = _extract_by_path(data, path)
        logger.debug("Extracted '%s' from '%s': %s", path, source_name, type(extracted).__name__)

        store_in = params.get("store_in_variable")
        if store_in:
            context.set_variable(store_in, extracted)
            logger.debug("Stored extracted value in variable '%s'", store_in)

        return StepOutput(value=extracted)
