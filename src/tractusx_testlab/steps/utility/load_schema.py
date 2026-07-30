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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""load_schema step — loads a JSON schema from file for validation assertions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


@step("util/load_schema")
class LoadSchemaStep(BaseStep):
    """Load a JSON schema from a local file path.

    Params:
        name: Identifier for the loaded schema in context.
        source: Source type — currently only "file" supported.
        path: File path relative to the TCK root directory.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition
    ) -> StepOutput:
        source = params.get("source", "file")
        path = params["path"]

        if source != "file":
            raise ValueError(f"Unsupported schema source: {source}. Only 'file' is supported.")

        schema_path: Path
        tck_root = context.get_variable("_tck_root")
        if tck_root:
            # Strip leading ../ sequences — paths are relative to TCK root, not subdirs
            import re
            normalized = re.sub(r'^(\.\.[\\/])+', '', path)
            schema_path = (Path(tck_root) / normalized).resolve()
        else:
            schema_path = Path(path).resolve()

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
        logger.info("Loaded schema from %s (%d keys)", schema_path, len(schema_data))

        return StepOutput(value=schema_data)
