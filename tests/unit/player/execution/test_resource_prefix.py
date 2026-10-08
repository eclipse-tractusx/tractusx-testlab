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
## This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: GPT-6).
## It was reviewed and tested by a human committer.

"""The player uses the host's prefix and its actual run ID."""

import pytest

from tractusx_testlab.authoring.parser import YamlParser
from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import clear_callback_manager, set_callback_manager


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", [None, "cx-test-suite:"])
async def test_session_resource_namespace_uses_the_run_id(tmp_path, prefix):
    config = TestlabConfig(logs_dir=tmp_path / "logs", data_dir=tmp_path / "data")
    player = TestlabPlayer(config=config, **({"resource_prefix": prefix} if prefix else {}))
    tck = Tck.from_single_test(
        YamlParser.parse_test_from_dict(
            {
                "syntax": "v1-alpha",
                "kind": "test",
                "id": "empty",
                "namespace": "test",
                "metadata": {"name": "Empty", "version": "1.0"},
                "execution": [],
            }
        )
    )
    set_callback_manager(CallbackManager())
    try:
        session = await player.open_session(
            tck,
            job_id="run-a",
            runtime_vars={"execution.id": "other-run", "execution.resource_prefix": "other-app:"},
        )
        try:
            context = session._context
            assert context.resource_id("asset") == (prefix or "testlab:") + "run-a:asset"
            assert context.resource_id(context.resource_id("asset")) == context.resource_id("asset")
            assert context.get_variable("execution.id") == "run-a"
            assert (
                context.get_variable("execution.resource_prefix")
                == (prefix or "testlab:") + "run-a:"
            )
        finally:
            await session.close()
    finally:
        clear_callback_manager()


@pytest.mark.parametrize("prefix", ["", "cx-test-suite", "test_lab:", "testlab:%", "../"])
def test_prefix_rejects_empty_or_wildcard_namespaces(tmp_path, prefix):
    with pytest.raises(ValueError, match="resource_prefix"):
        TestlabPlayer(config=TestlabConfig(logs_dir=tmp_path), resource_prefix=prefix)
