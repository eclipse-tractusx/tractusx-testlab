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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""Checking that a test names a variable whole, never a path into it.

A declaration says what the variable is; a reference in a test says where it
is read. ``${{ env.usage_policy.policy }}`` named the artifact key the verb
used to choose, and ``${{ env.usage_policy.value }}`` names the key that
replaced it. Both are a path into a value the id already names whole, and the
run resolves neither — so both are answered here, at the line that has to
change, rather than as an unresolved reference in the middle of a test.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from tractusx_testlab.syntax import keys, patterns


def declared_variable_ids(env_data: dict[str, Any]) -> frozenset[str]:
    """The ids of every variable the manifest declares."""
    variables = env_data.get("variables")
    if not isinstance(variables, list):
        return frozenset()
    return frozenset(
        str(entry[keys.ID]) for entry in variables if isinstance(entry, dict) and entry.get(keys.ID)
    )


def validate_variable_references(
    test_data: dict[str, Any],
    variable_ids: frozenset[str],
    source_label: str,
) -> list[str]:
    """Reject a reference that reaches into a variable instead of naming it.

    ``${{ env.usage_policy.policy }}`` named the artifact key the verb used to
    choose, and ``${{ env.usage_policy.value }}`` names the key that replaced
    it. Both are a path into a value the id already names whole, and the run
    resolves neither — so both are answered here, at the line that has to
    change, rather than as an unresolved reference in the middle of a test.
    """
    return [
        f"{source_label}: '${{{{ {reference} }}}}' reaches into variable "
        f"'{var_id}' for '{field}'. A variable is one value and its id names all "
        f"of it — write '${{{{ env.{var_id} }}}}'."
        for reference in _references_in(test_data)
        for var_id, field in [_env_field(reference)]
        if var_id in variable_ids and field
    ]


def _env_field(reference: str) -> tuple[str, str]:
    """Split ``env.<id>.<field…>`` into its variable id and the rest."""
    parts = reference.strip().split(".")
    if len(parts) < 2 or parts[0] != "env":
        return "", ""
    return parts[1], ".".join(parts[2:])


def _references_in(node: Any) -> Iterator[str]:
    """Yield every ``${{ … }}`` expression anywhere in a parsed YAML document."""
    if isinstance(node, str):
        for match in patterns.EXPR_REF.finditer(node):
            yield match.group(1)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _references_in(value)
    elif isinstance(node, list):
        for item in node:
            yield from _references_in(item)
