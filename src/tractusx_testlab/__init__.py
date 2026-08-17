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

"""extensions.testlab — automated interoperability testing for Tractus-X dataspaces."""

from tractusx_testlab.compiler.compiler import Compiler
from tractusx_testlab.compiler.packager import Packager
from tractusx_testlab.compiler.validation.validator import ScriptValidator
from tractusx_testlab.config.loader import ConfigLoader
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.infrastructure import (
    ConnectorBinding,
    DtrBinding,
    EngineBindings,
    Infrastructure,
    InfrastructureManager,
    SubmodelServerBinding,
    SutBindings,
)
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.scripting.parser import YamlParser
from tractusx_testlab.scripting.registry import StepRegistry, step
from tractusx_testlab.scripting.script import Tck as Tck, TestScript  # SDK alias
from tractusx_testlab.security.trust.identity import PlayerIdentity
from tractusx_testlab.server.app import create_app
from tractusx_testlab.steps.base import BaseStep, StepOutput

__all__ = [
    # Player
    "TestlabPlayer",
    "StepContext",
    "JobManager",
    # Compiler
    "Compiler",
    "Packager",
    "ScriptValidator",
    # Scripting
    "YamlParser",
    "StepRegistry",
    "step",
    "Tck",
    "TestScript",
    # Steps
    "BaseStep",
    "StepOutput",
    # Config
    "ConfigLoader",
    "TestlabConfig",
    # Infrastructure
    "ConnectorBinding",
    "DtrBinding",
    "EngineBindings",
    "Infrastructure",
    "InfrastructureManager",
    "SubmodelServerBinding",
    "SutBindings",
    # Security
    "PlayerIdentity",
    # Server
    "create_app",
]
