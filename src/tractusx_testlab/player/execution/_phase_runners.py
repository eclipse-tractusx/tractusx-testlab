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

"""Phase runners — barrel re-export preserving existing import paths.

The implementation now lives in ``player.execution.phases`` package.
This module re-exports the public API so that existing callers remain unchanged.
"""

from tractusx_testlab.player.execution.phases.execution import run_execution as execute_main_steps
from tractusx_testlab.player.execution.phases.setup import run_setup as execute_setup_steps
from tractusx_testlab.player.execution.phases.teardown import run_teardown as execute_teardown_steps

__all__ = ["execute_setup_steps", "execute_main_steps", "execute_teardown_steps"]
