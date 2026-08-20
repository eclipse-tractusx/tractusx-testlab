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

"""What the engine requires of an SDK service, stated as types.

Every accessor that hands a step an SDK object used to be annotated ``object``.
Nothing could be read off one without a checker objecting, so the steps read
them defensively instead — 56 ``getattr(service, "name", None)`` probes across
the codebase — and a misspelled SDK attribute became a ``None`` that flowed on
and surfaced as an empty result several steps later rather than as an error.

These Protocols are deliberately **not** a mirror of the SDK. They are the
members the steps actually call: the engine's requirement of a connector, in one
readable place. The SDK stays untyped at its own boundary (``ignore_missing_imports``),
so an SDK object satisfies a Protocol structurally, and what gets checked is the
half we own — the steps.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Controller(Protocol):
    """A management-API resource collection — assets, policies, transfers.

    The SDK exposes each as an attribute of the service, with an ``adapter``
    carrying the base URL and an ``endpoint_url`` carrying the versioned path.
    The engine reads both to report the URL a step called.
    """

    def get_by_id(self, oid: str, **options: Any) -> Any: ...
    def create(self, *args: Any, **kwargs: Any) -> Any: ...
    def delete(self, *args: Any, **kwargs: Any) -> Any: ...


@runtime_checkable
class ConnectorConsumer(Protocol):
    """The consumer half of a connector: catalog, negotiation, transfer, EDR."""

    dataspace_version: str

    #: Management-API resource collections. The engine reads state off them
    #: while polling, and reads their URL to report what a step called.
    catalogs: Controller
    edrs: Controller
    contract_negotiations: Controller
    transfer_processes: Controller

    # -- catalog ------------------------------------------------------------
    def get_catalog_with_filter(self, **kwargs: Any) -> Any: ...
    def get_catalog_by_asset_id(self, **kwargs: Any) -> Any: ...
    def get_catalog_with_bpnl(self, **kwargs: Any) -> Any: ...
    def get_filter_expression(self, *args: Any, **kwargs: Any) -> Any: ...

    # -- DSP, spoken directly rather than through the management API --------
    def do_dsp(self, *args: Any, **kwargs: Any) -> Any: ...
    def do_dsp_with_bpnl(self, *args: Any, **kwargs: Any) -> Any: ...
    def do_dsp_by_dct_type(self, *args: Any, **kwargs: Any) -> Any: ...

    # -- negotiation and transfer ------------------------------------------
    def start_edr_negotiation(self, **kwargs: Any) -> Any: ...
    def get_transfer_id(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_edr(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_edr_entry(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_endpoint_with_token(self, *args: Any, **kwargs: Any) -> Any: ...


@runtime_checkable
class ConnectorProvider(Protocol):
    """The provider half of a connector: assets, policies, contract definitions."""

    dataspace_version: str

    assets: Controller
    policies: Controller
    contract_definitions: Controller

    def create_asset(self, **kwargs: Any) -> Any: ...
    def create_policy(self, **kwargs: Any) -> Any: ...


@runtime_checkable
class RegistryService(Protocol):
    """A Digital Twin Registry — shell and submodel descriptors."""

    aas_url: str
    aas_lookup_url: str

    def create_asset_administration_shell_descriptor(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_asset_administration_shell_descriptor_by_id(self, *args: Any, **kwargs: Any) -> Any: ...
    def delete_asset_administration_shell_descriptor(self, *args: Any, **kwargs: Any) -> Any: ...
    def create_submodel_descriptor(self, *args: Any, **kwargs: Any) -> Any: ...

    #: Reached into by ``digital-twin/provider/lookup_shells`` to reuse the
    #: SDK's auth headers. A private SDK member in a public contract is a smell,
    #: and declaring it here is what makes that visible rather than hidden
    #: inside a getattr — see F-F02's follow-up note in the cleanup ledger.
    def _prepare_headers(self, *args: Any, **kwargs: Any) -> Any: ...


@runtime_checkable
class NotificationService(Protocol):
    """Notifications ride on the connector consumer; this is the half used."""

    def send_notification(self, *args: Any, **kwargs: Any) -> Any: ...
    def discover_notification_assets(self, *args: Any, **kwargs: Any) -> Any: ...


@runtime_checkable
class CallReporter(Protocol):
    """Publishing one call a step made, the moment it is answered.

    Handed to the context by the phase runner, which is what knows the job and
    the script a call belongs to; taken from the context by the step runner,
    which is what knows the step. A nested step reports through the same one,
    because it runs on the same context.
    """

    def __call__(
        self,
        step_type: str,
        step_id: str | None,
        index: int,
        call: Any,
    ) -> None: ...


@runtime_checkable
class StepInvoker(Protocol):
    """Running one step — the part of the runner a nested step needs.

    ``flow/if`` and ``flow/retry`` run the steps nested inside them, which means
    a step calling the runner. The runner lives in the player, and the player
    imports the steps package to register them, so the import goes both ways.

    It was held open by importing ``run_step`` from inside the ``execute``
    bodies: legal, but it hides a cycle rather than removing one, and it puts
    the player's module path inside a step. A flow step needs the *shape* of the
    runner, not the runner — so it takes this, and the player supplies itself.
    """

    async def __call__(
        self,
        step_cls: type,
        step_def: Any,
        step_name: str,
        context: Any,
    ) -> Any: ...
