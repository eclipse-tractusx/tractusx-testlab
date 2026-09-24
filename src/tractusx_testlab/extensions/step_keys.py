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

"""The keys extensions add to a test, to a step and to a ``validate:`` entry.

``TestDefinition``, ``StepDefinition`` and ``Assertion`` inherit these, so an extension's key is an
ordinary, typed field: the JSON Schema the IDE reads describes it, and a typo in
it is refused like any other. Whether the TCK *may* use it is the compiler's
check, driven by ``Extension.test_keys``, ``Extension.step_keys`` and
``Extension.validation_keys``.

To add keys, write a model of them in the extension's own package and add it to
the bases below. Keep the classes free of ``model_config``: the core models set
the strict config, and a base that set its own would be overridden anyway.
"""

from __future__ import annotations

from tractusx_testlab.extensions.cac.references import (
    CacAssertionKeys,
    CacStepKeys,
    CacTestKeys,
)


class TestExtensionKeys(CacTestKeys):
    """Every key an extension adds to a test (the top level of a ``kind: test`` file)."""

    __test__ = False  # a model, not a pytest test class


class StepExtensionKeys(CacStepKeys):
    """Every key an extension adds to a step."""


class AssertionExtensionKeys(CacAssertionKeys):
    """Every key an extension adds to a ``validate:`` entry."""
