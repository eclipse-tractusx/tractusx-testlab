#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################

"""Contract models shared by more than one step.

A step's declared models are its public interface, so when two steps talk about
the same thing — the counter-party of a DSP request, a catalog filter
criterion, an EDR data address — they share one model rather than each
re-declaring it.  Sharing is what makes the wiring between steps visible in the
types: ``query_catalog`` returns a :class:`CatalogPayload` and
``extract_dataset`` reads one, and both say so in their signature.

The mixins here are meant to be inherited by a step's own params model::

    class QueryCatalogParams(CounterPartyParams):
        asset_id: str = ""
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from tractusx_testlab.steps.base import StepExports, StepParams, StepPayload, StepValue
from tractusx_testlab.syntax.context_vars import (
    CATALOG_DATASETS,
    DATAPLANE_ENDPOINT,
    EDR_TOKEN,
)

#: JSON-LD key holding the dataset offers of a DCAT catalog.
DATASET_KEY = "dcat:dataset"


class NoOutput(StepValue[None]):
    """This step produces no value — it acts, and there is nothing to read back.

    Declaring it is the point: "no output" and "output not declared yet" look
    the same to a script author unless one of them says so.
    """


# ---------------------------------------------------------------------------
# Parameter mixins
# ---------------------------------------------------------------------------


class StoreInVariableParams(StepParams):
    """Adds the ``store_in_variable`` escape hatch to a step's inputs.

    The variable name comes from the script rather than from the step, so it
    cannot be declared in a :class:`~tractusx_testlab.steps.base.StepExports`
    model the way a fixed export is — the step writes it directly.
    """

    store_in_variable: str = Field(
        default="",
        description="Name of a context variable to also store the result in.",
    )


class CounterPartyParams(StepParams):
    """The counter-party a DSP request is addressed to.

    ``provider_url``/``bpnl`` are the legacy spellings kept working by the
    aliases; both resolve to the same two fields.
    """

    counter_party_address: str = Field(
        default="",
        validation_alias=AliasChoices("counter_party_address", "provider_url"),
        description="DSP endpoint of the counter-party connector.",
    )
    counter_party_id: str = Field(
        default="",
        validation_alias=AliasChoices("counter_party_id", "bpnl"),
        description="BPN of the counter-party.",
    )


# ---------------------------------------------------------------------------
# Catalog filtering
# ---------------------------------------------------------------------------


class FilterExpression(BaseModel):
    """One catalog filter criterion.

    Scripts and IDE blocks write snake_case; the connector management API
    expects camelCase, so the two spellings are accepted on the way in and the
    camelCase form is what gets serialised on the way out.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    operand_left: str = Field(
        validation_alias=AliasChoices("operand_left", "operandLeft"),
        serialization_alias="operandLeft",
        description="Left-hand property of the criterion, e.g. 'https://w3id.org/edc/v0.0.1/ns/id'.",
    )
    operator: str = Field(default="=", description="Comparison operator.")
    operand_right: Any = Field(
        default="",
        validation_alias=AliasChoices("operand_right", "operandRight"),
        serialization_alias="operandRight",
        description="Value the left-hand property is compared against.",
    )

    def to_sdk(self) -> dict:
        """Render as the dict shape the SDK's catalog request expects."""
        return self.model_dump(by_alias=True)


