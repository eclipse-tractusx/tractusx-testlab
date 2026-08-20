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

"""The JSON Schemas, generated from the models that actually validate.

The schemas were hand-written, and they had drifted. They named ``testlab`` and
``steps`` where the models declare ``syntax`` and ``execution``; they required
six fields the models made optional; they carried ``additionalProperties: true``,
so the layer meant to catch unknown keys accepted them. A TCK built through the
models was valid to the engine and invalid to the compiler, and the difference
only showed when someone happened to run the CLI.

Generating them removes the drift by construction: there is one description of a
TCK — :class:`TckDefinition` and :class:`ScriptDefinition` — and the schema is a
projection of it, published for the IDE and anything else outside this codebase.
``testlab schema --check`` fails the build when the committed files no longer
match, exactly as ``testlab docs --check`` does for the step reference.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from tractusx_testlab.models.authoring.definitions import (
    ScriptDefinition,
    TckDefinition,
)

#: Where the generated schemas are committed, relative to the package root.
SCHEMA_DIR = Path(__file__).parent / "schemas"

#: Filename → the model it is generated from.
SCHEMAS: dict[str, type[BaseModel]] = {
    "tck_index.schema.json": TckDefinition,
    "tck_test.schema.json": ScriptDefinition,
}

_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

_BANNER = (
    "Generated from {model} by `testlab schema`. Do not edit: the models in "
    "tractusx_testlab.models.authoring.definitions are the source of truth, and "
    "`testlab schema --check` fails the build if this file no longer matches them."
)


def render(model: type[BaseModel]) -> str:
    """Return the JSON Schema for *model*, as the bytes that get committed.

    ``by_alias`` matters: scripts write ``with:`` and ``if:``, while the fields
    are ``with_`` and ``if_condition`` because those spellings are not legal
    Python. The schema has to describe the YAML, not the Python.
    """
    schema = model.model_json_schema(by_alias=True)
    schema["$schema"] = _SCHEMA_DIALECT
    schema["$comment"] = _BANNER.format(model=model.__name__)
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_all(target_dir: Path | None = None) -> list[Path]:
    """Write every schema to *target_dir*, returning the paths written."""
    directory = target_dir or SCHEMA_DIR
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, model in SCHEMAS.items():
        path = directory / filename
        path.write_text(render(model), encoding="utf-8")
        written.append(path)
    return written


def stale(target_dir: Path | None = None) -> list[str]:
    """Return the names of committed schemas that no longer match the models."""
    directory = target_dir or SCHEMA_DIR
    out = []
    for filename, model in SCHEMAS.items():
        path = directory / filename
        if not path.is_file() or path.read_text(encoding="utf-8") != render(model):
            out.append(filename)
    return out
