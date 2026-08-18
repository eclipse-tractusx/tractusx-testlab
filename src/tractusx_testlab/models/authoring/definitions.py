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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Syntax v1-alpha authoring models — compile-time structures for scripts and TCKs.

All models follow the GitHub Actions-like verb-form YAML schema using ``uses``
and ``with`` keys.  The ``syntax`` field pins the format version (``v1-alpha``).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from tractusx_testlab.models.authoring.infrastructure import (
    DataspaceContext,
    InfrastructureConfig,
)
from tractusx_testlab.models.primitives.enums import ServiceType, VariableScope, VariableSource

# ---------------------------------------------------------------------------
# Shared primitive models (kept across syntax versions)
# ---------------------------------------------------------------------------

#: Every authoring model rejects keys it does not declare.
#:
#: Pydantic's default is ``extra="ignore"``, which silently discarded them. A
#: ``validte:`` block was dropped and the step reported PASS with zero
#: assertions; a ``whit:`` block was dropped and the step ran with no
#: parameters. The reasoning was already written down one layer in, on
#: ``StepParams``, and simply never applied to the models that select it: a key
#: the author wrote and the engine ignored is how a script comes to look like it
#: configured something it never configured.
_STRICT = ConfigDict(populate_by_name=True, extra="forbid")


class VariableDefinition(BaseModel):
    """Schema for a declared variable."""

    model_config = _STRICT

    name: str
    type: str = "str"
    default: Any | None = None
    runtime: bool = False
    description: str | None = None
    source: VariableSource = VariableSource.VALUE
    generator: str | None = None
    format: str | None = None
    placeholder: str | None = None
    scope: VariableScope | None = None


class ServiceDefinition(BaseModel):
    """Declaration of an external service used by tests."""

    model_config = _STRICT

    name: str
    type: ServiceType
    base_url: str
    auth: dict = Field(default_factory=dict)
    params: dict | None = None


class ImportDefinition(BaseModel):
    """Reference to an external script to import into a TCK."""

    model_config = _STRICT

    import_ref: str
    override: dict | None = None


# ---------------------------------------------------------------------------
# Syntax v1-alpha models
# ---------------------------------------------------------------------------


class MetadataDefinition(BaseModel):
    """Metadata block common to scripts and TCK manifests."""

    model_config = _STRICT

    name: str
    version: str = "1.0"
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class ReturnFieldDefinition(BaseModel):
    """Single output field declared in a step ``returns`` block."""

    model_config = _STRICT

    type: str
    cls: str | None = Field(default=None, alias="class")


class Assertion(BaseModel):
    """Assertion using ``uses`` / ``with`` verb-form keys."""

    model_config = _STRICT

    uses: str
    with_: dict[str, Any] | None = Field(default=None, alias="with")


class StepDefinition(BaseModel):
    """Step definition using ``uses`` and ``with`` verb-form keys."""

    model_config = _STRICT

    id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,49}$")
    uses: str
    name: str | None = None
    with_: dict[str, Any] | None = Field(default=None, alias="with")
    returns: dict[str, ReturnFieldDefinition] | None = None
    #: The step's checks. Named ``assertions`` in Python because a field called
    #: ``validate`` shadows ``BaseModel.validate`` — Pydantic warned about it on
    #: every import of this library, including every ``testlab`` invocation, and
    #: mypy reported the override as a type error. Scripts still write
    #: ``validate:``; the aliases are what make that the only spelling anyone
    #: outside this file sees.
    assertions: list[Assertion] | None = Field(
        default=None,
        validation_alias="validate",
        serialization_alias="validate",
    )
    #: Marks the step as a negative test (syntax spec §9.3): the request is one
    #: the system under test is required to refuse.
    #:
    #: Declarative. What "refused correctly" means is expressed by the step's
    #: ``validate:`` block, which is where a negative test's expectation lives —
    #: the shipped error-handling TCK marks a step ``expects: fail`` and then
    #: asserts ``status_code == 200`` with a well-formed rejection body, because
    #: the refusal is an application-level answer, not a transport failure.
    #: Inverting the step's own outcome would therefore fail exactly the runs
    #: that are correct.
    #:
    #: Declared rather than merely tolerated so it survives ``extra="forbid"``
    #: and reaches the compiled IR, where the IDE and reporting can see which
    #: steps are negative tests.
    expects: Literal["fail"] | None = None
    # Runtime control fields kept for execution-engine compatibility.
    timeout_s: float | None = None
    if_condition: str | None = Field(default=None, alias="if")


