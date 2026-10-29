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

"""Which operations ``labs/http/api_sweep`` calls, and with what. **Experimental.**

An operation is planned when it passes every filter — listed in
``operations`` (when the list is given), tagged with one of ``tags`` (when
given), not in ``exclude``, and its method in ``methods``. A write (anything
but GET, HEAD, OPTIONS, TRACE) additionally needs ``include_writes: true``
*and* its own entry in ``operations``: a sweep never changes data by accident.

A planned operation is called when every required parameter and body has a
value, and skipped with the reason otherwise.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from tractusx_testlab.openapi.operations import Operation, OperationIndex


@dataclass(frozen=True, slots=True)
class PlannedCall:
    """One operation the sweep is about to call, or the reason it will not."""

    operation: Operation
    path_params: dict[str, Any]
    query: dict[str, Any]
    body: Any = None
    skipped: str = ""


def selected(
    index: OperationIndex,
    *,
    operations: list[str],
    tags: list[str],
    methods: list[str],
    exclude: list[str],
    include_writes: bool,
) -> tuple[list[Operation], list[tuple[Operation, str]]]:
    """The operations to plan, in document order, and the writes held back with why."""
    listed = {found.location for name in operations if (found := index.find(name)) is not None}
    excluded = {found.location for name in exclude if (found := index.find(name)) is not None}
    wanted_methods = {method.upper() for method in methods}
    wanted_tags = set(tags)
    chosen: list[Operation] = []
    held: list[tuple[Operation, str]] = []
    for operation in index.operations:
        if operations and operation.location not in listed:
            continue
        if operation.location in excluded or operation.method not in wanted_methods:
            continue
        if wanted_tags and not wanted_tags.intersection(operation.tags):
            continue
        if operation.is_write and not (include_writes and operation.location in listed):
            held.append(
                (
                    operation,
                    "a write is called only with include_writes: true and listed in operations",
                )
            )
            continue
        chosen.append(operation)
    return chosen, held


def planned(
    operation: Operation,
    params: Mapping[str, Any],
    headers: Mapping[str, str],
    bodies: Mapping[str, Any],
) -> PlannedCall:
    """*operation* with its parameters filled from *params*, or the reason it cannot be."""
    path_params: dict[str, Any] = {}
    query: dict[str, Any] = {}
    given_headers = {name.lower() for name in headers}
    for parameter in operation.parameters:
        if parameter.name in params and parameter.location in ("path", "query"):
            target = path_params if parameter.location == "path" else query
            target[parameter.name] = params[parameter.name]
        if not parameter.required:
            continue
        if parameter.location == "header":
            missing = parameter.name.lower() not in given_headers
        elif parameter.location == "cookie":
            missing = "cookie" not in given_headers
        else:
            missing = parameter.name not in params
        if missing:
            where = "headers" if parameter.location in ("header", "cookie") else "params"
            reason = f"required {parameter.location} parameter '{parameter.name}' is not in {where}"
            return PlannedCall(operation, path_params, query, skipped=reason)
    body = bodies.get(operation.label, bodies.get(operation.key))
    if body is None and operation.body_required:
        return PlannedCall(
            operation,
            path_params,
            query,
            skipped=f"its required body is not in bodies['{operation.label}']",
        )
    return PlannedCall(operation, path_params, query, body)
