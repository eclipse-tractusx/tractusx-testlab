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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Notification steps — reuses SDK NotificationConsumerService."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import ConfigDict, Field, model_validator

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import http_client, sdk_call
from tractusx_testlab.steps.counter_party import CounterPartyParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload, StepValue

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

_logger = logging.getLogger(__name__)

#: Metadata keys copied into the body when a script passes them alongside it.
_NOTIFICATION_METADATA = ("notification_id", "sender_bpn", "recipient_bpn", "type", "status")


# ---------------------------------------------------------------------------
# notification/consumer/send
# ---------------------------------------------------------------------------


class SendNotificationParams(CounterPartyParams):
    """Input contract of ``notification/consumer/send``.

    Two modes share one step.  Giving ``dataplane_url`` picks the direct mode,
    which POSTs straight at a data-plane the DSP flow already opened; leaving it
    out picks the SDK mode, which negotiates the notification asset itself.
    """

    notification: dict | None = Field(
        default=None,
        description="The notification document to send.",
    )
    endpoint_path: str = Field(
        default="", description="Notification API path appended to the endpoint."
    )
    dataplane_url: str | None = Field(
        default=None,
        description="Direct mode: data-plane URL to POST to; its presence selects that mode.",
    )
    edr_token: str = Field(
        default="",
        description="Direct mode: authorization token for that data-plane URL.",
    )
    content: dict | None = Field(
        default=None,
        description="Older spelling of 'notification' — the document to send.",
    )
    timeout: float = Field(default=30, gt=0, description="Request timeout in seconds.")

    @property
    def is_direct(self) -> bool:
        """Whether this call goes straight to a data-plane rather than through the SDK."""
        return self.dataplane_url is not None

    @model_validator(mode="after")
    def _neither_mode_can_invent_a_notification(self) -> SendNotificationParams:
        """Neither mode can invent the document it is asked to send."""
        if self.notification is None and self.content is None:
            raise ValueError("'notification' is required")
        return self

    def document(self) -> dict:
        """The notification document, from whichever of the two keys carried it.

        Read by both modes, so a script that wrote ``content`` sends the same
        document whether it goes through the SDK or straight at a data plane —
        which it did not before: the SDK path used to read ``notification``
        alone and silently send an empty notification for a ``content`` script.
        """
        return dict(self.notification or self.content or {})

    def direct_url(self) -> str:
        """The data-plane URL to POST at, with the notification API path appended."""
        base = (self.dataplane_url or "").rstrip("/")
        path = self.endpoint_path.strip()
        if not path:
            return base
        return f"{base}/{path.lstrip('/')}"

    def direct_body(self) -> dict:
        """The body to POST in direct mode, with any metadata the script passed alongside."""
        body = self.document()
        extras = self.model_extra or {}
        for key in _NOTIFICATION_METADATA:
            if key in extras:
                body.setdefault(key, extras[key])
        return body


class SendNotificationOutput(StepPayload):
    """Output contract of ``notification/consumer/send``.

    Whatever the receiver answered, spread at the top level, plus the three
    parts of its answer named outright — status code, body and headers — so a
    script can assert on any of them without reaching into the HTTP record.
    """

    model_config = ConfigDict(extra="allow")

    status_code: int | None = Field(
        default=None, description="Status code the receiver answered with."
    )
    response_body: Any | None = Field(default=None, description="Body the receiver answered with.")
    response_headers: dict | None = Field(
        default=None, description="Headers the receiver answered with."
    )


