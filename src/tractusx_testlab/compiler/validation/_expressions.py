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

"""Expression resolver — converts ${{ expr }} template strings to $ref/$concat IR nodes."""

from __future__ import annotations

from typing import Any

from tractusx_testlab.syntax import patterns


def resolve_expression(value: Any) -> Any:
    """Recursively resolve ${{ expr }} strings to $ref/$concat objects."""
    if isinstance(value, str):
        return _resolve_string_expr(value)
    if isinstance(value, dict):
        return {k: resolve_expression(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_expression(item) for item in value]
    return value


def _resolve_string_expr(value: str) -> Any:
    """Convert a string with ${{ expr }} to $ref or $concat."""
    full_match = patterns.EXPR_REF_FULL.match(value)
    if full_match:
        return {"$ref": _normalize_ref(full_match.group(1))}

    parts = patterns.EXPR_REF.split(value)
    if len(parts) == 1:
        return value

    concat_parts: list[Any] = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            if part:
                concat_parts.append(part)
        else:
            concat_parts.append({"$ref": _normalize_ref(part)})

    if len(concat_parts) == 1:
        return concat_parts[0]
    return {"$concat": concat_parts}


#: Roots that name something inside the ``env:`` block without saying so, and are
#: rewritten under it. Every other root — ``env.``, ``steps.``, ``setup.``,
#: ``metadata.`` and, per ADR-0019, ``infrastructure.`` — is already canonical
#: and is kept verbatim. (``infrastructure.<side>.<capability>`` is a first-class
#: capability handle; deeper segments such as
#: ``infrastructure.sut.connector.dsp_url`` are operator-supplied binding fields
#: resolved from the binding profile at runtime.)
_ENV_SCOPED_ROOTS = ("testdata.", "schemas.")


def _normalize_ref(expr: str) -> str:
    """Normalize expression paths to canonical $ref format."""
    expr = expr.strip()
    if expr.startswith(_ENV_SCOPED_ROOTS):
        return f"env.{expr}"
    return expr
