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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""extensions.testlab — automated interoperability testing for Tractus-X dataspaces."""

from tractusx_testlab.compiler.compiler import Compiler
from tractusx_testlab.compiler.validation.validator import ScriptValidator
from tractusx_testlab.config.loader import ConfigLoader
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.infrastructure import (
    ConnectorBinding,
    DtrBinding,
    EngineBindings,
    EngineDtrBinding,
    Infrastructure,
    InfrastructureManager,
    SutBindings,
    SutConnectorBinding,
)
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.scripting.parser import YamlParser
from tractusx_testlab.scripting.registry import StepRegistry, step
from tractusx_testlab.scripting.script import Tck as Tck  # SDK alias
from tractusx_testlab.scripting.script import TestScript
from tractusx_testlab.security.trust.identity import PlayerIdentity
from tractusx_testlab.server.app import create_app
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput

__all__ = [
    # Steps
    "BaseStep",
    # Compiler
    "Compiler",
    # Config
    "ConfigLoader",
    # Infrastructure
    "ConnectorBinding",
    "DtrBinding",
    "EngineBindings",
    "EngineDtrBinding",
    "Infrastructure",
    "InfrastructureManager",
    "JobManager",
    # Security
    "PlayerIdentity",
    "ScriptValidator",
    "StepContext",
    "StepOutput",
    "StepRegistry",
    "SutBindings",
    "SutConnectorBinding",
    "Tck",
    "TestScript",
    "TestlabConfig",
    # Player
    "TestlabPlayer",
    # Scripting
    "YamlParser",
    # Server
    "create_app",
    "step",
]
