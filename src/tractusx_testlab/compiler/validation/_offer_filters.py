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

"""Warning about a negotiating step that has no filter to pick its offer by.

The run refuses such a step (:mod:`tractusx_testlab.steps.connector.offer_guard`);
the compiler says so first. Which steps negotiate is read off their contracts —
every step that takes ``allow_any_offer`` — not kept in a list here.
"""

from __future__ import annotations

from collections.abc import Iterator

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.extensions.extension import written_steps
from tractusx_testlab.models import TestDefinition
from tractusx_testlab.steps.connector.offer_guard import ALLOW_ANY_OFFER


def offer_filter_warnings(test: TestDefinition) -> Iterator[tuple[str, int, str, str]]:
    """``(phase, step index, field, message)`` for each negotiating step without filters."""
    for phase, idx, step in written_steps(test):
        uses = str(step.get("uses", ""))
        fields = getattr(
            getattr(StepRegistry.get_any(uses), "params_model", None), "model_fields", {}
        )
        if ALLOW_ANY_OFFER not in (fields or {}):
            continue
        params = step.get("with") or {}
        if params.get("filters") or params.get(ALLOW_ANY_OFFER) is True:
            continue
        yield (
            phase,
            idx,
            "with.filters",
            f"'{uses}' has no 'filters', so it would negotiate whichever offer the provider "
            "lists first; the run refuses it. Give 'filters' that select the asset, or "
            f"'{ALLOW_ANY_OFFER}: true' if any offer will do.",
        )
