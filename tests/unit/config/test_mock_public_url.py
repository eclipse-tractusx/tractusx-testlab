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

"""``mock_public_url`` — the mock server's address as the SUT reaches it."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tractusx_testlab.config.settings import TestlabConfig


class TestMockPublicUrl:
    def test_unset_it_resolves_to_localhost_on_the_server_port(self) -> None:
        config = TestlabConfig(server_port=8123)

        assert config.mock_public_url is None
        assert config.mock_base_url == "http://localhost:8123"

    def test_set_it_is_the_root_every_mock_url_is_built_on(self) -> None:
        config = TestlabConfig(mock_public_url="https://testlab.example.com")

        assert config.mock_base_url == "https://testlab.example.com"

    def test_a_trailing_slash_is_dropped(self) -> None:
        config = TestlabConfig(mock_public_url="http://engine:8100/")

        assert config.mock_public_url == "http://engine:8100"

    def test_blank_means_unset(self) -> None:
        config = TestlabConfig(mock_public_url="   ")

        assert config.mock_public_url is None
        assert config.mock_base_url == "http://localhost:8100"

    def test_a_bare_hostname_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="http://"):
            TestlabConfig(mock_public_url="testlab.example.com")

    def test_it_is_settable_from_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TESTLAB_MOCK_PUBLIC_URL", "https://lab.example.com/")

        assert TestlabConfig().mock_base_url == "https://lab.example.com"
