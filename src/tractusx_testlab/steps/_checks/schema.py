#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""The JSON Schema check behind ``validate/schema``."""

from __future__ import annotations

import json

import jsonschema


def check_schema_validation(
    actual: object, expected: object, _output: object = None
) -> tuple[bool, str]:
    """Validate *actual* against the JSON Schema document in *expected*.

    A schema that arrives as text is decoded first, because an unresolved
    ``${{ env.schemas.X }}`` reference and a genuine inline schema look the
    same at this point and only one of them is an authoring mistake.
    """
    if expected is None:
        return False, "No schema provided — 'validate/schema' needs a 'schema:' key"
    try:
        schema = expected if isinstance(expected, dict) else json.loads(expected)
        jsonschema.validate(actual, schema)
        return True, ""
    except jsonschema.ValidationError as exc:
        return False, f"Schema validation failed: {exc.message}"
    except (json.JSONDecodeError, TypeError) as exc:
        return False, f"Invalid schema: {exc}"
