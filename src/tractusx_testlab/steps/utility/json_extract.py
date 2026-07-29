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
import re
from typing import TYPE_CHECKING

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._checks.extraction import (
    _PREDICATE_RE,
    _find_by_predicate,
    _split_path,
)
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


def _resolve_predicate(current: object, segment: str, match: re.Match) -> object:
    """Resolve a ``name[key=value]`` segment, selecting the first matching element."""
    name, pred_key, pred_val = match.group(1), match.group(2), match.group(3)
    if isinstance(current, list):
        # Step over an intermediate array: apply the predicate to each element.
        containers = [
            item.get(name) for item in current
            if isinstance(item, dict) and isinstance(item.get(name), list)
        ]
        container = [entry for sublist in containers for entry in sublist]
    else:
        container = current.get(name) if isinstance(current, dict) else None
    if not isinstance(container, list):
        raise TypeError(
            f"Cannot filter '{name}' — expected a list, got "
            f"{type(container).__name__}"
        )
    found = _find_by_predicate(container, pred_key, pred_val)
    if found is None:
        raise KeyError(
            f"No element in '{name}' where {pred_key}={pred_val} (segment '{segment}')"
        )
    return found


def _extract_by_path(data: object, path: str) -> object:
    """Walk a dot-separated path through nested dicts/lists.

    Supports ``key.0.nested`` where numeric segments index into lists, and
    ``key[field=value].nested`` which selects the first list element whose
    *field* equals *value*.  Dots inside a predicate are not separators, so
    values such as ``[interface='SUBMODEL-VALUE-3.1']`` survive intact.

    Raises:
        KeyError: When a dict key is missing or a predicate matches nothing.
        IndexError: When a list index is out of range.
        TypeError: When traversal hits a non-subscriptable value.
    """
    current = data
    for segment in _split_path(path):
        predicate = _PREDICATE_RE.match(segment)
        if predicate:
            current = _resolve_predicate(current, segment, predicate)
            continue
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


@step("util/json_path_extract", aliases=["json_path_extract"])
class JsonPathExtractStep(BaseStep):
    """Extract a value from a context variable using dot-notation path.

    Params:
        source: Either the *name* of the context variable holding the JSON/dict
            data (e.g. ``response_body``), or the data itself when a ``${{ }}``
            expression is passed (it resolves before the step runs).
        path (str): Dot-notation path to the desired value (e.g. ``datasets.0.id``).

    Output:
        The extracted value (stored via ``store_in_memory``).
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput:
        source = params.get("source")
        if source is None:
            source = params.get("variable")
        if source is None:
            raise KeyError("json_path_extract requires either 'source' or 'variable' param")
        path = params["path"]

        # ``source`` is normally a variable name (a string) that we look up.  But
        # a ``${{ }}`` expression resolves to the value itself before the step
        # runs, so a dict/list arriving here is the data, not a name — use it
        # directly rather than attempting an unhashable dict lookup.
        if isinstance(source, str):
            data = context.get_variable(source)
            if data is None:
                raise KeyError(f"Context variable '{source}' not found")
        else:
            data = source

        extracted = _extract_by_path(data, path)
        source_label = source if isinstance(source, str) else f"<{type(source).__name__}>"
        logger.debug("Extracted '%s' from '%s': %s", path, source_label, type(extracted).__name__)

        store_in = params.get("store_in_variable")
        if store_in:
            context.set_variable(store_in, extracted)
            logger.debug("Stored extracted value in variable '%s'", store_in)

        return StepOutput(value=extracted)
