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

## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""The notification service is the SDK's, wrapped around the seeded consumer.

Returning the consumer itself, as ``notifications()`` once did, gave the
notification steps an object without ``discover_notification_assets`` or
``send_notification`` (E2E run 34633071862).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tractusx_sdk.industry.services.notifications import NotificationConsumerService

from tractusx_testlab.contracts import NotificationService
from tractusx_testlab.models import ServiceType
from tractusx_testlab.player.execution.dataspace_access import DataspaceAccess


def _access(consumer: MagicMock) -> DataspaceAccess:
    services = MagicMock()
    services.service_names = ["engine-connector"]
    services.get.side_effect = lambda name, stype=None: (
        consumer if stype is ServiceType.CONNECTOR_CONSUMER else MagicMock()
    )
    return DataspaceAccess(services)


class TestNotifications:
    def test_it_is_the_sdk_service_over_the_consumer(self) -> None:
        consumer = MagicMock()
        service = _access(consumer).notifications()
        assert isinstance(service, NotificationConsumerService)
        assert service.connector_consumer is consumer

    def test_it_satisfies_the_contract_the_steps_are_written_against(self) -> None:
        assert isinstance(_access(MagicMock()).notifications(), NotificationService)

    def test_it_is_built_once(self) -> None:
        access = _access(MagicMock())
        assert access.notifications() is access.notifications()