@step("notification/consumer/send")
class SendNotificationStep(BaseStep[SendNotificationParams, SendNotificationOutput]):
    """Send a notification through the dataspace.

    Supports two modes:
    - **Dataplane-direct mode**: ``dataplane_url``, ``edr_token``, ``endpoint_path``,
      ``notification`` — what the IDE's Send Notification block emits
    - **SDK mode**: ``notification``, ``counter_party_id``, ``counter_party_address``
    """

    params_model = SendNotificationParams
    output_model = SendNotificationOutput

    async def execute(
        self,
        params: SendNotificationParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[SendNotificationOutput]:
        if params.is_direct:
            return await self._execute_dataplane_direct(params)
        return await self._execute_sdk_notification(params, context)

    async def _execute_sdk_notification(
        self,
        params: SendNotificationParams,
        context: StepContext,
    ) -> StepOutput[SendNotificationOutput]:
        """Canonical mode: send via SDK NotificationConsumerService."""
        notif_service = context.dataspace.notifications()
        from tractusx_sdk.industry.models.notifications.notification import Notification

        notification = Notification(**params.document())
        party = params.counter_party(context)
        result = await asyncio.to_thread(
            notif_service.send_notification,
            provider_bpn=party.identity,
            provider_dsp_url=party.address,
            notification=notification,
            endpoint_path=params.endpoint_path,
            timeout=params.timeout,
        )

        status_code = 200
        return StepOutput(
            value=SendNotificationOutput.model_validate(
                {
                    **(result if isinstance(result, dict) else {}),
                    "status_code": status_code,
                    "response_body": result,
                    "response_headers": {},
                }
            ),
            request=HttpRequest(method="POST", url=party.address, body=notification.to_data()),
            response=HttpResponse(status_code=status_code, body=result),
        )

    async def _execute_dataplane_direct(
        self,
        params: SendNotificationParams,
    ) -> StepOutput[SendNotificationOutput]:
        """CCM mode: POST directly to dataplane URL with EDR auth token."""
        url = params.direct_url()
        body = params.direct_body()
        headers = {"Content-Type": "application/json"}
        if params.edr_token:
            headers["Authorization"] = params.edr_token

        response_headers: dict[str, str] = {}
        try:
            resp = await http_client.request(
                "POST", url, json=body, headers=headers, timeout=params.timeout
            )
            result = resp.json() if resp.content else {}
            status_code = resp.status_code
            response_headers = dict(resp.headers)
        except (httpx.HTTPError, ValueError) as exc:
            _logger.warning("Dataplane notification failed: %s", exc)
            result = {"error": str(exc)}
            status_code = 500

        return StepOutput(
            value=SendNotificationOutput.model_validate(
                {
                    **(result if isinstance(result, dict) else {}),
                    "status_code": status_code,
                    "response_body": result,
                    "response_headers": response_headers,
                }
            ),
            request=HttpRequest(method="POST", url=url, body=body),
            response=HttpResponse(status_code=status_code, headers=response_headers, body=result),
        )


# ---------------------------------------------------------------------------
# notification/consumer/discover_assets
# ---------------------------------------------------------------------------


class DiscoverNotificationAssetsParams(CounterPartyParams):
    """Input contract of ``notification/consumer/discover_assets``."""

    timeout: float = Field(default=60, gt=0, description="Discovery timeout in seconds.")


class NotificationAssetsOutput(StepValue[Any]):
    """The notification datasets found in the provider's catalog."""


@step("notification/consumer/discover_assets")
class DiscoverNotificationAssetsStep(
    BaseStep[DiscoverNotificationAssetsParams, NotificationAssetsOutput]
):
    """Discover notification assets in a provider catalog."""

    params_model = DiscoverNotificationAssetsParams
    output_model = NotificationAssetsOutput

    async def execute(
        self,
        params: DiscoverNotificationAssetsParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[NotificationAssetsOutput]:
        notif_service = context.dataspace.notifications()
        party = params.counter_party(context)
        datasets = await sdk_call.run(
            notif_service.discover_notification_assets,
            provider_bpn=party.identity,
            provider_dsp_url=party.address,
            timeout=params.timeout,
        )

        return StepOutput(
            value=NotificationAssetsOutput(datasets),
            request=HttpRequest(method="POST", url=party.address),
            response=HttpResponse(status_code=200, body=datasets),
        )
