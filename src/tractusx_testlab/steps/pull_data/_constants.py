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

"""Constants for pull_data shortcut step executors."""

from __future__ import annotations

# -- Step type identifiers ----------------------------------------------------
STEP_PULL_DATA_FILTERED = "connector/consumer/pull_data_filtered"
<<<<<<< HEAD
STEP_PULL_DATA_FILTERED_BY_POLICY = "connector/consumer/pull_data_filtered_by_policy"
=======
>>>>>>> 4151bc2 (Refactor step identifiers for consistency and clarity)

STEP_TYPES: list[str] = [
    STEP_PULL_DATA_FILTERED,
]

# -- Default values -----------------------------------------------------------
DEFAULT_MAX_WAIT = 60
DEFAULT_POLL_INTERVAL = 2
