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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Syntax v2 authoring models — compile-time structures for scripts and TCKs.

All models follow the GitHub Actions-like verb-form YAML schema using ``uses``
and ``with`` keys.  The discriminator field ``syntax`` routes to the correct versioned model via Pydantic Discriminated Unions.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tractusx_testlab.models.authoring.infrastructure import (
    DataspaceContext,
    InfrastructureConfig,
)
from tractusx_testlab.models.primitives.enums import FailurePolicy, ServiceType, VariableScope, VariableSource


# ---------------------------------------------------------------------------
# Shared primitive models (kept across syntax versions)
# ---------------------------------------------------------------------------

class VariableDefinition(BaseModel):
    """Schema for a declared variable."""

    name: str
    type: str = "str"
    default: Optional[Any] = None
    runtime: bool = False
    description: Optional[str] = None
    source: VariableSource = VariableSource.VALUE
    generator: Optional[str] = None
    format: Optional[str] = None
    placeholder: Optional[str] = None
    scope: Optional[VariableScope] = None


class ServiceDefinition(BaseModel):
    """Declaration of an external service used by tests."""

    name: str
    type: ServiceType
    base_url: str
    auth: dict = Field(default_factory=dict)
    params: Optional[dict] = None


class ImportDefinition(BaseModel):
    """Reference to an external script to import into a TCK."""

    import_ref: str
    override: Optional[dict] = None


# ---------------------------------------------------------------------------
# Syntax v2 models
# ---------------------------------------------------------------------------

class MetadataDefinition(BaseModel):
    """Metadata block common to scripts and TCK manifests."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    version: str = "1.0"
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class ReturnFieldDefinition(BaseModel):
    """Single output field declared in a step ``returns`` block."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    cls: Optional[str] = Field(default=None, alias="class")


class AssertionV2(BaseModel):
    """Syntax v2 assertion using ``uses`` / ``with`` verb-form keys."""

    model_config = ConfigDict(populate_by_name=True)

    uses: str
    with_: Optional[dict[str, Any]] = Field(default=None, alias="with")


class StepDefinitionV2(BaseModel):
    """Syntax v2 step definition using ``uses`` and ``with`` verb-form keys."""

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,49}$")
    uses: str
    name: Optional[str] = None
    with_: Optional[dict[str, Any]] = Field(default=None, alias="with")
    returns: Optional[dict[str, ReturnFieldDefinition]] = None
    validate: Optional[list[AssertionV2]] = None
    # Runtime control fields kept for execution-engine compatibility.
    on_failure: FailurePolicy = FailurePolicy.ABORT
    timeout_s: Optional[float] = None
    if_condition: Optional[str] = Field(default=None, alias="if")


class ScriptDefinitionV2(BaseModel):
    """Syntax v2 top-level test script definition."""

    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["test"] = "test"
    syntax: Literal["v2"]
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,99}$")
    namespace: str
    metadata: MetadataDefinition
    setup: list[StepDefinitionV2] = Field(default_factory=list)
    execution: list[StepDefinitionV2] = Field(default_factory=list)
    teardown: list[StepDefinitionV2] = Field(default_factory=list)
    dataspace_version: Literal["saturn", "jupiter"] = "saturn"
    # Transition fields: allow dataspace/infrastructure on per-script level for
    # backward-compatible test suites that embed them inline.
    dataspace: Optional["DataspaceContext"] = None
    infrastructure: Optional["InfrastructureConfig"] = None


class TckMetadataDefinition(MetadataDefinition):
    """Metadata block for TCK manifests — extends base with certification fields."""

    authors: list[dict[str, Any]] = Field(default_factory=list)
    copyright_holders: list[str] = Field(default_factory=list)
    license: str = "Apache-2.0"
    standards: list[dict[str, Any]] = Field(default_factory=list)
    dataspace_version: Literal["saturn", "jupiter"] = "saturn"


class SchemaDefinition(BaseModel):
    """A single schema entry in the TCK env block."""

    id: str
    source: str


class TestDataDefinition(BaseModel):
    """A single test data entry in the TCK env block."""

    id: str
    source: str
    type: str = "application/json"


class EnvDefinition(BaseModel):
    """Environment block in a TCK manifest — shared variables, services, and test data."""

    variables: Optional[Any] = None
    services: Optional[list[dict[str, Any]]] = None
    schemas: Optional[list[SchemaDefinition]] = None
    testdata: Optional[list[TestDataDefinition]] = None


class TckTestEntry(BaseModel):
    """A single entry in the TCK ``tests:`` list.

    ``id`` is the test filename, relative to the ``tests/`` sub-folder of the
    TCK package.  ``name`` is an optional human-readable label used in reports
    and log output.  ``skippable`` controls whether the operator may omit this
    test at runtime via the ``skip_tests`` runtime variable.
    """

    id: str = Field(pattern=r"^[a-zA-Z0-9_\-\.]+\.yaml$")
    name: Optional[str] = None
    skippable: bool = False


class TckDefinitionV2(BaseModel):
    """Syntax v2 top-level TCK manifest definition."""

    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["tck"] = "tck"
    syntax: Literal["v2"]
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,99}$")
    metadata: TckMetadataDefinition
    env: Optional[EnvDefinition] = None
    tests: list[TckTestEntry] = Field(default_factory=list)
    # Transition fields — kept for compatibility with existing CCM examples.
    dataspace: Optional[DataspaceContext] = None
    infrastructure: Optional[InfrastructureConfig] = None


# ---------------------------------------------------------------------------
# Discriminated union routing — single public type aliases, fail-fast on unknown syntax
# ---------------------------------------------------------------------------

ScriptDefinition = Annotated[
    Union[ScriptDefinitionV2],
    Field(discriminator="syntax"),
]

TckDefinition = Annotated[
    Union[TckDefinitionV2],
    Field(discriminator="syntax"),
]
