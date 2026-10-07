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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""``async:`` — a test in the manifest that runs when someone asks for it. **Experimental.**

Written on a ``tests:`` entry of ``index.yaml``::

    extensions: [labs]
    tests:
      - id: push-notification.yaml
        async: true

A host that holds the run open between tests (:class:`~tractusx_testlab.player.TckSession`)
runs every other test on its own and leaves this one waiting until it is asked
for, as many times as it is asked for. A run that is not held open — ``testlab
run``, :meth:`TestlabPlayer.run` — runs it in manifest order like any other test.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LabsEntryKeys(BaseModel):
    """The key this extension adds to a ``tests:`` entry of the manifest."""

    #: ``async`` is a Python keyword, so the field carries it as its alias.
    async_: bool = Field(
        default=False,
        alias="async",
        description=(
            "Run this test on demand: a host that holds the run open leaves it "
            "waiting until someone runs it, and lets them run it again. Requires "
            "'extensions: [labs]'."
        ),
    )
