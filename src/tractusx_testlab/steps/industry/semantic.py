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

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepParams, StepPayload

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


# ---------------------------------------------------------------------------
# validate/semantic_schema
# ---------------------------------------------------------------------------


class ValidateSemanticSchemaParams(StepParams):
    """Input contract of ``validate/semantic_schema``."""

    source: str = Field(description="Name of the context variable holding the JSON data.")
    schema_ref: str = Field(
        description="Schema reference identifier, e.g. 'CX-0135'."
    )
    required_keys: list[str] = Field(
        default_factory=list,
        description="Overrides the keys the schema reference is known to require.",
    )


class SemanticSchemaOutput(StepPayload):
    """Which required keys the payload carried, and which it was missing."""

    is_valid: bool = Field(description="True when no required key is missing.")
    schema_ref: str = Field(description="The schema reference that was checked.")
    missing_keys: list[str] = Field(description="Required keys absent from the payload.")
    checked_keys: list[str] = Field(description="Every key the payload was checked for.")


@step("validate/semantic_schema")
class ValidateSemanticSchemaStep(
    BaseStep[ValidateSemanticSchemaParams, SemanticSchemaOutput]
):
    """Check a payload for the top-level keys a Catena-X semantic model requires.

    Unlike ``validate/schema`` this does not fail the step — it reports what it
    found, so a script can assert on ``is_valid`` or inspect ``missing_keys``.
    """

    params_model = ValidateSemanticSchemaParams
    output_model = SemanticSchemaOutput

    async def execute(
        self,
        params: ValidateSemanticSchemaParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[SemanticSchemaOutput]:
        data = context.get_variable(params.source)
        if data is None:
            raise KeyError(f"Context variable '{params.source}' not found")
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for validation, got {type(data).__name__}")

        required_keys = params.required_keys or _SCHEMA_REQUIRED_KEYS.get(params.schema_ref, [])
        if not required_keys:
            logger.warning("No required keys defined for schema_ref '%s'", params.schema_ref)

        is_valid, missing = _validate_keys(data, required_keys)

        logger.debug(
            "Schema validation for '%s': %s (missing: %s)",
            params.schema_ref,
            "PASS" if is_valid else "FAIL",
            missing,
        )

        return StepOutput(
            value=SemanticSchemaOutput(
                is_valid=is_valid,
                schema_ref=params.schema_ref,
                missing_keys=missing,
                checked_keys=required_keys,
            )
        )
