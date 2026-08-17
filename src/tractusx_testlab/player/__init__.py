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

"""Player module — test execution engine.

Sub-modules:
    execution — core player, step context, and execution monitor
    loading   — TCK loading and parameter resolution
    jobs      — job lifecycle management
"""

from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.player.loading.resolver import resolve_params

__all__ = [
    "ExecutionMonitor",
    # Jobs
    "JobManager",
    # Loading
    "Loader",
    # Execution
    "StepContext",
    "TestlabPlayer",
    "resolve_params",
]
