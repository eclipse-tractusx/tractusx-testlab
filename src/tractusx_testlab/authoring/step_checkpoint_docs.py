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

"""The step reference's line about a step that is a checkpoint (ADR-0028)."""

from __future__ import annotations

from tractusx_testlab.models.primitives.checkpoint import Checkpoint, Direction

#: What each direction asks of whoever runs the test.
MEANINGS: dict[Direction, str] = {
    Direction.INBOUND: "your system calls the Test Suite, which answers",
    Direction.OUTBOUND: "the Test Suite calls your system, which has to answer",
    Direction.INTERNAL: "you choose in the Test Suite; nothing is called",
}


def render_checkpoint(checkpoint: Checkpoint | None) -> list[str]:
    """The paragraph a checkpoint step's reference entry carries; none for any other step."""
    if checkpoint is None:
        return []
    via = f", via `{checkpoint.via}`" if checkpoint.via else ""
    return [
        f"**Checkpoint** — `{checkpoint.direction}`{via}: {MEANINGS[checkpoint.direction]}. "
        "Every use of the step is one; a test switches it off with `checkpoint: false`.",
        "",
    ]
