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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""A connector that answers the management-API calls the steps make.

Standing up a real EDC pair for a unit test is not on, so the consumer and
provider services are doubled — but only at the SDK boundary the steps actually
call, and each double records what it was asked for. A step that passes the
wrong id to the SDK fails here, which a ``MagicMock`` returning a truthy mock
for every attribute would not catch.

The data plane is *not* doubled: it is a real socket served by
:class:`~combinations.http_double.HttpDouble`, because that hop is a plain HTTP
request the step builds itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class _Response:
    """The part of a ``requests.Response`` the SDK controllers hand back."""

    def __init__(self, status_code: int = 200, body: dict | None = None) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("no body")
        return self._body


@dataclass
class _Controller:
    """A management-API controller that answers reads with a fixed document."""

    document: dict
    reads: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def get_by_id(self, oid: str, **_kwargs: Any) -> _Response:
        self.reads.append(oid)
        return _Response(200, {"@id": oid, **self.document})

    def delete(self, oid: str, **_kwargs: Any) -> _Response:
        self.deleted.append(oid)
        return _Response(204, None)


class ConsumerDouble:
    """The consumer side of a DSP flow, as the connector steps see it."""

    dataspace_version = "jupiter"

    def __init__(self, catalog: dict, dataplane_url: str, token: str = "Bearer edr") -> None:
        self._catalog = catalog
        self._dataplane_url = dataplane_url
        self._token = token
        self.contract_negotiations = _Controller(
            {"state": "FINALIZED", "contractAgreementId": "agr-1"}
        )
        self.transfer_processes = _Controller({"state": "STARTED"})
        #: Every call the steps made, so a test can assert on what was asked.
        self.calls: list[tuple[str, dict]] = []

    def _record(self, name: str, **kwargs: Any) -> None:
        self.calls.append((name, kwargs))

    def args_of(self, name: str) -> dict:
        """The arguments of the first call to *name*."""
        for called, kwargs in self.calls:
            if called == name:
                return kwargs
        raise AssertionError(f"{name!r} was never called. Called: {[c for c, _ in self.calls]}")

    # -- the SDK surface the steps use ------------------------------------

    def get_filter_expression(self, key: str, value: Any, operator: str) -> dict:
        """The SDK builds the JSON-LD filter; the shape is all the step needs."""
        self._record("get_filter_expression", key=key, value=value, operator=operator)
        return {"operandLeft": key, "operator": operator, "operandRight": value}

    def get_catalog_with_filter(self, **kwargs: Any) -> dict:
        self._record("get_catalog_with_filter", **kwargs)
        return self._catalog

    def get_catalog_by_asset_id(self, **kwargs: Any) -> dict:
        self._record("get_catalog_by_asset_id", **kwargs)
        return self._catalog

    def start_edr_negotiation(self, **kwargs: Any) -> str:
        self._record("start_edr_negotiation", **kwargs)
        return "neg-1"

    def get_edr_entry(self, **kwargs: Any) -> dict:
        self._record("get_edr_entry", **kwargs)
        return {"transferProcessId": "tp-1"}

    def get_edr(self, **kwargs: Any) -> dict:
        self._record("get_edr", **kwargs)
        return {"endpoint": self._dataplane_url, "authorization": self._token}


class ProviderDouble:
    """The provider side — enough of it for a setup and a teardown."""

    dataspace_version = "jupiter"

    def __init__(self) -> None:
        self.assets = _Controller({})
        self.policies = _Controller({})
        self.contract_definitions = _Controller({})
        self.created: list[dict] = []

    def create_asset(self, **kwargs: Any) -> _Response:
        self.created.append(kwargs)
        return _Response(200, {"@id": kwargs.get("asset_id", "asset-1")})


class ServicesDouble:
    """A ``ServiceManager`` stand-in holding one consumer and one provider.

    ``DataspaceAccess`` reaches a service by walking ``service_names`` and
    calling ``get`` for a type, and asks ``definition_of_type`` for the declared
    base URL — that trio is the whole surface to stand in for.
    """

    def __init__(
        self,
        consumer: ConsumerDouble | None = None,
        provider: ProviderDouble | None = None,
    ) -> None:
        self._by_type: dict[str, object] = {}
        if consumer is not None:
            self._by_type["CONNECTOR_CONSUMER"] = consumer
        if provider is not None:
            self._by_type["CONNECTOR_PROVIDER"] = provider
        self._definitions: dict[str, object] = {}

    @property
    def service_names(self) -> list[str]:
        return list(self._by_type)

    def definition_of_type(self, service_type: Any) -> object | None:
        """No declarations here: these doubles carry their own base URLs.

        ``DataspaceAccess`` falls back to the controller's own adapter URL when
        there is no declaration, which is what these doubles provide.
        """
        return None

    def get(self, name: str, service_type: Any) -> object:
        """Return the service when *name* is the one registered for that type."""
        wanted = getattr(service_type, "name", str(service_type))
        if name != wanted or name not in self._by_type:
            from tractusx_testlab.models import ServiceNotFoundError

            raise ServiceNotFoundError(name)
        return self._by_type[name]
