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

"""Checking how a ``source: register`` document is handed to the SUT operator.

A registered document is one the operator puts into their own system before
the run: ``with.instructions`` says what to do with it, and ``with.one_of``
makes it one of several alternatives they register only one of (what a group
is, and how the run reads it, is in :mod:`tractusx_testlab.syntax.one_of`).
Each says something only an operator reads, so each belongs on a registered
document and nowhere else.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from tractusx_testlab.syntax import keys
from tractusx_testlab.syntax.one_of import one_of_groups

#: The source of a document handed to the SUT operator, the only kind that
#: takes ``with.instructions`` and ``with.one_of``.
_REGISTER_SOURCE = "register"

#: What a ``with.one_of`` group may be called. The group is referenced as
#: ``${{ env.<group> }}``, so it takes a name a reference can spell.
_GROUP_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def check_instructions(with_block: dict[str, Any], var_id: str, source: Any) -> Iterator[str]:
    """Check ``with.instructions``: text, on a document handed to the SUT operator.

    The instructions are what the engine shows beside a ``source: register``
    document — where to register it, and how the run will read it back. On a
    variable the engine keeps to itself nobody would read them, so they are a
    sign the source was forgotten rather than something to ignore.
    """
    if keys.INSTRUCTIONS not in with_block:
        return
    instructions = with_block[keys.INSTRUCTIONS]
    if not isinstance(instructions, str) or not instructions.strip():
        yield (
            f"Variable '{var_id}' has 'with.instructions' that are not text. Write "
            f"what the SUT operator has to do with the document, as a sentence."
        )
    if str(source) != _REGISTER_SOURCE:
        yield (
            f"Variable '{var_id}' has 'with.instructions' but is not handed to the "
            f"SUT operator. Instructions are shown beside a document they register "
            f"themselves — add 'with.source: register', or drop them."
        )


def check_alternative(with_block: dict[str, Any], var_id: str, source: Any) -> Iterator[str]:
    """Check ``with.one_of`` and ``with.default`` on one entry.

    Both say how a document is offered to the SUT operator — as one of several
    they register only one of — so, like the instructions, they belong on a
    ``source: register`` document and nowhere else.
    """
    if keys.ONE_OF in with_block:
        group = with_block[keys.ONE_OF]
        if not isinstance(group, str) or not group.strip():
            yield (
                f"Variable '{var_id}' has a 'with.one_of' that is not a name. Write the "
                f"name of the group it is an alternative in, e.g. 'one_of: usage_policy'."
            )
        elif not _GROUP_NAME.match(group.strip()):
            yield (
                f"Variable '{var_id}' is in group '{group}', which is not a name a "
                f"reference can spell. Use letters, digits and '_', starting with a "
                f"letter or '_'."
            )
        if str(source) != _REGISTER_SOURCE:
            yield (
                f"Variable '{var_id}' has 'with.one_of' but is not handed to the SUT "
                f"operator. Alternatives are documents the operator registers one of "
                f"— add 'with.source: register', or drop 'one_of'."
            )
    if keys.DEFAULT in with_block:
        if not isinstance(with_block[keys.DEFAULT], bool):
            yield (
                f"Variable '{var_id}' has 'with.default: {with_block[keys.DEFAULT]}'. "
                f"Write 'default: true' or leave it out."
            )
        elif keys.ONE_OF not in with_block:
            yield (
                f"Variable '{var_id}' has 'with.default' but is in no 'with.one_of' "
                f"group. The default is the alternative offered first, so it needs "
                f"the others — add 'one_of', or drop 'default'."
            )


def check_one_of_groups(variables: list[Any], variable_ids: set[str]) -> Iterator[str]:
    """Check each ``with.one_of`` group as a whole.

    The group is published as ``${{ env.<group> }}``, the list of its
    alternatives, so its name may not be a variable's too, and the list has to
    hold one kind of thing: alternatives of different verbs are not the same
    document said two ways, and a step reading the group would get a list it
    cannot take.
    """
    for group, members in one_of_groups(variables).items():
        member_ids = [str(member[keys.ID]) for member in members]
        if group in variable_ids:
            yield (
                f"Group '{group}' has the name of a variable. '${{{{ env.{group} }}}}' "
                f"would name both the variable and the list of the group's "
                f"alternatives — rename one of them."
            )
        if len(members) < 2:
            yield (
                f"Group '{group}' has one alternative, '{member_ids[0]}'. A group "
                f"offers the operator a choice — add another alternative with "
                f"'one_of: {group}', or drop 'one_of' from this one."
            )
        verbs = sorted({str(member.get(keys.USES) or "") for member in members})
        if len(verbs) > 1:
            yield (
                f"Group '{group}' mixes {', '.join(repr(verb) for verb in verbs)}. "
                f"Its alternatives are the same kind of document, so they share one "
                f"'uses'."
            )
        defaults = [
            member_id
            for member, member_id in zip(members, member_ids, strict=True)
            if (member.get(keys.WITH) or {}).get(keys.DEFAULT) is True
        ]
        if len(defaults) > 1:
            yield (
                f"Group '{group}' has more than one default: {', '.join(defaults)}. "
                f"The default is the one alternative offered first — keep "
                f"'default: true' on one of them."
            )
