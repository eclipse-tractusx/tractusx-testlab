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

"""Pull data shortcut steps — registers all 3 step types."""

from __future__ import annotations

from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.pull_data._constants import (
    STEP_PULL_DATA_FILTERED,
    STEP_PULL_DATA_FILTERED_BY_POLICY,
    STEP_TYPES,
)
from tractusx_testlab.steps.pull_data._executor import (
    ConnectorPullDataFiltered,
    PullDataFiltered,
    PullDataFilteredByPolicy,
)

__all__ = ["STEP_TYPES"]

step("connector/consumer/pull_data_filtered", aliases=[STEP_PULL_DATA_FILTERED])(PullDataFiltered)
step("connector/consumer/pull_data_filtered_by_policy", aliases=[STEP_PULL_DATA_FILTERED_BY_POLICY])(PullDataFilteredByPolicy)
step("connector/pull_data_filtered")(ConnectorPullDataFiltered)
