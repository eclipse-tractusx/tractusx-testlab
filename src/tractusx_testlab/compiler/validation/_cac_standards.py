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

from tractusx_testlab.compiler.validation.issues import ValidationIssue
from tractusx_testlab.models import TckDefinition, TestDefinition
from tractusx_testlab.syntax import patterns

#: The ``with:`` keys under which a flow step carries nested step definitions.
#: A ``cac`` inside a branch is as much a claim about the standard as one at the
#: top level, so it is held to the same manifest.
_NESTED_STEP_KEYS = ("then", "else", "steps")


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _cac_in(step: dict) -> list[tuple[str, str]]:
    """Every ``cac`` entry in one step as written, nested flow steps included."""
    found = [("cac", reference) for reference in _strings(step.get("cac"))]
    for check in step.get("validate") or []:
        if isinstance(check, dict):
            found += [("validate.cac", reference) for reference in _strings(check.get("cac"))]
    if not str(step.get("uses", "")).startswith("flow/"):
        return found
    params = step.get("with") or {}
    for key in _NESTED_STEP_KEYS:
        for nested in params.get(key) or []:
            if isinstance(nested, dict):
                found += _cac_in(nested)
    return found


def uncertified_cac(tck: TckDefinition, test: TestDefinition) -> list[ValidationIssue]:
    """Every ``cac`` in *test* whose standard the manifest does not certify against.

    ``metadata.standards`` is what the conformity report is drawn up for, so a
    CAC of a standard missing from it — or of another version of one listed —
    is coverage the report would attribute to nothing. The usual cause is a
    version bump made in the manifest and not in the tests.
    """
    certified = {
        f"{standard.get('id')}:{standard.get('version')}" for standard in tck.metadata.standards
    }
    findings: list[ValidationIssue] = []
    for phase, steps in (
        ("setup", test.setup),
        ("execution", test.execution),
        ("teardown", test.teardown),
    ):
        for idx, step in enumerate(steps):
            written = step.model_dump(by_alias=True, exclude_none=True)
            for field_name, reference in _cac_in(written):
                match = patterns.CAC_REF.match(reference)
                # A malformed entry was already refused by the model, in the
                # author's terms; only the standard it names is checked here.
                if match is None or f"{match['standard']}:{match['version']}" in certified:
                    continue
                findings.append(
                    ValidationIssue(
                        level="error",
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
