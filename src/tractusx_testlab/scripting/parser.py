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

"""YAML parser — fail-fast loading of test scripts and TCK manifests.

Delegates all alias resolution and model validation to Pydantic's
``TypeAdapter`` after checking for the mandatory ``syntax`` / ``testlab``
discriminator key.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import TypeAdapter

from tractusx_testlab.models.authoring.definitions import (
    ScriptDefinition,
    TckDefinition,
)
from tractusx_testlab.syntax import diagnostics

_SCRIPT_ADAPTER: TypeAdapter[ScriptDefinition] = TypeAdapter(ScriptDefinition)
_TCK_ADAPTER: TypeAdapter[TckDefinition] = TypeAdapter(TckDefinition)

_INCLUDE_PREFIX = "!include "


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, returning the top-level mapping.

    A parse failure is turned into the author's finding here, where the file
    that failed is known. Left as a ``yaml.YAMLError`` it reached the terminal
    as a rich traceback of the compiler's own call stack — the parser's line
    and column were in there, several screens down.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(str(diagnostics.unparseable(exc, path))) from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping at top level in {path}")
    return data


def _normalize_discriminator(data: dict, path: Path) -> dict:
    """Validate that the ``syntax`` discriminator key is present."""
    if "syntax" not in data:
        raise ValueError(
            f"Error in {path}: Missing mandatory field 'syntax'. Expected 'syntax: v1-alpha'."
        )
    return data


class YamlParser:
    """Parses YAML test scripts and TCK manifests into definition models."""

    @staticmethod
    def parse_script(path: Path) -> ScriptDefinition:
        """Parse a script YAML file into a ``ScriptDefinition``."""
        data = _load_yaml(path)
        normalized = _normalize_discriminator(data, path)
        return _SCRIPT_ADAPTER.validate_python(normalized)

    @staticmethod
    def parse_tck(path: Path) -> TckDefinition:
        """Parse a TCK manifest YAML file into a ``TckDefinition``."""
        data = _load_yaml(path)
        normalized = _normalize_discriminator(data, path)
        return _TCK_ADAPTER.validate_python(normalized)

    @staticmethod
    def parse_script_from_dict(data: dict, path: Path | None = None) -> ScriptDefinition:
        """Parse a script from an already-loaded YAML dict."""
        normalized = _normalize_discriminator(data, path or Path("<dict>"))
        return _SCRIPT_ADAPTER.validate_python(normalized)

    @staticmethod
    def parse_tck_from_dict(data: dict, path: Path | None = None) -> TckDefinition:
        """Parse a TCK from an already-loaded YAML dict."""
        normalized = _normalize_discriminator(data, path or Path("<dict>"))
        return _TCK_ADAPTER.validate_python(normalized)
