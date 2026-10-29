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

"""The ``env:`` entries of a TCK manifest that name a file of the package.

``schemas`` (JSON Schemas), ``testdata`` (request bodies and other fixtures)
and ``apis`` (OpenAPI documents, ADR-0030) are the same shape — an ``id`` a
test references and a ``source`` under the folder named like the collection —
and differ in what the file is.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Every authoring model rejects keys it does not declare. Pydantic's default is
#: ``extra="ignore"``, which silently discarded them: a ``validte:`` block was
#: dropped and the step reported PASS with zero assertions; a ``whit:`` block was
#: dropped and the step ran with no parameters. The reasoning was already written
#: down one layer in, on ``StepParams``, and never applied to the models that
#: select it: a key the author wrote and the engine ignored is how a test comes
#: to look like it configured something it never configured.
STRICT = ConfigDict(populate_by_name=True, extra="forbid")


class SchemaDefinition(BaseModel):
    """A single schema entry in the TCK env block."""

    model_config = STRICT

    id: str
    source: str


class TestDataDefinition(BaseModel):
    """A single test data entry in the TCK env block."""

    model_config = STRICT

    id: str
    source: str
    type: str = "application/json"


#: The media types an API file may declare: the OpenAPI ones registered with
#: IANA, and the generic ones a document is just as often served as.
ApiMediaType = Literal[
    "application/vnd.oai.openapi",
    "application/vnd.oai.openapi+json",
    "application/yaml",
    "application/json",
]

#: The type of an API file whose entry declares none, by its extension.
API_TYPE_BY_EXTENSION: dict[str, ApiMediaType] = {
    ".yaml": "application/vnd.oai.openapi",
    ".yml": "application/vnd.oai.openapi",
    ".json": "application/vnd.oai.openapi+json",
}

#: An API id is one segment of a reference (``env.apis.<id>``) and, later, the
#: prefix of the types its schemas become (``<id>.<Schema>``): no dots.
API_ID_PATTERN = r"^[a-z][a-z0-9_]{0,49}$"


class ApiDefinition(BaseModel):
    """An OpenAPI document the TCK carries under ``apis/`` (ADR-0030).

    It says what an API is, never how it is reached: there is no base URL,
    connector or credential here, because the steps of a test decide that.
    """

    model_config = STRICT

    id: str = Field(
        pattern=API_ID_PATTERN,
        description="Name a test references the document by: '${{ env.apis.<id> }}'.",
    )
    source: str = Field(min_length=1, description="File name under the package's apis/ folder.")
    type: ApiMediaType | None = Field(
        default=None,
        description=(
            "Media type the file is read as. Omitted: application/vnd.oai.openapi for "
            ".yaml/.yml, application/vnd.oai.openapi+json for .json."
        ),
    )

    @model_validator(mode="after")
    def _type_from_extension(self) -> Self:
        """Fill in ``type`` from the file's extension when the entry declares none."""
        if self.type is None:
            suffix = PurePosixPath(self.source).suffix.lower()
            if suffix not in API_TYPE_BY_EXTENSION:
                raise ValueError(
                    f"type cannot be inferred from '{self.source}': name the file .yaml, .yml "
                    f"or .json, or declare type: one of {', '.join(get_args(ApiMediaType))}"
                )
            self.type = API_TYPE_BY_EXTENSION[suffix]
        return self
