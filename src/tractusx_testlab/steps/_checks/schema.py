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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""The JSON Schema check behind ``validate/schema``."""

from __future__ import annotations

import json

import jsonschema


def _decode(value: object, label: str) -> tuple[object, str]:
    """Return *value* as parsed JSON, decoding it when it arrived as text.

    HTTP steps hand back response bodies as text, and an unresolved
    ``${{ env.schemas.X }}`` reference also arrives as a string — decoding here
    keeps the ordinary case working and turns the unresolved one into a message
    that names the problem instead of a confusing schema mismatch.
    """
    if not isinstance(value, str):
        return value, ""
    try:
        return json.loads(value), ""
    except json.JSONDecodeError as exc:
        return None, f"{label} is not valid JSON: {value[:120]!r} ({exc})"


def check_schema_validation(
    actual: object, expected: object, _output: object = None
) -> tuple[bool, str]:
    """Validate *actual* against the JSON Schema document in *expected*.

    Every error is reported, not only the first: a payload that is wrong in
    three places costs three runs to fix if the check stops at one, and a TCK
    run against a remote SUT is not cheap to repeat.

    The schema itself is checked before it is used.  An invalid schema silently
    accepts everything under some drafts, which is the failure mode this whole
    module exists to prevent — a validation step that passes because the
    validation was never really configured.
    """
    if expected is None:
        return False, "No schema provided — 'validate/schema' needs a 'schema:' key"

    schema, problem = _decode(expected, "The schema")
    if problem:
        return False, problem
    payload, problem = _decode(actual, "The payload")
    if problem:
        return False, problem

    if not isinstance(schema, dict):
        return False, (
            f"Expected a JSON Schema object, got {type(schema).__name__}. "
            f"Check that the schema reference resolves."
        )

    validator_cls = jsonschema.validators.validator_for(schema)
    try:
        validator_cls.check_schema(schema)
    except jsonschema.SchemaError as exc:
        return False, f"Invalid JSON Schema: {exc.message}"

    errors = sorted(validator_cls(schema).iter_errors(payload), key=lambda e: list(e.path))
    if not errors:
        return True, ""

    details = "; ".join(
        f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in errors
    )
    return False, f"Schema validation failed ({len(errors)} error(s)): {details}"
