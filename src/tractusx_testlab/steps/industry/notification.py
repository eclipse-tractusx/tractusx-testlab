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
from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

_logger = logging.getLogger(__name__)


@step("industry/notification/send", aliases=["send_notification"])
class SendNotificationStep(BaseStep):
    """Send a notification through the dataspace.

    Supports two modes:
    - **SDK mode** (canonical): ``notification``, ``provider_bpn``, ``provider_dsp_url``
    - **Dataplane-direct mode** (CCM): ``dataplane_url``, ``edr_token``, ``content``
    """

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        # Detect mode: CCM dataplane-direct vs. canonical SDK notification
        if "dataplane_url" in params or "endpoint_url" in params:
            return await self._execute_dataplane_direct(params, context)
        return await self._execute_sdk_notification(params, context)

    async def _execute_sdk_notification(
        self, params: dict, context: "StepContext",
    ) -> StepOutput:
        """Canonical mode: send via SDK NotificationConsumerService."""
        notif_service = context.get_notification_service()
        from tractusx_sdk.industry.models.notifications.notification import Notification

        notification = Notification(**params["notification"])
        provider_bpn = params["provider_bpn"]
        provider_dsp = params["provider_dsp_url"]
        endpoint_path = params.get("endpoint_path", "")

        result = await asyncio.to_thread(
            notif_service.send_notification,
            provider_bpn=provider_bpn,
            provider_dsp_url=provider_dsp,
            notification=notification,
            endpoint_path=endpoint_path,
            timeout=params.get("timeout", 30),
        )

        return StepOutput(
            value=result,
            request=HttpRequest(method="POST", url=provider_dsp, body=notification.to_data()),
            response=HttpResponse(status_code=200 if result else 500, body=result),
        )

    async def _execute_dataplane_direct(
        self, params: dict, context: "StepContext",
    ) -> StepOutput:
        """CCM mode: POST directly to dataplane URL with EDR auth token."""
        import httpx

        dataplane_url = params.get("dataplane_url") or params.get("endpoint_url", "")
        edr_token = params.get("edr_token") or params.get("auth_token", "")

        # Build notification body from CCM params
        body: dict = {}
        if "content" in params:
            body = dict(params["content"])
        elif "payload" in params:
            body = dict(params["payload"])

        # Enrich body with notification metadata when provided
        for key in ("notification_id", "sender_bpn", "recipient_bpn", "type", "status"):
            if key in params:
                body.setdefault(key, params[key])

        headers = {"Authorization": edr_token} if edr_token else {}
        headers["Content-Type"] = "application/json"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(dataplane_url, json=body, headers=headers, timeout=30)
                result = resp.json() if resp.content else {}
                status_code = resp.status_code
        except (httpx.HTTPError, ValueError) as exc:
            _logger.warning("Dataplane notification failed: %s", exc)
            result = {"error": str(exc)}
            status_code = 500

        return StepOutput(
            value={"status_code": status_code, **result},
            request=HttpRequest(method="POST", url=dataplane_url, body=body),
            response=HttpResponse(status_code=status_code, body=result),
        )


@step("industry/notification/discover_assets", aliases=["discover_notification_assets"])
class DiscoverNotificationAssetsStep(BaseStep):
    """Discover notification assets in a provider catalog."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        notif_service = context.get_notification_service()
        provider_bpn = params["provider_bpn"]
        provider_dsp = params["provider_dsp_url"]

        datasets = notif_service.discover_notification_assets(
            provider_bpn=provider_bpn,
            provider_dsp_url=provider_dsp,
            timeout=params.get("timeout", 60),
        )

        return StepOutput(
            value=datasets,
            request=HttpRequest(method="POST", url=provider_dsp),
            response=HttpResponse(status_code=200, body=datasets),
        )