class ScriptDefinition(BaseModel):
    """Top-level test script definition."""

    model_config = _STRICT

    kind: Literal["test"] = "test"
    syntax: Literal["v1-alpha"]
    id: str = Field(
        # Dots are allowed so an id can carry the version it was cut at,
        # e.g. "certificate-management-tck-v0.0.1".
        pattern=r"^[a-z][a-z0-9_.-]{0,99}$"
    )
    namespace: str
    metadata: MetadataDefinition
    setup: list[StepDefinition] = Field(default_factory=list)
    execution: list[StepDefinition] = Field(default_factory=list)
    teardown: list[StepDefinition] = Field(default_factory=list)
    #: The ecosystem release and the capabilities this script needs. Both are
    #: stated in blocks — there is no flat ``dataspace_version`` field: it was
    #: the older spelling of ``dataspace.version`` and having two ways to say
    #: one thing is how the two came to disagree.
    dataspace: DataspaceContext | None = None
    infrastructure: InfrastructureConfig | None = None


class TckMetadataDefinition(MetadataDefinition):
    """Metadata block for TCK manifests — extends base with certification fields."""

    authors: list[dict[str, Any]] = Field(default_factory=list)
    copyright_holders: list[str] = Field(default_factory=list)
    license: str = "Apache-2.0"
    standards: list[dict[str, Any]] = Field(default_factory=list)


class SchemaDefinition(BaseModel):
    """A single schema entry in the TCK env block."""

    model_config = _STRICT

    id: str
    source: str


class TestDataDefinition(BaseModel):
    """A single test data entry in the TCK env block."""

    model_config = _STRICT

    id: str
    source: str
    type: str = "application/json"


class EnvDefinition(BaseModel):
    """Environment block in a TCK manifest — shared variables, services, and test data."""

    model_config = _STRICT

    variables: Any | None = None
    services: list[dict[str, Any]] | None = None
    schemas: list[SchemaDefinition] | None = None
    testdata: list[TestDataDefinition] | None = None


class TckTestEntry(BaseModel):
    """A single entry in the TCK ``tests:`` list.

    ``id`` is the test filename, relative to the ``tests/`` sub-folder of the
    TCK package.  ``name`` is an optional human-readable label used in reports
    and log output.  ``skippable`` controls whether the operator may omit this
    test at runtime via the ``skip_tests`` runtime variable.
    """

    model_config = _STRICT

    id: str = Field(pattern=r"^[a-zA-Z0-9_\-\.]+\.yaml$")
    name: str | None = None
    skippable: bool = False


class TckDefinition(BaseModel):
    """Top-level TCK manifest definition."""

    model_config = _STRICT

    kind: Literal["tck"] = "tck"
    syntax: Literal["v1-alpha"]
    id: str = Field(
        # Dots are allowed so an id can carry the version it was cut at,
        # e.g. "certificate-management-tck-v0.0.1".
        pattern=r"^[a-z][a-z0-9_.-]{0,99}$"
    )
    metadata: TckMetadataDefinition
    env: EnvDefinition | None = None
    tests: list[TckTestEntry] = Field(default_factory=list)
    # Transition fields — kept for compatibility with existing CCM examples.
    dataspace: DataspaceContext | None = None
    infrastructure: InfrastructureConfig | None = None


# ``syntax`` is a plain ``Literal["v1-alpha"]`` on both models: there is exactly
# one syntax version, so the field itself fail-fasts on anything else and no
# discriminated-union routing is needed.
