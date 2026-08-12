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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). 
## It was reviewed and tested by a human committer.

"""Notification steps — reuses SDK NotificationConsumerService."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Optional

import httpx
from pydantic import ConfigDict, Field, model_validator

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import StepParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload, StepValue

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

_logger = logging.getLogger(__name__)

#: Metadata keys copied into the body when a script passes them alongside it.
_NOTIFICATION_METADATA = ("notification_id", "sender_bpn", "recipient_bpn", "type", "status")


class ProviderParams(StepParams):
    """The provider a notification step talks to."""

    provider_bpn: str = Field(default="", description="BPN of the receiving participant.")
    provider_dsp_url: str = Field(
        default="", description="DSP endpoint of the receiving participant's connector."
    )


# ---------------------------------------------------------------------------
# notification/consumer/send
# ---------------------------------------------------------------------------


class SendNotificationParams(ProviderParams):
    """Input contract of ``notification/consumer/send``.

    Two modes share one step.  Giving ``dataplane_url`` picks the direct mode,
    which POSTs straight at a data-plane the DSP flow already opened; leaving it
    out picks the SDK mode, which negotiates the notification asset itself.
    """

    notification: Optional[dict] = Field(
        default=None,
        description="SDK mode: the notification document to send.",
    )
    endpoint_path: str = Field(
        default="", description="SDK mode: path appended to the notification endpoint."
    )
    dataplane_url: Optional[str] = Field(
        default=None,
        description="Direct mode: data-plane URL to POST to; its presence selects that mode.",
    )
    edr_token: str = Field(
        default="",
        description="Direct mode: authorization token for that data-plane URL.",
    )
    content: Optional[dict] = Field(
        default=None,
        description="Direct mode: the notification body.",
    )
    timeout: float = Field(default=30, gt=0, description="Request timeout in seconds.")

    @property
    def is_direct(self) -> bool:
        """Whether this call goes straight to a data-plane rather than through the SDK."""
        return self.dataplane_url is not None

    @model_validator(mode="after")
    def _sdk_mode_needs_a_notification(self) -> "SendNotificationParams":
        """SDK mode cannot invent the document it is asked to send."""
        if not self.is_direct and self.notification is None:
            raise ValueError(
                "either 'dataplane_url' (direct mode) or 'notification' (SDK mode) is required"
            )
        return self

    def direct_body(self) -> dict:
        """The body to POST in direct mode, with any metadata the script passed alongside."""
        body = dict(self.content or {})
        extras = self.model_extra or {}
        for key in _NOTIFICATION_METADATA:
            if key in extras:
                body.setdefault(key, extras[key])
        return body


class SendNotificationOutput(StepPayload):
    """Output contract of ``notification/consumer/send``.

    Whatever the receiver answered, plus — in direct mode — the status code it
    answered with, so a script can assert on it without reaching into the HTTP
    record.
    """

    model_config = ConfigDict(extra="allow")

    status_code: Optional[int] = Field(
        default=None, description="Direct mode: status code the receiver answered with."
    )


@step("notification/consumer/send")
class SendNotificationStep(BaseStep[SendNotificationParams, SendNotificationOutput]):
    """Send a notification through the dataspace.

    Supports two modes:
    - **SDK mode** (canonical): ``notification``, ``provider_bpn``, ``provider_dsp_url``
    - **Dataplane-direct mode** (CCM): ``dataplane_url``, ``edr_token``, ``content``
    """

    params_model = SendNotificationParams
    output_model = SendNotificationOutput

    async def execute(
        self,
        params: SendNotificationParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[SendNotificationOutput]:
        if params.is_direct:
            return await self._execute_dataplane_direct(params)
        return await self._execute_sdk_notification(params, context)

    async def _execute_sdk_notification(
        self, params: SendNotificationParams, context: "StepContext",
    ) -> StepOutput[SendNotificationOutput]:
        """Canonical mode: send via SDK NotificationConsumerService."""
        notif_service = context.get_notification_service()
        from tractusx_sdk.industry.models.notifications.notification import Notification

        notification = Notification(**(params.notification or {}))
        result = await asyncio.to_thread(
            notif_service.send_notification,
            provider_bpn=params.provider_bpn,
            provider_dsp_url=params.provider_dsp_url,
            notification=notification,
            endpoint_path=params.endpoint_path,
            timeout=params.timeout,
        )

        return StepOutput(
            value=SendNotificationOutput.of(result),
            request=HttpRequest(
                method="POST", url=params.provider_dsp_url, body=notification.to_data()
            ),
            response=HttpResponse(status_code=200 if result else 500, body=result),
        )

    async def _execute_dataplane_direct(
        self, params: SendNotificationParams,
    ) -> StepOutput[SendNotificationOutput]:
        """CCM mode: POST directly to dataplane URL with EDR auth token."""
        url = params.dataplane_url or ""
        body = params.direct_body()
        headers = {"Content-Type": "application/json"}
        if params.edr_token:
            headers["Authorization"] = params.edr_token

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, json=body, headers=headers, timeout=params.timeout
                )
                result = resp.json() if resp.content else {}
                status_code = resp.status_code
        except (httpx.HTTPError, ValueError) as exc:
            _logger.warning("Dataplane notification failed: %s", exc)
            result = {"error": str(exc)}
            status_code = 500

        return StepOutput(
            value=SendNotificationOutput.model_validate({"status_code": status_code, **result}),
            request=HttpRequest(method="POST", url=url, body=body),
            response=HttpResponse(status_code=status_code, body=result),
        )


# ---------------------------------------------------------------------------
# notification/consumer/discover_assets
# ---------------------------------------------------------------------------


class DiscoverNotificationAssetsParams(ProviderParams):
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
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[NotificationAssetsOutput]:
        notif_service = context.get_notification_service()
        datasets = notif_service.discover_notification_assets(
            provider_bpn=params.provider_bpn,
            provider_dsp_url=params.provider_dsp_url,
            timeout=params.timeout,
        )

        return StepOutput(
            value=NotificationAssetsOutput(datasets),
            request=HttpRequest(method="POST", url=params.provider_dsp_url),
            response=HttpResponse(status_code=200, body=datasets),
        )
