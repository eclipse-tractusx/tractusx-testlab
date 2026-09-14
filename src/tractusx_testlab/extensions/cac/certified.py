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

"""``cac:`` references must name a standard the TCK certifies against."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tractusx_testlab.extensions.cac.references import CAC_REF
from tractusx_testlab.extensions.extension import ExtensionFinding, written_steps

if TYPE_CHECKING:
    from tractusx_testlab.models.authoring.definitions import TckDefinition, TestDefinition


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _cac_in(step: dict[str, Any]) -> list[tuple[str, str]]:
    """Every ``cac`` entry on one step and its checks, as (field, reference)."""
    found = [("cac", reference) for reference in _strings(step.get("cac"))]
    for check in step.get("validate") or []:
        if isinstance(check, dict):
            found += [("validate.cac", reference) for reference in _strings(check.get("cac"))]
    return found


def uncertified_cac(tck: TckDefinition, test: TestDefinition) -> list[ExtensionFinding]:
    """Every ``cac`` in *test* whose standard the manifest does not certify against.

    ``metadata.standards`` is what the conformity report is drawn up for, so a
    CAC of a standard missing from it — or of another version of one listed —
    is coverage the report would attribute to nothing. The usual cause is a
    version bump made in the manifest and not in the tests.
    """
    certified = {
        f"{standard.get('id')}:{standard.get('version')}" for standard in tck.metadata.standards
    }
    findings: list[ExtensionFinding] = []
    for phase, idx, step in written_steps(test):
        for field_name, reference in _cac_in(step):
            match = CAC_REF.match(reference)
            # A malformed entry was already refused by the model, in the
            # author's terms; only the standard it names is checked here.
            if match is None or f"{match['standard']}:{match['version']}" in certified:
                continue
            findings.append(
                ExtensionFinding(
                    message=(
                        f"cac '{reference}' belongs to {match['standard']} "
                        f"{match['version']}, which metadata.standards does not list. "
                        f"Listed: {', '.join(sorted(certified)) or 'none'}."
                    ),
                    step_index=idx,
                    field=field_name,
                    phase=phase,
                )
            )
    return findings
