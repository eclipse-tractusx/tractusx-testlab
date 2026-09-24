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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""``cac:`` — the conformity assessment criteria a test, a step or a check verifies.

Syntax spec §9.1. Purely traceability: nothing in a run's outcome depends on it.
It is carried into the compiled IR and into every terminal step event, which is
what lets a report say which CACs a run covered.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, WithJsonSchema
from pydantic_core import PydanticCustomError

CAC_REF = re.compile(r"^(?P<standard>[^:\s]+):(?P<version>[^:\s]+):(?P<cac>[^:\s]+)$")
"""Matches a ``cac:`` entry — ``<standard-id>:<standard-version>:<cac-id>``.

Three segments, none empty, no whitespace, e.g. ``CX-0135:v3.1.0:CAC-014``. The
standard and version are named so the compiler can hold them to the manifest's
``metadata.standards``; what a CAC id looks like is the Expert Group's business.
"""


def _cac_reference(value: str) -> str:
    """Refuse an entry that does not name a standard, its version and a CAC.

    Said in the author's terms rather than as the regex: a report that cannot
    tell which standard a CAC belongs to cannot put it in a coverage matrix.
    """
    if CAC_REF.match(value) is None:
        raise PydanticCustomError(
            "cac_reference",
            "'{value}' is not a CAC reference — write it as "
            "<standard-id>:<standard-version>:<cac-id>, e.g. 'CX-0135:v3.1.0:CAC-014'",
            {"value": value},
        )
    return value


#: The same form, as the published JSON Schema states it for the IDE. Group names
#: are dropped: ``(?P<name>...)`` is Python, and JSON Schema patterns are ECMA-262.
_JSON_PATTERN = re.sub(r"\?P<\w+>", "", CAC_REF.pattern)

CacReferences = list[
    Annotated[
        str,
        AfterValidator(_cac_reference),
        WithJsonSchema({"type": "string", "pattern": _JSON_PATTERN}),
    ]
]
"""A ``cac:`` list — each entry ``<standard-id>:<standard-version>:<cac-id>``."""


class CacTestKeys(BaseModel):
    """The key this extension adds to a test."""

    #: The CACs this test as a whole verifies. Every step without its own
    #: ``cac`` — nested and skipped ones included — reports under them, and so
    #: does every check whose step does not name one either.
    cac: CacReferences | None = None


class CacStepKeys(BaseModel):
    """The key this extension adds to a step."""

    #: The CACs this step verifies; each of its checks reports under them unless
    #: the check names its own. Overrides the test's ``cac`` for this step.
    cac: CacReferences | None = None


class CacAssertionKeys(BaseModel):
    """The key this extension adds to a ``validate:`` entry."""

    #: The CACs this one check verifies. Overrides the step's ``cac`` for this
    #: check when reported; absent, the check reports under the step's.
    cac: CacReferences | None = None
