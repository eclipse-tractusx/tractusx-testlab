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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A test's ``checkpoint:`` key on a step — mark it a checkpoint, or switch it off (ADR-0028).

A step type that is a checkpoint declares it on its ``@step`` decorator. A test
author can go further, on any step, with one key::

    checkpoint: true                  # this step is a checkpoint
    checkpoint: false                 # this one is not, whatever its type declares
    checkpoint:                       # it is, and this is what the run calls it
      label: The SUT accepts the certificate
      description: Your connector has to answer the push with 2xx.
      direction: outbound             # only for a step type that declares none

A step type that declares nothing becomes an ``outbound`` checkpoint unless the
mark gives another direction: most steps call the system under test.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from tractusx_testlab.models.primitives.checkpoint import Direction, Via


class CheckpointMark(BaseModel):
    """What a test says about a step it marks a checkpoint."""

    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, description="What the run calls the checkpoint.")
    description: str | None = Field(
        default=None, description="What whoever acts has to do, in a sentence or two."
    )
    direction: Direction | None = Field(
        default=None,
        description=(
            "'inbound', 'outbound' or 'internal' — for a step type that declares no "
            "checkpoint of its own; 'outbound' when left out."
        ),
    )
    via: Via | None = Field(
        default=None, description="'direct' or 'dataplane': how the call travels, when it does."
    )
