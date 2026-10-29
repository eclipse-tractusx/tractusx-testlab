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

"""Checking answers against an API document: responses, errors and leaks."""

from tractusx_testlab.openapi.conformance.error_conformance import (
    FORMATS,
    ErrorAnswer,
    error_problems,
)
from tractusx_testlab.openapi.conformance.leak_patterns import LEAK_PATTERNS, Leak, leaks_in
from tractusx_testlab.openapi.conformance.response_conformance import (
    CHECKS,
    DATA_PLANE_STATUSES,
    Problem,
    ResponseVerdict,
    check_response,
    documented_response,
    expect_matches,
)
from tractusx_testlab.openapi.conformance.validator_cache import (
    SchemaProblem,
    forget_validators,
    schema_problems,
)

__all__ = [
    "CHECKS",
    "DATA_PLANE_STATUSES",
    "FORMATS",
    "LEAK_PATTERNS",
    "ErrorAnswer",
    "Leak",
    "Problem",
    "ResponseVerdict",
    "SchemaProblem",
    "check_response",
    "documented_response",
    "error_problems",
    "expect_matches",
    "forget_validators",
    "leaks_in",
    "schema_problems",
]
