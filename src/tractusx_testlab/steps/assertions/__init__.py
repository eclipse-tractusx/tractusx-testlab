#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""Assertions — the ``validate:`` vocabulary and the engine that runs it."""

from tractusx_testlab.steps.assertions.engine import AssertionEngine
from tractusx_testlab.steps.assertions.operators import (
    OPERATORS,
    RANGE_OPERATORS,
    UNARY_OPERATORS,
    AssertOperator,
    apply_operator,
)
from tractusx_testlab.steps.assertions.vocabulary import (
    DEFAULT_OPERATOR,
    AssertionKind,
    ResolvedAssertion,
    resolve,
)

__all__ = [
    "DEFAULT_OPERATOR",
    "OPERATORS",
    "RANGE_OPERATORS",
    "UNARY_OPERATORS",
    "AssertOperator",
    "AssertionEngine",
    "AssertionKind",
    "ResolvedAssertion",
    "apply_operator",
    "resolve",
]
