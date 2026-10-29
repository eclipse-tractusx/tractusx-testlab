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

"""``with.one_of``: documents the SUT operator registers one of.

A standard often allows more than one document for the same purpose — a usage
policy with or without a membership constraint, say — and a conformant SUT
offers either. Each is declared as its own ``source: register`` variable, and
``with.one_of: <group>`` names the group they are alternatives in::

    - id: ccm_usage_policy_default
      uses: config/connector/policy
      with:
        source: register
        one_of: ccm_usage_policy
        default: true
        value: { … }
    - id: ccm_usage_policy_membership
      uses: config/connector/policy
      with:
        source: register
        one_of: ccm_usage_policy
        value: { … }

The group is a variable too: ``${{ env.ccm_usage_policy }}`` is the list of its
alternatives' values, in manifest order, so a test that accepts any of them —
``expected_policies`` — names the group rather than each alternative. An
engine offers the alternatives as one choice, ``with.default`` first.

This module is the one reading of the grouping, shared by the compiler (which
validates it and puts the group in scope), the symbol table and the run (which
seeds the group).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from tractusx_testlab.syntax import keys


def one_of_groups(entries: Iterable[Any]) -> dict[str, list[dict[str, Any]]]:
    """Map each ``with.one_of`` group to its alternatives, in manifest order.

    Only well-formed entries count — a mapping with an id whose ``with.one_of``
    is non-blank text; what is wrong with the others is the compiler's to say.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get(keys.ID):
            continue
        group = group_of(entry)
        if group is not None:
            groups.setdefault(group, []).append(entry)
    return groups


def group_of(entry: dict[str, Any]) -> str | None:
    """The ``with.one_of`` group *entry* is an alternative in, or ``None``."""
    with_block = entry.get(keys.WITH)
    if not isinstance(with_block, dict):
        return None
    group = with_block.get(keys.ONE_OF)
    if not isinstance(group, str) or not group.strip():
        return None
    return group.strip()


def group_value(members: Iterable[dict[str, Any]]) -> list[str]:
    """What the group variable holds: a reference to each alternative.

    Seeded as a template, so each reference resolves when the group is read —
    to the value the manifest wrote or the one the operator supplied for it.
    """
    return [f"${{{{ env.{member[keys.ID]} }}}}" for member in members]
