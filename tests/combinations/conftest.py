################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""Fixtures for the combination tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from combinations.harness import Harness, build_context
from combinations.http_double import HttpDouble


@pytest.fixture()
def harness() -> Harness:
    """A fresh context per test — variables must not leak between chains."""
    return Harness(build_context())


@pytest.fixture()
def http() -> Generator[HttpDouble, None, None]:
    """A stopped HTTP double; call ``start()`` once its routes are registered."""
    double = HttpDouble()
    try:
        yield double
    finally:
        double.stop()
