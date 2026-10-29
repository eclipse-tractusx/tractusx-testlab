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

"""The names a step's ``returns:`` block may read: those the step publishes."""

from __future__ import annotations

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps._checks.extraction import declared_names
from tractusx_testlab.steps._checks.published_names import names_a_published_output


def returns_findings(step_def: StepDefinition, step_cls: type | None) -> list[str]:
    """One message per ``returns:`` name *step_cls* does not publish."""
    returns = step_def.returns or {}
    if not returns or step_cls is None:
        return []
    declared = declared_names(step_cls)
    return [
        f"'returns' name '{name}' is not produced by step "
        f"'{step_def.uses}'. It publishes: {', '.join(sorted(declared))}."
        for name in returns
        if not names_a_published_output(name, declared)
    ]
