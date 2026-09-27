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

"""``labs/mock/api/dynamic`` — a mock that works out its reply per call. **Experimental.**

``mock/api`` answers every call with the same canned reply. This one runs
steps for each call first — the mock's ``process`` — and reads its reply
after them, so the reply can depend on what the call carried: echo its
``messageId``, swap its sender and receiver, answer COMPLETED or REJECTED.

- :mod:`.params` — the step's input contract.
- :mod:`.call` — answering one call: its own context, its steps, its reply.
- :mod:`.step` — the step, registering the mock with a handler.
"""

from tractusx_testlab.extensions.labs.steps.dynamic_mock import step

__all__ = ["step"]
