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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Fail-fast YAML parser using Pydantic TypeAdapter and discriminated unions.

Checks for the mandatory ``testlab`` / ``syntax`` discriminator key before
delegating fully to Pydantic for alias resolution and model validation.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from tractusx_testlab.models.authoring.definitions import (
    ScriptDefinition,
    TckDefinition,
)

logger = logging.getLogger(__name__)

_SCRIPT_ADAPTER: TypeAdapter[ScriptDefinition] = TypeAdapter(ScriptDefinition)
_TCK_ADAPTER: TypeAdapter[TckDefinition] = TypeAdapter(TckDefinition)


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and assert it is a mapping."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
    return data


def _normalize_discriminator(data: dict, path: Path) -> dict:
    """Validate that the ``syntax`` discriminator key is present."""
    if "syntax" not in data:
        raise ValueError(
            f"Error in {path}: Missing mandatory field 'syntax'. Expected 'syntax: v1-alpha'."
        )
    return data


def parse_script_file(path: Path) -> ScriptDefinition:
    """Load and parse a single script YAML file using strict syntax routing."""
    data = _load_yaml(path)
    normalized = _normalize_discriminator(data, path)
    return _SCRIPT_ADAPTER.validate_python(normalized)


def parse_tck_file(path: Path) -> TckDefinition:
    """Load and parse a TCK manifest YAML file using strict syntax routing."""
    data = _load_yaml(path)
    normalized = _normalize_discriminator(data, path)
    return _TCK_ADAPTER.validate_python(normalized)
