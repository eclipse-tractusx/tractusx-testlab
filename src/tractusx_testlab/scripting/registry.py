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

"""Version-aware registry mapping (step_type, dataspace_version) to BaseStep classes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tractusx_testlab.steps.base import BaseStep

logger = logging.getLogger(__name__)

# Registry: (step_type, dataspace_version) -> BaseStep class
_REGISTRY: dict[tuple[str, str], type["BaseStep"]] = {}

# Global (version-agnostic) steps: step_type -> BaseStep class
_GLOBAL_REGISTRY: dict[str, type["BaseStep"]] = {}


class StepRegistry:
    """Manages the mapping of step type names to BaseStep implementations."""

    @staticmethod
    def register(
        step_type: str,
        dataspace_version: Optional[str] = None,
    ):
        """Decorator to register a BaseStep class.

        Args:
            step_type: The canonical step key used in YAML
                (e.g., ``connector/provider/create_asset``).
            dataspace_version: Restrict to a specific version (e.g., ``saturn``).
                If ``None``, the step is available for all versions.
        """
        def decorator(cls: type["BaseStep"]) -> type["BaseStep"]:
            # Stamp the canonical key onto the class so a step can describe its
            # own contract (BaseStep.describe) without a registry lookup.
            cls.step_type = step_type
            if dataspace_version:
                key = (step_type, dataspace_version)
                _REGISTRY[key] = cls
                logger.debug("Registered step %s for %s", step_type, dataspace_version)
            else:
                _GLOBAL_REGISTRY[step_type] = cls
                logger.debug("Registered global step %s", step_type)
            return cls
        return decorator

    @staticmethod
    def get(step_type: str, dataspace_version: str) -> Optional[type["BaseStep"]]:
        """Look up a step class by type and version.

        Version-specific registrations take priority over global ones.
        """
        cls = _REGISTRY.get((step_type, dataspace_version))
        if cls:
            return cls
        return _GLOBAL_REGISTRY.get(step_type)

    @staticmethod
    def has(step_type: str, dataspace_version: str) -> bool:
        return StepRegistry.get(step_type, dataspace_version) is not None

    @staticmethod
    def list_step_types(dataspace_version: Optional[str] = None) -> list[str]:
        """Return all registered step type names, optionally filtered by version."""
        types = set(_GLOBAL_REGISTRY.keys())
        if dataspace_version:
            types.update(entry[0] for entry in _REGISTRY if entry[1] == dataspace_version)
        else:
            types.update(entry[0] for entry in _REGISTRY)
        return sorted(types)

    @staticmethod
    def clear():
        """Remove all registrations (for testing)."""
        _REGISTRY.clear()
        _GLOBAL_REGISTRY.clear()


# Convenience alias
step = StepRegistry.register