class CatalogFilter(BaseModel):
    """Nested ``filter:`` block — an alternative spelling of ``filter_expression``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    filter_expression: list[FilterExpression] = Field(
        default_factory=list,
        description="Filter criteria applied to the catalog request.",
    )


class FilterExpressionParams(StepParams):
    """Adds catalog filter criteria to a step's inputs.

    ``filters`` is the spelling the IDE blocks emit and ``filter_expression``
    the one the SDK uses; a script may write either.
    """

    filter_expression: list[FilterExpression] = Field(
        default_factory=list,
        validation_alias=AliasChoices("filter_expression", "filters"),
        description="Filter criteria applied to the catalog request.",
    )

    def sdk_filter_expression(self) -> list[dict]:
        """The filter criteria in the dict shape the SDK expects."""
        return [entry.to_sdk() for entry in self.filter_expression]


# ---------------------------------------------------------------------------
# Catalog documents
# ---------------------------------------------------------------------------


class CatalogPayload(StepPayload):
    """A provider's DCAT catalog.

    The catalog is a JSON-LD document defined by DSP rather than by testlab, so
    the well-known keys scripts assert on are named here and everything else
    the provider sends round-trips untouched.

    Only the JSON-LD spellings populate these fields — no ``populate_by_name``
    — so a provider that happens to send a plain ``id`` key keeps it rather
    than having it rewritten as ``@id``.
    """

    model_config = ConfigDict(extra="allow")

    context: Any = Field(default=None, alias="@context", description="JSON-LD context.")
    id: Optional[str] = Field(default=None, alias="@id", description="Catalog ID.")
    type: Any = Field(default=None, alias="@type", description="JSON-LD type.")
    # Left as Any rather than list[dict]: a provider offering exactly one
    # dataset sends a bare object, and coercing it here would silently change
    # the document that assertions run against.
    datasets: Any = Field(
        default=None,
        alias=DATASET_KEY,
        description="Dataset offers — a list, or a bare object when there is exactly one.",
    )


class CatalogDatasetsExports(StepExports):
    """The offers a catalog query publishes for the steps that follow it."""

    datasets: Optional[list[dict]] = Field(
        default=None,
        alias=CATALOG_DATASETS,
        description="Dataset offers from the catalog, always as a list.",
    )


def as_dataset_list(catalog: Optional[dict]) -> list[dict]:
    """Return a catalog's datasets, normalising the single-offer object form."""
    datasets = (catalog or {}).get(DATASET_KEY, [])
    if isinstance(datasets, dict):
        return [datasets]
    return datasets or []


# ---------------------------------------------------------------------------
# Data-plane access
# ---------------------------------------------------------------------------


class DataplaneExports(StepExports):
    """The data-plane address every step that completes a transfer publishes.

    ``connector/dataplane/http_request`` reads exactly these two variables, so
    any step that produces them declares them through this model.
    """

    dataplane_endpoint: Optional[str] = Field(
        default=None,
        alias=DATAPLANE_ENDPOINT,
        description="Data-plane URL the negotiated data is fetched from.",
    )
    edr_token: Optional[str] = Field(
        default=None,
        alias=EDR_TOKEN,
        description="Authorization token for that data-plane URL.",
    )


class DataAddressPayload(StepPayload):
    """An EDR data address — where negotiated data is fetched and with what token."""

    model_config = ConfigDict(extra="allow")

    endpoint: Optional[str] = Field(
        default=None, description="Data-plane URL to fetch the data from."
    )
    authorization: Optional[str] = Field(
        default=None, description="Authorization token for that URL."
    )
    auth_code: Optional[str] = Field(
        default=None,
        alias="authCode",
        description="Legacy spelling of 'authorization' used by older connectors.",
    )


def data_address_token(data_address: Optional[dict]) -> Optional[str]:
    """Read the auth token from a data address under either of its two spellings."""
    if not data_address:
        return None
    return data_address.get("authorization") or data_address.get("authCode")


# ---------------------------------------------------------------------------
# HTTP calls
# ---------------------------------------------------------------------------


class HttpTransportParams(StepParams):
    """How a step reaches an HTTP server, regardless of what it sends.

    Steps that build their own URL and verb — ``digital-twin/submodel/upload`` always POSTs
    to a URL it generates — take only this half.
    """

    headers: dict[str, str] = Field(
        default_factory=dict, description="Extra HTTP headers merged into the request."
    )
    timeout: Optional[float] = Field(
        default=None,
        description="Request timeout in seconds; the script's default is used when omitted.",
    )

    @field_validator("headers", mode="before")
    @classmethod
    def _no_headers_is_no_headers(cls, value: Any) -> Any:
        """Treat an explicit ``headers: null`` as "none given"."""
        return {} if value is None else value

    def timeout_or(self, default: float) -> float:
        """The timeout to use, falling back to the run's configured default."""
        return default if self.timeout is None else self.timeout


class HttpCallParams(HttpTransportParams):
    """The parts of an HTTP request every calling step accepts.

    The target URL is deliberately not here: each step derives it differently —
    ``http/http_request`` takes it verbatim, the data-plane step reads it from
    the EDR — so the URL belongs to the step, and only the shared verb, body,
    headers, and timeout live in one place.
    """

    method: str = Field(default="GET", description="HTTP method.")
    body: Any = Field(default=None, description="Request body; dicts are sent as JSON.")

    @field_validator("method")
    @classmethod
    def _uppercase_method(cls, value: str) -> str:
        """Accept ``get`` as readily as ``GET``."""
        return value.upper()


class HttpBodyOutput(StepValue[Any]):
    """A response body: parsed JSON when the server sent JSON, otherwise the raw text.

    Steps that call HTTP return the body itself rather than wrapping it, so a
    script asserts on ``value.field`` the same way it would read the document.
    """
