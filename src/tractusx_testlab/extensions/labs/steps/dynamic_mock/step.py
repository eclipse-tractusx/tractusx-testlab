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

"""The ``labs/mock/api/dynamic`` step. **Experimental.**"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.extensions.labs.steps.dynamic_mock.call import CallHandler
from tractusx_testlab.extensions.labs.steps.dynamic_mock.params import (
    REPLY_PARAMS,
    DynamicMockParams,
)
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.mock.api import MockEndpointOutput, publish_mock
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput
from tractusx_testlab.syntax import call_scope

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("labs/mock/api/dynamic")
class DynamicMockStep(BaseStep[DynamicMockParams, MockEndpointOutput]):
    """Register a mock that runs steps for every call and answers with what they worked out.

    It is ``mock/api`` in everything but the reply: the same key, the same
    listener for ``mock/wait/*``, the same published address. Each call runs
    ``process`` on a context of its own — a copy of the run's variables, plus
    the call as ``*.request.*`` — and the reply is read after it, so it can
    name what the steps published (``*.process.<id>.<field>``). A step that
    fails, a reply that cannot be read, or steps slower than
    ``process_timeout`` answer 500.

    The steps run on the event loop of the run that registered the mock, so
    they reach the run's services exactly as its other steps do.
    """

    params_model = DynamicMockParams
    output_model = MockEndpointOutput
    #: Handed over as written: ``process`` runs per call, and the reply is read
    #: after it, so neither can be resolved when the step runs.
    deferred_params = frozenset({"process", *REPLY_PARAMS})
    #: The deferred keys that are values the step resolves, not nested steps.
    template_params = frozenset(REPLY_PARAMS)
    #: What ``process`` and the reply may read besides what the test has.
    body_references = call_scope.request_roots()
    #: Where ``process`` publishes — per call, never under the phase.
    nested_namespace = call_scope.PROCESS

    async def execute(
        self, params: DynamicMockParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[MockEndpointOutput]:
        handler = CallHandler(params, context, asyncio.get_running_loop())
        return publish_mock(params, handler, context, definition)
