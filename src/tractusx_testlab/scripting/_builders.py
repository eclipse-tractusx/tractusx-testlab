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

"""Builders for parsing variable definitions and service declarations.

Step and assertion parsing are now handled by Pydantic model validation
via ``YamlParser`` / ``TypeAdapter``.  This module retains only the helpers
needed at runtime for environment variable resolution and service wiring.
"""

from __future__ import annotations

import tractusx_testlab.syntax.keys as keys
from tractusx_testlab.models import (
    VariableDefinition,
)
from tractusx_testlab.models.authoring.definitions import ServiceDefinition
from tractusx_testlab.models.primitives.enums import ServiceType
from tractusx_testlab.scripting._variable_form import VariablesBlock, parse_variables_block
from tractusx_testlab.syntax import defaults


def parse_variables(raw: VariablesBlock) -> dict[str, VariableDefinition]:
    """Parse a variables block (legacy mapping or verb-form list) into definitions."""
    return parse_variables_block(raw)


def parse_service(raw: dict) -> ServiceDefinition:
    """Parse a single service dict into a ServiceDefinition."""
    raw_type = raw.get(keys.TYPE, defaults.SERVICE_TYPE)

    base_url = raw.get(keys.BASE_URL, "")
    config_block = raw.get(keys.CONFIG)
    if not base_url and isinstance(config_block, dict):
        base_url = config_block.get(keys.MANAGEMENT_URL, defaults.BASE_URL)

    return ServiceDefinition(
        name=raw.get(keys.NAME, defaults.NAME),
        type=ServiceType(raw_type.upper() if isinstance(raw_type, str) else raw_type),
        base_url=base_url or defaults.BASE_URL,
        auth=raw.get(keys.AUTH, {}),
        params=raw.get(keys.PARAMS),
    )
