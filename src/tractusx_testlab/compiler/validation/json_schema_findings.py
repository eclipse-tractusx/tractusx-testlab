################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.


"""What a JSON Schema failure is told to the author of the document.

The schemas under ``compiler/schemas/`` are generated from the authoring models
and are the contract the IDE validates against, so every TCK is checked twice:
once by Pydantic as it is loaded, once here. Both have to say something the
author can act on, and jsonschema's own rendering does not — see
:func:`collect_errors` for what it said and why.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

#: Past this a message has stopped explaining and started quoting the author's
#: own document back at them. They have the file open; they need the rule.
_MAX_MESSAGE = 200


@cache
def validator_for(schema_name: str) -> Draft202012Validator:
    """Return the validator for a schema, reading and compiling it once per process."""
    schema: dict[str, Any] = json.loads((_SCHEMAS_DIR / schema_name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def collect_errors(
    validator: Draft202012Validator,
    data: dict[str, Any],
    source_label: str,
) -> list[str]:
    """Every failure, reported against the deepest sub-schema that explains it.

    Every optional block in the generated schema is an ``anyOf`` of the thing
    and ``null``, so one wrong key inside a step's ``validate:`` list failed
    both branches and was reported as *the whole list* "is not valid under any
    of the given schemas" — the author's own document echoed back at them, with
    the offending key nowhere named. ``best_match`` descends to the branch that
    got furthest, which is the one the author meant.
    """
    errors: list[str] = []
    for error in validator.iter_errors(data):
        finding = best_match([error]) or error
        path = ".".join(str(part) for part in finding.absolute_path)
        location = f"'{path}' in {source_label}" if path else source_label
        message = finding.message
        if len(message) > _MAX_MESSAGE:
            message = f"{message[:_MAX_MESSAGE]}…"
        errors.append(f"{message} (at {location})")
    return errors
