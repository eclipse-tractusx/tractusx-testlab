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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4).
## It was reviewed and tested by a human committer.

"""Semantic schema validation step — validates required top-level keys by schema reference."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

# Configurable registry of known schema references and their required top-level keys.
# Extend this mapping as new Catena-X standards are supported.
_SCHEMA_REQUIRED_KEYS: dict[str, list[str]] = {
    "CX-0135": ["catenaXId", "childItems"],
    "CX-0126": ["catenaXId", "sites"],
    "CX-0001": ["assetId", "globalAssetId", "specificAssetIds"],
    "CX-0002": ["idShort", "submodelElements"],
}


def _validate_keys(data: dict, required_keys: list[str]) -> tuple[bool, list[str]]:
    """Check that all required keys exist in the data dict.

    Returns:
        Tuple of (is_valid, list of missing key names).
    """
    missing = [key for key in required_keys if key not in data]
    return len(missing) == 0, missing


@step("industry/semantic/validate", aliases=["validate_semantic_schema", "validate/semantic_schema"])
class ValidateSemanticSchemaStep(BaseStep):
    """Validate a JSON payload against expected top-level keys for a semantic model.

    Params:
        source (str): Context variable name containing the JSON data.
        schema_ref (str): Schema reference identifier (e.g. ``CX-0135``).
        required_keys (list[str], optional): Override the default required keys.

    Output:
        Dict with ``is_valid``, ``schema_ref``, ``missing_keys``, and ``checked_keys``.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput:
        source_name = params["source"]
        schema_ref = params["schema_ref"]

        data = context.get_variable(source_name)
        if data is None:
            raise KeyError(f"Context variable '{source_name}' not found")
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for validation, got {type(data).__name__}")

        required_keys = params.get("required_keys") or _SCHEMA_REQUIRED_KEYS.get(schema_ref, [])
        if not required_keys:
            logger.warning("No required keys defined for schema_ref '%s'", schema_ref)

        is_valid, missing = _validate_keys(data, required_keys)

        result = {
            "is_valid": is_valid,
            "schema_ref": schema_ref,
            "missing_keys": missing,
            "checked_keys": required_keys,
        }

        logger.debug(
            "Schema validation for '%s': %s (missing: %s)",
            schema_ref,
            "PASS" if is_valid else "FAIL",
            missing,
        )

        return StepOutput(value=result)
