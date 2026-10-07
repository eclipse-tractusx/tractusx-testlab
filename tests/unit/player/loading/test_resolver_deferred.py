################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A flow step's nested steps reach it as written, and resolve when they run."""

from __future__ import annotations

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import Job
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.loading.resolver import resolve_params, try_resolve_params
from tractusx_testlab.services.instances import ServiceManager

_NESTED = [{"uses": "util/log", "with": {"message": "${{ each.item }}"}}]


@pytest.fixture()
def context() -> StepContext:
    context = StepContext(
        services=ServiceManager(), job=Job(job_id="run-1"), config=TestlabConfig()
    )
    context.set_variable("ids", ["a"])
    return context


def test_a_deferred_key_is_handed_over_as_written(context: StepContext) -> None:
    resolved = resolve_params({"items": "${{ env.ids }}", "steps": _NESTED}, context, {"steps"})

    assert resolved == {"items": ["a"], "steps": _NESTED}


def test_without_deferral_a_name_the_loop_binds_later_does_not_resolve(
    context: StepContext,
) -> None:
    assert try_resolve_params({"steps": _NESTED}, context) is None
